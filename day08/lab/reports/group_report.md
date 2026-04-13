# Group Report — Lab Day 08: RAG Pipeline

**Nhóm:** 25
**Ngày:** 2026-04-13
**Thành viên:**
| Tên | Vai trò |
|-----|---------|
| Thức | Tech Lead |
| Khang | Retrieval Owner |
| Duy | Eval Owner |
| Thư | Documentation Owner |

---

## 1. Tổng quan hệ thống

Nhóm xây dựng RAG pipeline trợ lý nội bộ cho CS + IT Helpdesk, trả lời câu hỏi về 5 tài liệu chính sách: hoàn tiền, SLA ticket, kiểm soát truy cập, IT FAQ, và nghỉ phép. Pipeline đảm bảo mọi câu trả lời đều grounded từ tài liệu, có citation, và abstain khi không đủ dữ liệu.

**Tech stack:**
- Embedding: OpenAI `text-embedding-3-small`
- Vector store: ChromaDB (PersistentClient, cosine similarity)
- LLM: `gpt-4o-mini` (temperature=0)
- Sparse search: BM25 (rank-bm25)
- Evaluation: LLM-as-Judge (gpt-4o-mini)

---

## 2. Quyết định kỹ thuật quan trọng

### Chunking strategy
Chọn heading-based chunking (split theo `=== Section ===`) thay vì fixed-size. Lý do: mỗi section trong tài liệu là một đơn vị ngữ nghĩa hoàn chỉnh (một điều khoản, một level quyền, một loại ticket). Cắt cố định theo token count có nguy cơ cắt giữa điều khoản.

- Chunk size: 400 tokens, overlap: 80 tokens
- Tổng: 29 chunks từ 5 tài liệu

### Retrieval strategy
Baseline dùng dense retrieval (cosine similarity). Sprint 3 thử hybrid (Dense + BM25 RRF). Kết luận: **baseline dense tốt hơn** với corpus nhỏ này — Context Recall đã đạt 5.00/5. Hybrid làm thay đổi thứ tự chunks, khiến một số câu trả lời kém chính xác hơn.

### Grounded prompt
Prompt áp dụng 4 nguyên tắc: evidence-only, abstain khi thiếu, citation bắt buộc, output ngắn gọn. Temperature=0 để output ổn định cho evaluation.

---

## 3. Kết quả evaluation

### Scorecard tóm tắt
| Metric | Baseline (Dense) | Variant (Hybrid) | Delta |
|--------|-----------------|-------------------|-------|
| Faithfulness | 4.70/5 | 4.10/5 | -0.60 |
| Answer Relevance | 4.60/5 | 4.20/5 | -0.40 |
| Context Recall | 5.00/5 | 5.00/5 | 0.00 |
| Completeness | 3.80/5 | 3.40/5 | -0.40 |

### Phân tích kết quả
- **Điểm mạnh**: Faithfulness và Context Recall cao, pipeline không hallucinate và retrieve đúng source.
- **Điểm yếu**: Completeness thấp nhất (3.80/5) — pipeline thường trả lời đúng nhưng thiếu chi tiết. Ví dụ q07 không nhận ra "Access Control SOP" là tên mới của "Approval Matrix".
- **Baseline vs Variant**: Dense tốt hơn hybrid. Corpus nhỏ (29 chunks) khiến dense search đã đủ chính xác. BM25 tokenize tiếng Việt bằng whitespace split không hiệu quả.

### Câu trả lời tốt nhất vs kém nhất
- **Tốt nhất**: q01 (SLA P1), q02 (Hoàn tiền 7 ngày), q08 (Remote 2 ngày) — 5/5 trên mọi metric.
- **Kém nhất**: q09 (ERR-403-AUTH) — pipeline nên abstain nhưng baseline lại suy luận từ tài liệu access control. q10 (VIP refund) — abstain đúng nhưng thiếu context phụ.

---

## 4. Bài học rút ra

1. **Corpus nhỏ → dense đủ tốt**: Với chỉ 29 chunks, embedding search đã cover hầu hết queries. Hybrid/rerank phát huy với corpus lớn hơn.
2. **Abstain là khó nhất**: Dạng câu hỏi "thông tin không có trong docs" khó hơn câu hỏi thông thường. Prompt cần rõ ràng hơn về khi nào nên từ chối.
3. **LLM-as-Judge tiết kiệm thời gian**: So với chấm thủ công 40 lần (4 metrics × 10 câu), LLM judge cho kết quả nhất quán và nhanh hơn nhiều.
4. **A/B rule quan trọng**: Chỉ đổi retrieval_mode (dense → hybrid) giúp xác định rõ hybrid kém hơn. Nếu đổi nhiều biến cùng lúc sẽ không biết nguyên nhân.

---

## 5. Nếu có thêm thời gian

1. **Rerank bằng cross-encoder**: Top-10 dense → cross-encoder → top-3. Giữ Context Recall nhưng cải thiện chunk ordering.
2. **Cải thiện BM25 tokenizer**: Dùng underthesea hoặc pyvi cho tiếng Việt thay vì whitespace split.
3. **Prompt tuning cho abstain**: Thêm rule "If none of the retrieved chunks directly mention the queried term, say you don't have information about it specifically" để cải thiện q09.
