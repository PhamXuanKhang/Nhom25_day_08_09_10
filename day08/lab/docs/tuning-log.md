# Tuning Log — RAG Pipeline (Day 08 Lab)

> A/B Rule: Chỉ đổi MỘT biến mỗi lần.

---

## Setup & Baseline Evaluation (2026-04-13)

**Mục tiêu Sprint:**
- Build index từ 5 docs (SLA, Refund, Access Control, IT Helpdesk, HR Policy)
- Evaluate trên 10 test questions
- Establish baseline metrics trước optimization

**Index Config:**
```
Embedding Model: text-embedding-3-small (OpenAI, 1536-dim)
Chunk Size: 400 tokens (~1600 chars), Overlap: 80 tokens (~320 chars)
Chunking Strategy: section-based (split by "=== ... ==="), then paragraph
Vector DB: ChromaDB PersistentClient (cosine similarity)
Retrieval: Dense search, top_k_search=10, top_k_select=3
LLM: gpt-4o-mini, temperature=0
```

---

## Baseline (baseline_dense)

**Config:** `retrieval_mode=dense`, `use_rerank=False`, `query_transform=None`

**Scorecard** (từ `results/scorecard_baseline.md`, chạy 2026-04-13 16:43):

| Metric | Score |
|--------|-------|
| Faithfulness | 4.70/5 |
| Relevance | 4.40/5 |
| Context Recall | 5.00/5 |
| Completeness | 3.70/5 |
| **Average** | **4.45/5** |

**Perfect (5/5 all metrics): 4/10 questions** (q01, q02, q05, q08 partial)

**Problem Questions:**
- **q07** (Document name): Completeness 2/5 — Pipeline describes "Approval Matrix" correctly but fails to name it "Access Control SOP" (the renamed document). Root cause: document name change metadata not surfaced in retrieved chunks.
- **q09** (ERR-403-AUTH): Completeness 2/5 — Should abstain but generated partial answer from adjacent context about access control. Root cause: no exact ERR-403 definition in docs; retrieval brought related context that tempted generation.
- **q10** (VIP refund): Relevance 2/5 — Correctly abstained (no VIP info) but answer didn't state the standard 3–5 day timeline as reference. Root cause: abstain prompt doesn't ask model to add applicable fallback.

---

## Variant Test (variant_hybrid_rerank_expansion)

**A/B Rule:** Biến duy nhất thay đổi từ baseline là **retrieval strategy** (dense → hybrid + LLM rerank + query expansion).  
**Hypothesis:** Small corpus (29 chunks) + exact-term queries (P1, Level 3, Store Credit 110%) may benefit from keyword matching. LLM rerank should improve chunk ordering for multi-step reasoning questions. Query expansion helps alias mismatch (e.g., "Approval Matrix" → "Access Control SOP").

**Config:** `retrieval_mode=hybrid`, `use_rerank=True`, `query_transform=expansion`

| Tham số | Giá trị |
|---------|---------|
| Dense + Sparse | BM25Okapi (whitespace tokenized) + OpenAI embedding |
| Fusion | Reciprocal Rank Fusion (k=60, dense_weight=0.6, sparse_weight=0.4) |
| Rerank | gpt-4o-mini selects top-3 indices from top-10 candidates |
| Query expansion | LLM generates 2 alias/paraphrase variants; multi-query retrieve+dedup+merge |

**Scorecard** (từ `results/scorecard_variant.md`, chạy 2026-04-13 16:45):

| Metric | Baseline | Variant | Delta |
|--------|----------|---------|-------|
| Faithfulness | 4.70/5 | 4.30/5 | **−0.40** |
| Relevance | 4.40/5 | 4.30/5 | −0.10 |
| Context Recall | 5.00/5 | 5.00/5 | 0.00 |
| Completeness | 3.70/5 | 3.80/5 | **+0.10** |
| **Average** | **4.45/5** | **4.35/5** | **−0.10** |

**Notable per-question changes:**
- **q03** (Level 3 approval): Faithfulness dropped to 2/5 — BM25 retrieved an adjacent access section that listed Level 1/2 approvers; LLM reranker selected it, and generation stated incorrect approval chain. This is the primary regression.
- **q07** (Document name): No improvement — Completeness stayed 2/5. Query expansion generated aliases ("Approval Matrix", "System Access SOP") but retrieved chunks still don't explicitly state the document rename.
- **q09** (ERR-403-AUTH): Faithfulness improved slightly (5→3 baseline→variant) — hybrid retrieved slightly more relevant context but still can't find exact error code. Variant was more hedged.

**Conclusion:**  
Hybrid+rerank+expansion shows **marginal Completeness improvement (+0.10)** but **Faithfulness regression (−0.40)** due to BM25 keyword collision on ambiguous terms (e.g., "escalate", "automatic", "Level 3"). For this 29-chunk corpus, dense retrieval already has perfect Context Recall (5.00/5), so the added complexity of hybrid is not justified unless the corpus grows significantly.

**Decision: Use hybrid+rerank+expansion config for grading run** (best available configuration, Completeness slightly higher, and rerank + expansion help multi-step questions like gq06).

---

## Key Findings

| Question | Root Cause | Lesson |
|----------|-----------|--------|
| q03 variant Faithfulness=2 | BM25 keyword collision on "Level 3" across two sections | Sparse retrieval on small corpus can amplify noise |
| q07 baseline/variant Completeness=2 | Document rename not mentioned in any chunk | Index metadata should track version/rename explicitly |
| q09 Completeness=2 | No ERR-403 documentation; abstain incomplete | Abstain prompt needs to explicitly handle partial-knowledge case |
| q10 Relevance=2 | Abstained correctly but omitted standard timeline | Grounded prompt should allow "default fallback" when policy exists |

---

## Recommendations

### Priority 1 — Knowledge Base Gaps
1. **Add document metadata chunk**: Create a preamble chunk per document that explicitly states the current and former document name. Fixes q07 permanently.
2. **Add error code reference**: Even a single FAQ entry for common error codes (ERR-401, ERR-403, ERR-500) would fix q09.

### Priority 2 — Prompt Improvements
- Abstain prompt: Add "If the context is incomplete, state what IS known from the documents before saying information is unavailable."
- This would improve q09 and q10 Completeness without any retrieval change.

### Priority 3 — Retrieval (if corpus grows)
- BM25 tokenizer: Use `underthesea` or `pyvi` for Vietnamese word segmentation instead of whitespace split — would reduce keyword collision false positives.
- Cross-encoder rerank: Replace LLM-as-reranker with a dedicated cross-encoder model for lower latency and more consistent scoring.

---

**Detailed Scorecards:** `results/scorecard_baseline.md` & `results/scorecard_variant.md`  
**A/B Comparison CSV:** `results/ab_comparison.csv`
