"""
rag_answer.py — Sprint 2 + Sprint 3: Retrieval & Grounded Answer
================================================================
Sprint 2 (60 phút): Baseline RAG
  - Dense retrieval từ ChromaDB
  - Grounded answer function với prompt ép citation
  - Trả lời được ít nhất 3 câu hỏi mẫu, output có source

Sprint 3 (60 phút): Tuning tối thiểu
  - Thêm hybrid retrieval (dense + sparse/BM25)
  - Hoặc thêm rerank (cross-encoder)
  - Hoặc thử query transformation (expansion, decomposition, HyDE)
  - Tạo bảng so sánh baseline vs variant

Definition of Done Sprint 2:
  ✓ rag_answer("SLA ticket P1?") trả về câu trả lời có citation
  ✓ rag_answer("Câu hỏi không có trong docs") trả về "Không đủ dữ liệu"

Definition of Done Sprint 3:
  ✓ Có ít nhất 1 variant (hybrid / rerank / query transform) chạy được
  ✓ Giải thích được tại sao chọn biến đó để tune
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CẤU HÌNH
# =============================================================================

TOP_K_SEARCH = 10    # Số chunk lấy từ vector store trước rerank (search rộng)
TOP_K_SELECT = 3     # Số chunk gửi vào prompt sau rerank/select (top-3 sweet spot)

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


# =============================================================================
# RETRIEVAL — DENSE (Vector Search)
# =============================================================================

def retrieve_dense(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Dense retrieval: tìm kiếm theo embedding similarity trong ChromaDB.

    Args:
        query: Câu hỏi của người dùng
        top_k: Số chunk tối đa trả về

    Returns:
        List các dict, mỗi dict là một chunk với:
          - "text": nội dung chunk
          - "metadata": metadata (source, section, effective_date, ...)
          - "score": cosine similarity score

    TODO Sprint 2:
    1. Embed query bằng cùng model đã dùng khi index (xem index.py)
    2. Query ChromaDB với embedding đó
    3. Trả về kết quả kèm score

    Gợi ý:
        import chromadb
        from index import get_embedding, CHROMA_DB_DIR

        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_collection("rag_lab")

        query_embedding = get_embedding(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        # Lưu ý: distances trong ChromaDB cosine = 1 - similarity
        # Score = 1 - distance
    """
    import chromadb
    from index import get_embedding, CHROMA_DB_DIR

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")

    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "metadata": meta,
            "score": round(1 - dist, 4),  # cosine distance → similarity
        })
    return chunks


# =============================================================================
# RETRIEVAL — SPARSE / BM25 (Keyword Search)
# Dùng cho Sprint 3 Variant hoặc kết hợp Hybrid
# =============================================================================

def retrieve_sparse(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Sparse retrieval: tìm kiếm theo keyword (BM25).

    Mạnh ở: exact term, mã lỗi, tên riêng (ví dụ: "ERR-403", "P1", "refund")
    Hay hụt: câu hỏi paraphrase, đồng nghĩa

    TODO Sprint 3 (nếu chọn hybrid):
    1. Cài rank_bm25: pip install rank-bm25
    2. Load tất cả chunks từ ChromaDB (hoặc rebuild từ docs)
    3. Tokenize và tạo BM25Index
    4. Query và trả về top_k kết quả

    Gợi ý:
        from rank_bm25 import BM25Okapi
        corpus = [chunk["text"] for chunk in all_chunks]
        tokenized_corpus = [doc.lower().split() for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    """
    import chromadb
    from rank_bm25 import BM25Okapi
    from index import CHROMA_DB_DIR

    # Load tất cả chunks từ ChromaDB
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")
    all_data = collection.get(include=["documents", "metadatas"])

    all_docs = all_data["documents"]
    all_metas = all_data["metadatas"]
    all_ids = all_data["ids"]

    if not all_docs:
        return []

    # Tokenize đơn giản (split whitespace, lowercase)
    tokenized_corpus = [doc.lower().split() for doc in all_docs]
    bm25 = BM25Okapi(tokenized_corpus)

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    return [
        {
            "text": all_docs[i],
            "metadata": all_metas[i],
            "score": round(float(scores[i]), 4),
            "id": all_ids[i],
        }
        for i in top_indices
        if scores[i] > 0
    ]


# =============================================================================
# RETRIEVAL — HYBRID (Dense + Sparse với Reciprocal Rank Fusion)
# =============================================================================

def retrieve_hybrid(
    query: str,
    top_k: int = TOP_K_SEARCH,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: kết hợp dense và sparse bằng Reciprocal Rank Fusion (RRF).

    Mạnh ở: giữ được cả nghĩa (dense) lẫn keyword chính xác (sparse)
    Phù hợp khi: corpus lẫn lộn ngôn ngữ tự nhiên và tên riêng/mã lỗi/điều khoản

    Args:
        dense_weight: Trọng số cho dense score (0-1)
        sparse_weight: Trọng số cho sparse score (0-1)

    TODO Sprint 3 (nếu chọn hybrid):
    1. Chạy retrieve_dense() → dense_results
    2. Chạy retrieve_sparse() → sparse_results
    3. Merge bằng RRF:
       RRF_score(doc) = dense_weight * (1 / (60 + dense_rank)) +
                        sparse_weight * (1 / (60 + sparse_rank))
       60 là hằng số RRF tiêu chuẩn
    4. Sort theo RRF score giảm dần, trả về top_k

    Khi nào dùng hybrid (từ slide):
    - Corpus có cả câu tự nhiên VÀ tên riêng, mã lỗi, điều khoản
    - Query như "Approval Matrix" khi doc đổi tên thành "Access Control SOP"
    """
    dense_results = retrieve_dense(query, top_k=top_k)
    sparse_results = retrieve_sparse(query, top_k=top_k)

    # Reciprocal Rank Fusion (RRF) — hằng số k=60 theo chuẩn
    K = 60
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, Dict] = {}

    for rank, chunk in enumerate(dense_results):
        key = chunk["metadata"].get("source", "") + "|" + chunk["text"][:50]
        rrf_scores[key] = rrf_scores.get(key, 0) + dense_weight * (1 / (K + rank + 1))
        chunk_map[key] = chunk

    for rank, chunk in enumerate(sparse_results):
        key = chunk["metadata"].get("source", "") + "|" + chunk["text"][:50]
        rrf_scores[key] = rrf_scores.get(key, 0) + sparse_weight * (1 / (K + rank + 1))
        chunk_map[key] = chunk

    sorted_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)[:top_k]
    return [
        {**chunk_map[k], "score": round(rrf_scores[k], 6)}
        for k in sorted_keys
    ]


# =============================================================================
# RERANK (Sprint 3 alternative)
# Cross-encoder để chấm lại relevance sau search rộng
# =============================================================================

def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = TOP_K_SELECT,
) -> List[Dict[str, Any]]:
    """
    Rerank các candidate chunks bằng LLM-as-Reranker (gpt-4o-mini).

    LLM được yêu cầu chọn top_k chunks relevant nhất với query và trả về
    danh sách index theo thứ tự giảm dần về relevance.

    Funnel logic: Search rộng (top-10) → LLM Rerank → top-3 vào prompt.
    Ưu điểm so với cross-encoder: không cần download model, dùng luôn API key có sẵn.
    """
    if len(candidates) <= top_k:
        return candidates

    # Tạo danh sách chunks để LLM chấm
    chunk_summaries = []
    for i, chunk in enumerate(candidates):
        source = chunk["metadata"].get("source", "?")
        section = chunk["metadata"].get("section", "")
        preview = chunk["text"][:300].replace("\n", " ")
        chunk_summaries.append(f"[{i}] {source} | {section}\n{preview}")

    chunks_text = "\n\n".join(chunk_summaries)

    prompt = f"""You are a relevance judge. Given a user question and a list of text chunks,
select the {top_k} most relevant chunk indices that best answer the question.

Question: {query}

Chunks:
{chunks_text}

Return ONLY a JSON array of {top_k} integer indices in order of relevance (most relevant first).
Example: [2, 0, 5]
Return ONLY the JSON array, no explanation."""

    try:
        from openai import OpenAI
        import json as _json

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=64,
        )
        raw = response.choices[0].message.content.strip()
        # Parse JSON array — strip markdown fences if present
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        indices = _json.loads(raw)
        # Validate: keep only valid indices, deduplicate, cap at top_k
        seen = set()
        selected = []
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(candidates) and idx not in seen:
                selected.append(candidates[idx])
                seen.add(idx)
            if len(selected) == top_k:
                break
        # Fill remaining slots if LLM returned fewer than top_k
        if len(selected) < top_k:
            for i, c in enumerate(candidates):
                if i not in seen:
                    selected.append(c)
                if len(selected) == top_k:
                    break
        return selected
    except Exception:
        # Fallback: trả về top_k đầu tiên nếu LLM rerank thất bại
        return candidates[:top_k]


# =============================================================================
# QUERY TRANSFORMATION (Sprint 3 alternative)
# =============================================================================

def transform_query(query: str, strategy: str = "expansion") -> List[str]:
    """
    Biến đổi query để tăng recall.

    Strategies được implement:
      - "expansion": LLM sinh 2 alias/paraphrase. Mỗi variant được retrieve độc lập,
        kết quả merge + dedup trước khi rerank/select. Giải quyết alias mismatch
        (vd: "Approval Matrix" → cũng tìm "Access Control SOP").
      - "decomposition": LLM tách query phức tạp thành 2-3 sub-queries độc lập.
        Phù hợp khi query hỏi nhiều thứ cùng lúc.
      - "hyde": LLM sinh một câu trả lời giả (hypothetical answer). Embed câu trả lời
        đó thay vì query gốc để tìm chunks có ngữ nghĩa gần với answer hơn.

    Returns:
        List[str]: Danh sách queries để retrieve (1 hoặc nhiều).
        Caller nên retrieve từng query rồi merge + dedup kết quả.
    """
    try:
        from openai import OpenAI
        import json as _json

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        if strategy == "expansion":
            prompt = f"""Given this search query about internal company policies:
"{query}"

Generate 2 alternative phrasings or related terms that could help find the same information.
Consider: synonyms, old names vs new names, Vietnamese/English variants, abbreviations.

Return ONLY a JSON array of 2 strings. Example: ["phrasings 1", "phrasing 2"]"""

        elif strategy == "decomposition":
            prompt = f"""Break down this complex query into 2-3 simpler, independent sub-queries:
"{query}"

Each sub-query should be self-contained and searchable on its own.
Return ONLY a JSON array of strings. Example: ["sub-query 1", "sub-query 2"]"""

        elif strategy == "hyde":
            prompt = f"""Write a short, factual answer (2-3 sentences) to this question about internal company policies,
as if you were an expert who has read the relevant documents:
"{query}"

Write the hypothetical answer directly, no preamble."""
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=150,
            )
            hypothetical_answer = response.choices[0].message.content.strip()
            return [hypothetical_answer]  # Embed này thay cho query gốc

        else:
            return [query]

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip().strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        variants = _json.loads(raw)
        if isinstance(variants, list) and variants:
            # Luôn đặt query gốc đầu tiên để đảm bảo không mất recall
            all_queries = [query] + [v for v in variants if isinstance(v, str) and v != query]
            return all_queries[:3]  # Tối đa 3 queries để tránh quá nhiều API calls
        return [query]

    except Exception:
        return [query]


# =============================================================================
# GENERATION — GROUNDED ANSWER FUNCTION
# =============================================================================

def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """
    Đóng gói danh sách chunks thành context block để đưa vào prompt.

    Format: structured snippets với source, section, score (từ slide).
    Mỗi chunk có số thứ tự [1], [2], ... để model dễ trích dẫn.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        score = chunk.get("score", 0)
        text = chunk.get("text", "")

        # TODO: Tùy chỉnh format nếu muốn (thêm effective_date, department, ...)
        header = f"[{i}] {source}"
        if section:
            header += f" | {section}"
        if score > 0:
            header += f" | score={score:.2f}"

        context_parts.append(f"{header}\n{text}")

    return "\n\n".join(context_parts)


def build_grounded_prompt(query: str, context_block: str) -> str:
    """
    Xây dựng grounded prompt theo 4 quy tắc từ slide:
    1. Evidence-only: Chỉ trả lời từ retrieved context
    2. Abstain: Thiếu context thì nói không đủ dữ liệu
    3. Citation: Gắn source/section khi có thể
    4. Short, clear, stable: Output ngắn, rõ, nhất quán

    TODO Sprint 2:
    Đây là prompt baseline. Trong Sprint 3, bạn có thể:
    - Thêm hướng dẫn về format output (JSON, bullet points)
    - Thêm ngôn ngữ phản hồi (tiếng Việt vs tiếng Anh)
    - Điều chỉnh tone phù hợp với use case (CS helpdesk, IT support)
    """
    prompt = f"""Answer only from the retrieved context below.
If the context is insufficient to answer the question, say you do not know and do not make up information.
Cite the source field (in brackets like [1]) when possible.
Keep your answer short, clear, and factual.
Respond in the same language as the question.

Question: {query}

Context:
{context_block}

Answer:"""
    return prompt


def call_llm(prompt: str) -> str:
    """
    Gọi LLM để sinh câu trả lời.

    TODO Sprint 2:
    Chọn một trong hai:

    Option A — OpenAI (cần OPENAI_API_KEY):
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,     # temperature=0 để output ổn định, dễ đánh giá
            max_tokens=512,
        )
        return response.choices[0].message.content

    Option B — Google Gemini (cần GOOGLE_API_KEY):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text

    Lưu ý: Dùng temperature=0 hoặc thấp để output ổn định cho evaluation.
    """
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=512,
    )
    return response.choices[0].message.content


def rag_answer(
    query: str,
    retrieval_mode: str = "dense",
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
    use_rerank: bool = False,
    query_transform: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Pipeline RAG hoàn chỉnh: query → (transform) → retrieve → (rerank) → generate.

    Args:
        query: Câu hỏi
        retrieval_mode: "dense" | "sparse" | "hybrid"
        top_k_search: Số chunk lấy từ vector store (search rộng)
        top_k_select: Số chunk đưa vào prompt (sau rerank/select)
        use_rerank: Dùng LLM reranker để chọn top_k_select chunks tốt nhất
        query_transform: None | "expansion" | "decomposition" | "hyde"
                         Nếu không None, query được biến đổi trước khi retrieve.
                         Kết quả từ mọi variant được merge + dedup theo text.
        verbose: In thêm thông tin debug

    Returns:
        Dict với:
          - "answer": câu trả lời grounded
          - "sources": list source names trích dẫn
          - "chunks_used": list chunks đã dùng
          - "query": query gốc
          - "queries_used": list queries thực sự dùng để retrieve
          - "config": cấu hình pipeline đã dùng
    """
    config = {
        "retrieval_mode": retrieval_mode,
        "top_k_search": top_k_search,
        "top_k_select": top_k_select,
        "use_rerank": use_rerank,
        "query_transform": query_transform,
    }

    # --- Bước 1: Query Transformation (optional) ---
    if query_transform:
        queries = transform_query(query, strategy=query_transform)
    else:
        queries = [query]

    if verbose:
        print(f"\n[RAG] Original query: {query}")
        if len(queries) > 1:
            print(f"[RAG] Transformed queries ({query_transform}): {queries}")

    # --- Bước 2: Retrieve (cho mỗi query variant, rồi merge + dedup) ---
    def _retrieve(q: str) -> List[Dict[str, Any]]:
        if retrieval_mode == "dense":
            return retrieve_dense(q, top_k=top_k_search)
        elif retrieval_mode == "sparse":
            return retrieve_sparse(q, top_k=top_k_search)
        elif retrieval_mode == "hybrid":
            return retrieve_hybrid(q, top_k=top_k_search)
        else:
            raise ValueError(f"retrieval_mode không hợp lệ: {retrieval_mode}")

    if len(queries) == 1:
        candidates = _retrieve(queries[0])
    else:
        # Multi-query: merge kết quả, dedup theo text, giữ score cao nhất
        seen_texts: Dict[str, int] = {}  # text[:100] → index in candidates
        candidates = []
        for q in queries:
            for chunk in _retrieve(q):
                key = chunk["text"][:100]
                if key not in seen_texts:
                    seen_texts[key] = len(candidates)
                    candidates.append(chunk)
                else:
                    # Giữ score cao nhất nếu chunk đã tồn tại
                    existing_idx = seen_texts[key]
                    if chunk.get("score", 0) > candidates[existing_idx].get("score", 0):
                        candidates[existing_idx]["score"] = chunk["score"]
        # Sort lại theo score sau merge
        candidates.sort(key=lambda c: c.get("score", 0), reverse=True)
        candidates = candidates[:top_k_search]

    if verbose:
        print(f"[RAG] Retrieved {len(candidates)} candidates (mode={retrieval_mode})")
        for i, c in enumerate(candidates[:3]):
            print(f"  [{i+1}] score={c.get('score', 0):.3f} | {c['metadata'].get('source', '?')}")

    # --- Bước 3: Rerank (optional) ---
    if use_rerank:
        candidates = rerank(query, candidates, top_k=top_k_select)
    else:
        candidates = candidates[:top_k_select]

    if verbose:
        print(f"[RAG] After select: {len(candidates)} chunks")

    # --- Bước 3: Build context và prompt ---
    context_block = build_context_block(candidates)
    prompt = build_grounded_prompt(query, context_block)

    if verbose:
        print(f"\n[RAG] Prompt:\n{prompt[:500]}...\n")

    # --- Bước 4: Generate ---
    answer = call_llm(prompt)

    # --- Bước 5: Extract sources ---
    sources = list({
        c["metadata"].get("source", "unknown")
        for c in candidates
    })

    return {
        "query": query,
        "queries_used": queries,
        "answer": answer,
        "sources": sources,
        "chunks_used": candidates,
        "config": config,
    }


# =============================================================================
# SPRINT 3: SO SÁNH BASELINE VS VARIANT
# =============================================================================

def compare_retrieval_strategies(query: str) -> None:
    """
    So sánh các retrieval strategies với cùng một query.

    TODO Sprint 3:
    Chạy hàm này để thấy sự khác biệt giữa dense, sparse, hybrid.
    Dùng để justify tại sao chọn variant đó cho Sprint 3.

    A/B Rule (từ slide): Chỉ đổi MỘT biến mỗi lần.
    """
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)

    strategies = ["dense", "hybrid"]  # Thêm "sparse" sau khi implement

    for strategy in strategies:
        print(f"\n--- Strategy: {strategy} ---")
        try:
            result = rag_answer(query, retrieval_mode=strategy, verbose=False)
            print(f"Answer: {result['answer']}")
            print(f"Sources: {result['sources']}")
        except NotImplementedError as e:
            print(f"Chưa implement: {e}")
        except Exception as e:
            print(f"Lỗi: {e}")


# =============================================================================
# MAIN — Demo và Test
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 2 + 3: RAG Answer Pipeline")
    print("=" * 60)

    # Test queries từ data/test_questions.json
    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?",
        "Ai phải phê duyệt để cấp quyền Level 3?",
        "ERR-403-AUTH là lỗi gì?",  # Query không có trong docs → kiểm tra abstain
    ]

    print("\n--- Sprint 2: Test Baseline (Dense) ---")
    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = rag_answer(query, retrieval_mode="dense", verbose=True)
            print(f"Answer: {result['answer']}")
            print(f"Sources: {result['sources']}")
        except NotImplementedError:
            print("Chưa implement — hoàn thành TODO trong retrieve_dense() và call_llm() trước.")
        except Exception as e:
            print(f"Lỗi: {e}")

    print("\n--- Sprint 3: So sánh strategies ---")
    compare_retrieval_strategies("Approval Matrix để cấp quyền là tài liệu nào?")
    compare_retrieval_strategies("ERR-403-AUTH")

    print("\n\nViệc cần làm Sprint 2:")
    print("  1. Implement retrieve_dense() — query ChromaDB")
    print("  2. Implement call_llm() — gọi OpenAI hoặc Gemini")
    print("  3. Chạy rag_answer() với 3+ test queries")
    print("  4. Verify: output có citation không? Câu không có docs → abstain không?")

    print("\nViệc cần làm Sprint 3:")
    print("  1. Chọn 1 trong 3 variants: hybrid, rerank, hoặc query transformation")
    print("  2. Implement variant đó")
    print("  3. Chạy compare_retrieval_strategies() để thấy sự khác biệt")
    print("  4. Ghi lý do chọn biến đó vào docs/tuning-log.md")
