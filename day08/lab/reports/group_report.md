# Group Report — Lab Day 08: RAG Pipeline

**Nhóm:** Nhóm 25
**Ngày:** 2026-04-13
**Thành viên:**
| Tên | Vai trò |
|-----|---------|
| Phạm Xuân Khang | Tech Lead |
| Nguyễn Văn Thức | Retrieval Owner |
| Phạm Thành Duy | Eval Owner |
| Nguyễn Thị Thu Ngọc | Documentation Owner |

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
Baseline dùng dense retrieval (cosine similarity). Sprint 3 implement variant với **hybrid (Dense + BM25 RRF) + LLM Reranker + Query Expansion**. Kết quả: variant cải thiện nhẹ Completeness (+0.10) nhưng giảm Faithfulness (−0.40) do BM25 keyword collision trên corpus nhỏ. Context Recall giữ nguyên 5.00/5. Đối với grading run, nhóm chọn dùng hybrid+rerank+expansion (config tốt nhất có sẵn) vì Completeness cao hơn và rerank+expansion giúp các câu multi-hop phức tạp.

### Grounded prompt
Prompt áp dụng 4 nguyên tắc: evidence-only, abstain khi thiếu, citation bắt buộc, output ngắn gọn. Temperature=0 để output ổn định cho evaluation.

---

## 3. Kết quả evaluation

### Scorecard tóm tắt
| Metric | Baseline (Dense) | Variant (Hybrid+Rerank+Expansion) | Delta |
|--------|-----------------|-----------------------------------|-------|
| Faithfulness | 4.70/5 | 4.30/5 | −0.40 |
| Answer Relevance | 4.40/5 | 4.30/5 | −0.10 |
| Context Recall | 5.00/5 | 5.00/5 | 0.00 |
| Completeness | 3.70/5 | 3.80/5 | **+0.10** |

### Phân tích kết quả
- **Điểm mạnh**: Context Recall 5.00/5 trên cả hai config — retrieval không bao giờ bỏ sót expected source. Faithfulness baseline cao (4.70/5) — model bám sát context, không hallucinate.
- **Điểm yếu**: Completeness thấp nhất (3.70–3.80/5) — pipeline trả lời đúng nhưng hay thiếu chi tiết. Ví dụ q07 không nhận ra "Access Control SOP" là tên mới của "Approval Matrix" vì không có chunk nào ghi rõ tên cũ.
- **Baseline vs Variant**: Hybrid+rerank+expansion cải thiện nhẹ Completeness (+0.10) nhờ multi-query expansion và LLM reranker chọn chunk tốt hơn. Tuy nhiên, Faithfulness giảm (−0.40) do BM25 keyword collision — q03 Level 3 approval lấy nhầm section, dẫn đến hallucination.

### Câu trả lời tốt nhất vs kém nhất
- **Tốt nhất**: q01 (SLA P1), q02 (Hoàn tiền 7 ngày), q05 (Account lockout) — 5/5 trên mọi metric cả baseline lẫn variant.
- **Kém nhất**: q09 (ERR-403-AUTH) — pipeline nên abstain hoàn toàn nhưng lại suy luận từ context access control liên quan. q10 (VIP refund) — abstain đúng nhưng thiếu context phụ (standard timeline). q03 variant — Faithfulness 2/5 do BM25 gây nhiễu.

---

## 4. Bài học rút ra

1. **Context Recall ≠ Answer Quality**: Dù Context Recall đạt 5.00/5 (retrieval không bao giờ bỏ sót source), Completeness vẫn chỉ 3.70–3.80/5. Retrieval đúng nguồn là điều kiện cần, không phải đủ — generation vẫn có thể bỏ sót chi tiết quan trọng trong chunk đó.
2. **Abstain là khó nhất**: q09 (ERR-403-AUTH không có trong docs) là câu khó nhất. Pipeline retrieve đúng context liên quan (access control), nhưng generation bị "tempted" bởi partial match thay vì abstain sạch. Cần prompt rule rõ hơn: "If the specific term queried is not mentioned verbatim in any chunk, abstain."
3. **BM25 keyword collision trong corpus nhỏ**: Thuật ngữ như "escalate", "automatic", "Level 3" xuất hiện trong cả section SLA lẫn Access Control. Trên corpus 29 chunks, BM25 khuếch đại nhiễu này thay vì giảm. Dense embedding xử lý tốt hơn vì nó hiểu ngữ nghĩa toàn câu.
4. **LLM-as-Judge tiết kiệm thời gian nhưng cần calibration**: So với chấm thủ công 40 lần (4 metrics × 10 câu), LLM judge cho kết quả nhất quán. Tuy nhiên, judge đôi khi quá strict (q03 variant: faithfulness=2 khi câu trả lời thực ra đúng về nội dung) — cần reference answer tốt hơn để calibrate.
5. **A/B rule quan trọng**: Chỉ thay đổi một biến (dense → hybrid+rerank+expansion) giúp xác định rõ nguyên nhân của sự khác biệt. Nếu đổi nhiều biến cùng lúc (chunking + retrieval + prompt) sẽ không thể attribute regression cho biến nào.

---

## 5. Nếu có thêm thời gian

1. **Metadata chunk cho document identity**: Thêm một chunk mở đầu mỗi tài liệu ghi rõ tên hiện tại và tên cũ (ví dụ: "Tài liệu này trước đây có tên 'Approval Matrix for System Access', hiện được đổi tên thành 'Access Control SOP'"). Sẽ fix q07 và các câu hỏi về document versioning mà không cần thay đổi retrieval.
2. **Cải thiện BM25 tokenizer**: Dùng `underthesea` hoặc `pyvi` cho word segmentation tiếng Việt thay vì whitespace split. Sẽ giảm false positive từ partial keyword match (ví dụ: "level" vs "Level 3").
3. **Prompt tuning cho abstain**: Thêm rule "If the specific term is not found in any chunk, explicitly state that, then mention what related information IS available." Cải thiện q09 (ERR-403) và q10 (VIP refund) Completeness mà không cần re-index.
4. **Sử dụng grading run scores để iterate**: Sau khi nhận kết quả grading, so sánh với scorecard để xác định câu nào pipeline fail — dùng làm hard negatives cho prompt tuning tiếp theo.
