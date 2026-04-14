"""
setup_index.py — Build ChromaDB index từ data/docs/.

Chạy một lần trước khi run graph:
    python setup_index.py

Script:
- Đọc tất cả .txt files trong data/docs/
- Chunk nội dung theo section (tách bằng "=== ... ===")
- Embed bằng shared helper: SentenceTransformer → OpenAI → deterministic random fallback
- Lưu vào ChromaDB persistent client tại ./chroma_db
- Collection name: day09_docs (cosine distance)

Idempotent: chạy lại sẽ xóa collection cũ và tạo mới.
"""

import os
import re
import sys
from pathlib import Path

from workers.embedding_utils import embed_texts, get_embedding_fn

# Load .env nếu có
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


DOCS_DIR = Path(__file__).parent / "data" / "docs"
CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "day09_docs")


def chunk_by_section(text: str, source: str) -> list:
    """Split text thành chunks theo markers '=== ... ===' hoặc '---'.

    Mỗi chunk giữ lại header (nếu có) để context rõ hơn khi retrieve.
    """
    sections = re.split(r"(?=^===\s.+\s===$)", text, flags=re.MULTILINE)
    sections = [s.strip() for s in sections if s.strip()]

    if len(sections) <= 1:
        # Không có section markers → split theo paragraph
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        sections = paragraphs

    chunks = []
    for idx, section in enumerate(sections):
        if len(section) > 1800:
            # Sub-chunk mechanical (1500 char overlap-safe)
            for sub_idx, start in enumerate(range(0, len(section), 1500)):
                sub = section[start : start + 1500]
                chunks.append({
                    "id": f"{source}__sec{idx:02d}_sub{sub_idx:02d}",
                    "text": sub,
                    "source": source,
                    "section_idx": idx,
                })
        else:
            chunks.append({
                "id": f"{source}__sec{idx:02d}",
                "text": section,
                "source": source,
                "section_idx": idx,
            })
    return chunks


def main() -> int:
    # ── Kiểm tra dependencies ──
    try:
        import chromadb
    except ImportError:
        print("❌ chromadb chưa được cài. Chạy: pip install -r requirements.txt", file=sys.stderr)
        return 1

    if not DOCS_DIR.exists():
        print(f"❌ Không tìm thấy thư mục docs: {DOCS_DIR}", file=sys.stderr)
        return 1

    print(f"📂 Docs directory  : {DOCS_DIR}")
    print(f"💾 ChromaDB path   : {CHROMA_PATH}")
    print(f"🔖 Collection      : {COLLECTION_NAME}")
    print("🧠 Embedding model : shared helper (SentenceTransformer → OpenAI → random)")
    print("-" * 60)

    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Xóa collection cũ (idempotent)
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
        print(f"🗑  Deleted old collection '{COLLECTION_NAME}'")
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # ── Đọc và chunk tất cả .txt files ──
    all_chunks = []
    for txt_file in sorted(DOCS_DIR.glob("*.txt")):
        content = txt_file.read_text(encoding="utf-8")
        chunks = chunk_by_section(content, txt_file.name)
        all_chunks.extend(chunks)
        print(f"  • {txt_file.name}: {len(chunks)} chunks")

    if not all_chunks:
        print("❌ Không tìm thấy chunk nào để index.", file=sys.stderr)
        return 1

    print(f"\n🔢 Embedding {len(all_chunks)} chunks via shared embedding helper...")
    texts = [c["text"] for c in all_chunks]
    embeddings = embed_texts(texts)

    if len(embeddings) != len(all_chunks):
        print(
            f"❌ Embedding count mismatch: got {len(embeddings)}, expected {len(all_chunks)}",
            file=sys.stderr,
        )
        return 1

    # ── Upsert vào ChromaDB ──
    collection.add(
        ids=[c["id"] for c in all_chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[
            {"source": c["source"], "section_idx": c["section_idx"]}
            for c in all_chunks
        ],
    )

    print(f"\n✅ Indexed {collection.count()} chunks into '{COLLECTION_NAME}'.")

    # ── Smoke test ──
    print("\n🔎 Smoke test query: 'SLA P1 resolution time'")
    q_emb = get_embedding_fn()("SLA P1 resolution time")
    res = collection.query(query_embeddings=[q_emb], n_results=2)
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        print(f"  [sim={1 - dist / 2:.3f}] {meta['source']}: {doc[:80]}...")

    print("\n✅ Index ready. Giờ có thể chạy `python graph.py`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
