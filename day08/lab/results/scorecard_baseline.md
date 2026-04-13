# Scorecard: baseline_dense
**Generated**: 2026-04-13 15:58:11
**Status**: ✅ Baseline Configuration

## Summary

| Metric | Score | Rating |
|--------|-------|--------|
| Faithfulness | 4.70/5 | ⭐⭐⭐⭐ |
| Relevance | 4.50/5 | ⭐⭐⭐⭐ |
| Context Recall | 5.00/5 | ⭐⭐⭐⭐⭐ |
| Completeness | 4.10/5 | ⭐⭐⭐⭐ |
| **Overall Average** | **4.58/5** | ⭐⭐⭐⭐ |

## Configuration Details

```
Embedding Model: paraphrase-multilingual-MiniLM-L12-v2
Chunk Size: 400 tokens
Chunk Overlap: 80 tokens
Retrieval Strategy: Dense vector search (cosine similarity)
Top-K Retrieved: 5
Vector Database: ChromaDB
LLM: GPT-4
Temperature: 0.7
```

## Per-Question Results

| ID | Category | Faith | Relev | Recall | Complete | Status |
|----|----------|-------|-------|--------|----------|--------|
| q01 | SLA | 5 | 5 | 5 | 5 | ✅ Perfect |
| q02 | Refund | 5 | 5 | 5 | 5 | ✅ Perfect |
| q03 | Access Control | 4 | 5 | 5 | 5 | ✅ Good |
| q04 | Refund | 4 | 4 | 5 | 3 | ⚠️ Fair |
| q05 | IT Helpdesk | 5 | 5 | 5 | 5 | ✅ Perfect |
| q06 | SLA | 4 | 5 | 5 | 4 | ✅ Good |
| q07 | Access Control | 5 | 3 | 5 | 2 | ⚠️ Needs Work |
| q08 | HR Policy | 5 | 5 | 5 | 5 | ✅ Perfect |
| q09 | Insufficient Context | 5 | 5 | N/A | 2 | ⚠️ Limited Context |
| q10 | Refund | 5 | 3 | 5 | 5 | ⚠️ Poor Relevance |

## Analysis

### Strengths ✅

1. **Perfect Context Recall (5.0/5)**: Vector search finds all relevant documents
   - Every question retrieves relevant context correctly
   - Excellent coverage across all document types

2. **Strong Faithfulness (4.7/5)**: Answers grounded in context
   - 7 out of 10 questions have maximum faithfulness
   - Only minor hallucinations in q03, q04

3. **Consistent Completeness (4.1/5)**: Mostly comprehensive answers
   - 5 questions with perfect completeness (q01, q02, q03, q05, q08)
   - q10 has good completeness despite lower relevance

### Weaknesses ❌

1. **Completeness Gap in 3 Questions**
   - **q07**: Missing specific document name change ("Approval Matrix" → "Access Control SOP")
   - **q09**: Insufficient context - no source documents for ERR-403-AUTH
   - **q10**: Missing detail about VIP refund policy

2. **Relevance Issues**
   - **q07**: Relevance 3/5 - retrieval brought general document description
   - **q10**: Relevance 3/5 - question about VIP refund lacking specific information

3. **Knowledge Base Gaps**
   - No specific error code documentation (q09: ERR-403-AUTH)
   - Limited VIP-specific business policies (q10)

## Comparison with Variant (variant_hybrid_only)

| Metric | Baseline | Variant | Change |
|--------|----------|---------|--------|
| Faithfulness | 4.7 | 4.5 | -0.20 ❌ |
| Relevance | 4.5 | 4.2 | -0.30 ❌ |
| Context Recall | 5.0 | 5.0 | → ✅ |
| Completeness | 4.1 | 3.6 | -0.50 ❌ |
| **Overall** | **4.58** | **4.33** | **-0.25** |

✅ **Baseline outperforms variant by 0.25 points** - Dense vector search is more reliable than hybrid approach for this use case.

## Problem Questions Deep Dive

### 🔴 q07 - Document Name Change (Completeness: 2/5)
**Question**: "Approval Matrix để cấp quyền hệ thống là tài liệu nào?"

**Issue**: Missing specific document title change
- **Expected**: Mention 'Access Control SOP' as the current name
- **Got**: General description of what Approval Matrix is
- **Root Cause**: Chunking hasn't preserved document version/name changes

**Recommendation**: 
- Include "DOCUMENT UPDATE" metadata in chunks
- Explicit chunking rule: preserve section on "document name changes"

---

### 🔴 q09 - Error Code Documentation (Completeness: 2/5)
**Question**: "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Issue**: No coverage in documents
- **Expected**: Error code explanation + resolution steps
- **Got**: Limited context message
- **Root Cause**: Error codes not documented in current knowledge base

**Recommendation**:
- Create error code reference documentation
- Map common errors to resolution procedures
- Link to IT Helpdesk documentation

---

### 🟡 q10 - VIP Refund Policy (Completeness: 5/5, but Relevance: 3/5)
**Question**: "Nếu cần hoàn tiền khẩn cấp cho khách hàng VIP, quy trình có khác không?"

**Issue**: Correct answer but retrieval not specific
- **Expected**: VIP-specific refund procedures
- **Got**: Accurate "no special VIP process" answer (incidental correctness)
- **Root Cause**: VIP customer service policies not explicitly documented

**Recommendation**:
- Add VIP customer service section to refund policy
- Document any special handling requirements
- Clarify standard vs. expedited processes

## Recommendations for Improvement

### Priority 1 - High Impact 🚀

1. ✏️ **Expand Knowledge Base**
   - [ ] Add error code documentation (ERR-403-AUTH, etc.)
   - [ ] Create VIP customer service procedures document
   - [ ] Document all metadata changes and version updates
   - [ ] Expected impact: +0.3 to +0.5 on completeness

2. 📝 **Improve Chunking Strategy**
   - [ ] Preserve exact document titles and references
   - [ ] Mark document metadata changes explicitly
   - [ ] Keep definitions and references co-located
   - [ ] Expected impact: +0.2 on completeness

### Priority 2 - Medium Impact ⚡

3. 🎯 **Enhance Prompts**
   - [ ] Request specific document names when available
   - [ ] Include confidence levels for incomplete questions
   - [ ] Provide structural outline for complex topics
   - [ ] Expected impact: +0.15 on completeness

4. 🔍 **Optimize Retrieval**
   - [ ] Experiment with query expansion for error codes
   - [ ] Add domain-specific synonyms
   - [ ] Test BM25 hybrid search for terminology
   - [ ] Expected impact: +0.1 on relevance

### Priority 3 - Fine Tuning 🎨

5. 📊 **Add Few-Shot Examples**
   - [ ] Include examples of complete, well-cited answers
   - [ ] Show examples of appropriate "insufficient context" responses
   - [ ] Expected impact: +0.1 on completeness

## Success Metrics & Next Steps

### Immediate (This Sprint)
✅ Baseline captured (April 13)
- [ ] Implement Priority 1 improvements
- [ ] Rebuild index with expanded docs
- [ ] Re-evaluate on same test set

### Target Metrics (v2.0)
Expected scores after Priority 1 fixes:
- Faithfulness: 4.7 → 4.8 (+0.1)
- Relevance: 4.5 → 4.7 (+0.2)
- Context Recall: 5.0 → 5.0 (→)
- Completeness: 4.1 → 4.5 (+0.4)
- **Overall: 4.58 → 4.75 (+0.17)**

### Long-term (v3.0)
With Priority 2 + 3:
- **Target Overall: 4.85+**

---

**Dataset**: 10 questions across 5 categories (SLA, Refund, Access Control, IT Helpdesk, HR Policy)
**Source**: results/ab_comparison.csv (baseline_dense rows)
**Tracking**: results/baseline_tracking.csv
