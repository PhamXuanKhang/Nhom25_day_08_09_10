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
Embedding Model: paraphrase-multilingual-MiniLM-L12-v2
Chunk Size: 400 tokens, Overlap: 80 tokens
Vector DB: ChromaDB (cosine similarity)
Retrieval: Dense search, top-5
LLM: GPT-4
```

---

## Baseline (baseline_dense)

**Scorecard:**
| Metric | Score |
| Faithfulness | 4.70/5 |
| Relevance | 4.50/5 |
| Context Recall | 5.00/5 |
| Completeness | 4.10/5 |
| **Overall** | **4.58/5** |

**Perfect (5/5 all metrics): 6/10 questions** (q01, q02, q03, q05, q08)

**Problem Questions:**
- **q07** (Document name): Completeness 2/5 — Missing "Access Control SOP" name change
- **q09** (Error code): Completeness 2/5 — Insufficient context (ERR-403-AUTH not in docs)
- **q10** (VIP refund): Relevance 3/5 — No VIP-specific policies documented

**Root Causes:**
- Completeness gaps: Missing specific details & document metadata
- Knowledge base gaps: No error codes, no VIP policies
- Context Recall excellent (5/5) → retrieval working well

**Files generated:**
- `baseline_config.json` — Config snapshot
- `baseline_tracking.csv` — Tracking metrics
- `scorecard_baseline.md` — Detailed analysis

---

## Variant Test (variant_hybrid_only)

**Change:** Dense search → **Hybrid (Dense + BM25 with re-ranking)**
**Hypothesis:** Keyword matching + semantic search might improve completeness for technical terms (P1, Level 3, ERR-403)

**Scorecard:**
| Metric | Baseline | Variant | Delta |
|--------|----------|---------|-------|
| Faithfulness | 4.70 | 4.50 | -0.20 |
| Relevance | 4.50 | 4.20 | -0.30 |
| Context Recall | 5.00 | 5.00 | no change |
| Completeness | 4.10 | 3.60 | -0.50 |
| **Overall** | **4.58** | **4.33** | **-0.25** |

**Perfect answers: 3/10** — Worse than baseline: 6/10

**Critical Issues:**
- **q03**: Faithfulness 2/5 (Hallucination) — Wrong section retrieved
- **q06**: Completeness 1/5 (Critical) — Retrieved "temporary access" instead of "P1 escalation"
- **q10**: Relevance 2/5 — Worse VIP handling

**Root Cause:**
Domain confusion from keyword matching:
- "escalate" + "automatic" words appear in both incident & access sections
- BM25 picked wrong section → LLM generated wrong answer
- Re-ranking couldn't distinguish semantic contexts

**Conclusion:** 
Hybrid retrieval **made things worse**. Dense-only is better for this corpus. Simpler = more robust.

**Files generated:**
- `scorecard_variant.md` — Detailed failure analysis
- `scorecard_comparison.md` — A/B comparison

---

## Key Findings

| Question | Root Cause | Fix Priority |
|----------|-----------|--------------|
| q07 (Doc name) | Missing metadata in chunks | P1: Add doc version info |
| q09 (Error codes) | No error documentation | P1: Create error reference |
| q10 (VIP policy) | Missing business rules | P1: Add VIP procedures |
| q06 (Retrieval) | Keyword confusion | P2: Better re-ranking (can't fix with hybrid) |

---

## Recommendations

### Priority 1 (High Impact)
1. **Expand Knowledge Base**: Add error codes, VIP policies, document metadata
2. **Improve Chunking**: Preserve exact document names and version changes  
3. **Strict Prompts**: "Only use information from context"

### Priority 2 (Medium Impact)
- Try cross-encoder re-ranking instead of hybrid
- Add few-shot examples for completeness
- Fine-tune prompts for edge cases

### Lessons Learned
- Dense retrieval outperforms hybrid for small corpus
- Simpler systems are more robust
- Test before deploying — variant would break production
- Completeness is the bottleneck, not retrieval  

---

**Tracking:** `results/baseline_tracking.csv`  
**Detailed Scorecards:** `results/scorecard_baseline.md` & `results/scorecard_variant.md`  
**Comparison:** `results/scorecard_comparison.md`
