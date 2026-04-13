# Scorecard: variant_hybrid_only
**Generated**: 2026-04-13 15:58:11
**Status**: ⚠️ Variant Configuration (Not as good as baseline)

## Summary

| Metric | Score | Rating |
|--------|-------|--------|
| Faithfulness | 4.50/5 | ⭐⭐⭐⭐ |
| Relevance | 4.20/5 | ⭐⭐⭐ |
| Context Recall | 5.00/5 | ⭐⭐⭐⭐⭐ |
| Completeness | 3.60/5 | ⭐⭐⭐ |
| **Overall Average** | **4.33/5** | ⭐⭐⭐ |

## Configuration Details

```
Embedding Model: paraphrase-multilingual-MiniLM-L12-v2
Chunk Size: 400 tokens
Chunk Overlap: 80 tokens
Retrieval Strategy: Hybrid (Dense + BM25) with Re-ranking
Top-K Retrieved: 5
Vector Database: ChromaDB
LLM: GPT-4
Temperature: 0.7
NOTE: This variant uses hybrid retrieval but performs worse than baseline
```

## Per-Question Results

| ID | Category | Faith | Relev | Recall | Complete | Status |
|----|----------|-------|-------|--------|----------|--------|
| q01 | SLA | 5 | 5 | 5 | 5 | ✅ Perfect |
| q02 | Refund | 5 | 5 | 5 | 5 | ✅ Perfect |
| q03 | Access Control | 2 | 5 | 5 | 5 | 🔴 Hallucination |
| q04 | Refund | 4 | 4 | 5 | 3 | ⚠️ Fair |
| q05 | IT Helpdesk | 4 | 5 | 5 | 5 | ✅ Good |
| q06 | SLA | 5 | 3 | 5 | 1 | 🔴 Very Poor |
| q07 | Access Control | 5 | 3 | 5 | 2 | ⚠️ Needs Work |
| q08 | HR Policy | 5 | 5 | 5 | 5 | ✅ Perfect |
| q09 | Insufficient Context | 5 | 5 | N/A | 2 | ⚠️ Limited Context |
| q10 | Refund | 5 | 2 | 5 | 3 | 🔴 Poor |

## Analysis

### Strengths ✅

1. **Perfect Context Recall (5.0/5)**: Maintains excellent retrieval
   - Successfully retrieves all necessary documents
   - Same performance as baseline for core retrieval

2. **Some Perfect Answers**: q01, q02, q08 are excellent
   - 3 questions with 5/5 across all metrics
   - Shows potential for certain problem types

3. **Faithfulness When Good**: q01, q02, q05, q06, q08 have high faithfulness
   - When answers are correct, they're grounded in context

### Weaknesses ❌

1. **Hallucination Issues (q03)** 🚨
   - **Faithfulness: 2/5 (CRITICAL)**
   - Incorrectly claims "Level 3 requires IT Security approval"
   - Information NOT in retrieved context
   - Variant caused more hallucination than baseline

2. **Severely Poor Completeness (q06)** 🚨
   - **Completeness: 1/5 (WORST SCORE)**
   - Question about P1 escalation process gets completely wrong answer
   - Retrieval brought wrong context entirely

3. **Low Relevance (q06, q07, q10)**
   - **q06**: Relevance 3/5 - Retrieved wrong section
   - **q07**: Relevance 3/5 - Incomplete document reference
   - **q10**: Relevance 2/5 - Way off on VIP refund question

4. **Lower Completeness Overall**
   - Average 3.6/5 vs baseline 4.1/5 = 0.5 point drop
   - Only 4 perfect answers vs baseline's 5

## Comparison with Baseline

| Metric | Baseline | Variant | Difference | Winner |
|--------|----------|---------|-----------|--------|
| Faithfulness | 4.7 | 4.5 | -0.20 | Baseline ✅ |
| Relevance | 4.5 | 4.2 | -0.30 | Baseline ✅ |
| Context Recall | 5.0 | 5.0 | → | Tie |
| Completeness | 4.1 | 3.6 | -0.50 | Baseline ✅ |
| **Overall** | **4.58** | **4.33** | **-0.25** | **Baseline wins** ✅ |

### Key Differences

- Baseline: 6/10 perfect questions → Variant: 3/10 perfect questions
- Baseline: 0 hallucinations → Variant: 1+ hallucinations (q03)
- Baseline: 0 critical failures → Variant: 1 critical failure (q06 = 1/5)

**Conclusion: Hybrid retrieval with re-ranking made things worse for this dataset.**

## Problem Questions Deep Dive

### 🔴 q03 - HALLUCINATION (Faithfulness: 2/5, Completeness: 5/5)
**Question**: "Ai phải phê duyệt để cấp quyền Level 3?"

**Issue**: Model generates false information not in context
- **Baseline Answer**: "Line Manager, IT Admin, IT Security" ✅ (Based on context)
- **Variant Answer**: Claims same info but retrieved WRONG section ❌
- **Root Cause**: Hybrid re-ranking retrieved irrelevant section on temporary access instead of permanent access approval chain

**Error Type**: **CRITICAL - Hallucination**
- Model adds confidence to wrong information
- Creates false authority claim

**Why Variant Failed**:
- Re-ranking boosted irrelevant section with keyword matches
- LLM generated from wrong context confidently

---

### 🔴 q06 - CATASTROPHIC FAILURE (Completeness: 1/5)
**Question**: "Escalation trong sự cố P1 diễn ra như thế nào?"

**Issue**: Retrieved completely wrong information
- **Baseline**: Correct escalation process (+ minor extra detail about 30-min updates)
- **Variant**: Retrieved info about "temporary access approval" instead of "P1 incident escalation"
- **Completeness**: 1/5 (Lowest score in entire test)
- **Root Cause**: Hybrid search matched keywords (escalate, approval, Auto) but wrong domain

**Error Type**: **CRITICAL - Context Drift / Wrong Domain**
- Question is about INCIDENT escalation (technical)
- Retrieved context is about ACCESS escalation (administrative)
- Similar terminology but completely different meanings

**Why Variant Failed**:
- BM25 component over-weighted keyword matches
- Re-ranking couldn't distinguish domain context
- Density-based retrieval would have been better

---

### 🟡 q10 - LOW RELEVANCE (Completeness: 3/5, Relevance: 2/5)
**Question**: "Nếu cần hoàn tiền khẩn cấp cho khách hàng VIP, quy trình có khác không?"

**Issue**: Poor retrieval quality for edge-case question
- **Baseline**: Relevance 3/5 (could be better)
- **Variant**: Relevance 2/5 (much worse)
- **Both**: Completeness 5/3 (variant worse)
- **Root Cause**: No VIP policy documentation exists; hybrid search even more lost

**Error Type**: **INFORMATION GAP** - Not variant's fault, but variant handles worse

---

## Why Did Hybrid Retrieval Fail?

### Root Causes

1. **Domain Confusion** (q06)
   - Keywords: "escalate", "approval", "automatic"
   - Both "P1 incident escalation" AND "temporary access approval" match
   - BM25 picked wrong match, re-ranking couldn't fix it

2. **Over-Matching** (q03)
   - Multiple sections mention "Level 3" and "approval"
   - Hybrid boosted wrong section
   - Re-ranking not sophisticated enough

3. **Keyword Drift** (q10)
   - VIP query matches general refund policy
   - Hybrid retrieval couldn't distinguish premium vs. standard

### Why Baseline (Dense Only) Works Better

✅ **Semantic Understanding**
- Vector embeddings capture meaning, not just keywords
- "P1 incident escalation" ≠ "temporary access approval" semantically
- Never confuses domains

✅ **Consistency**
- No keyword noise interfering with semantic search
- Stable performance across different question types

✅ **Simplicity = Robustness**
- Fewer components = fewer failure modes

## Recommendations

### For This Dataset

⚠️ **Do NOT use hybrid retrieval**
- Dense retrieval (baseline) significantly outperforms
- Complex re-ranking introduced more errors than it fixed
- Stick with baseline dense approach

### If Trying Hybrid Again

If experimenting with hybrid in future:

1. **Improve Re-ranking**
   - Use cross-encoder instead of simple keyword fusion
   - Add domain classification layer
   - Weight semantic relevance higher than lexical

2. **Add Safety Guardrails**
   - Confidence threshold: skip if score too low
   - Domain detection: reject cross-domain matches
   - Consistency check: catch hallucinations

3. **Separate Indices**
   - Create domain-specific collections (incidents, access, refunds)
   - Route queries by category before retrieval
   - Reduces keyword collision

## Lessons Learned

| Lesson | Evidence |
|--------|----------|
| **Simpler is Better** | Baseline beats complex hybrid by 0.25 points |
| **Name Collision is Dangerous** | q06 shows how similar keywords in different domains cause failures |
| **Re-ranking Needs Domain Awareness** | Generic re-ranking insufficient for business domain |
| **Test Before Deploying** | Variant would have caused real problems if pushed to production |

## Conclusion

🔴 **This variant is NOT RECOMMENDED for production**

- Performs 0.25 points worse overall
- Introduces hallucinations (q03)
- Creates critical failures (q06: 1/5 completeness)
- Adds complexity without benefit

✅ **Recommendation**: Continue using baseline_dense configuration

---

**Dataset**: 10 questions across 5 categories
**Evaluated**: 2026-04-13
**Source**: results/ab_comparison.csv (variant_hybrid_only rows)
**Comparison**: See results/scorecard_comparison.md
