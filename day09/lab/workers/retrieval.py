"""
workers/retrieval.py — Retrieval Worker (Sprint 2)

Owner: Worker Owner (xem note.md)

Contract (xem contracts/worker_contracts.yaml):
    Input:  {"task": str, "retrieval_top_k"?: int = 3}
    Output: {
        "retrieved_chunks": [{"text","source","score","metadata"}, ...],
        "retrieved_sources": [str, ...],
        "worker_io_logs": [...]   # append-only
    }

Đặc tính:
- Stateless: input chỉ đọc, output ghi vào state theo contract.
- Fail-safe: ChromaDB error → trả về chunks=[] (để synthesis abstain).
- Embedding: OpenAI text-embedding-3-small (1536-dim, normalized).
  Fallback cuối: random 1536-dim (CHỈ cho smoke test, không có API key).

Test độc lập:
    python workers/retrieval.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "3"))
CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "day09_docs")

# Resolve chroma_path relative to project root (nơi chứa graph.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if not os.path.isabs(CHROMA_PATH):
    CHROMA_PATH = str(_PROJECT_ROOT / CHROMA_PATH)

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from workers.embedding_utils import get_embedding_fn


# ─────────────────────────────────────────────
# Singletons — khởi tạo một lần rồi cache
# ─────────────────────────────────────────────

_EMBED_FN = None
_COLLECTION = None


def _get_embedding_fn():
    """Trả về embedding function dùng OpenAI, cache singleton.

    Priority: SentenceTransformer → OpenAI → deterministic random fallback.
    """
    global _EMBED_FN
    if _EMBED_FN is not None:
        return _EMBED_FN

    _EMBED_FN = get_embedding_fn()
    return _EMBED_FN


def _get_collection():
    """Kết nối ChromaDB collection, cache singleton."""
    global _COLLECTION
    if _COLLECTION is not None:
        return _COLLECTION

    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        _COLLECTION = client.get_collection(COLLECTION_NAME)
    except Exception:
        _COLLECTION = client.get_or_create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        if _COLLECTION.count() == 0:
            print(
                f"⚠️  Collection '{COLLECTION_NAME}' trống. Chạy `python setup_index.py` trước.",
                file=sys.stderr,
            )
    return _COLLECTION


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """Dense retrieval: embed query → ChromaDB similarity search.

    Returns:
        list of {"text": str, "source": str, "score": float (0-1), "metadata": dict}
        Empty list nếu query fail — để synthesis abstain.
    """
    try:
        embed = _get_embedding_fn()
        query_embedding = embed(query)
        collection = _get_collection()

        if collection.count() == 0:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )

        chunks = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0] or [],
        ):
            meta = meta or {}
            # ChromaDB cosine distance: 0 (identical) → 2 (opposite). similarity = 1 - dist/2.
            # Với normalized embeddings, distance ∈ [0, 2]; clamp về [0,1] cho dễ đọc.
            score = max(0.0, min(1.0, 1.0 - dist / 2.0)) if dist is not None else 0.0
            chunks.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "score": round(score, 4),
                "metadata": meta,
            })
        return chunks

    except Exception as e:
        print(f"⚠️  ChromaDB retrieval failed: {e}", file=sys.stderr)
        return []


def run(state: dict) -> dict:
    """Worker entry point — gọi từ graph.py."""
    task = state.get("task", "")
    top_k = state.get("top_k", state.get("retrieval_top_k", DEFAULT_TOP_K))

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }

    try:
        chunks = retrieve_dense(task, top_k=top_k)
        sources = list(dict.fromkeys(c["source"] for c in chunks))

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
            "top_score": chunks[0]["score"] if chunks else 0.0,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state["worker_io_logs"].append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
        "Nhân viên probation được làm remote không?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")
