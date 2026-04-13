# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Phạm Xuân Khang
**Vai trò trong nhóm:** Tech Lead
**Ngày nộp:** 2026-04-13
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Với vai trò Tech Lead, tôi chịu trách nhiệm chính ở Sprint 2 và Sprint 3 — tức là toàn bộ retrieval pipeline và generation layer trong `rag_answer.py`.

Ở **Sprint 2**, tôi implement `retrieve_dense()` (query ChromaDB bằng embedding, trả về cosine similarity score), `call_llm()` (gọi `gpt-4o-mini` với temperature=0), và `rag_answer()` — hàm tổng hợp toàn bộ pipeline từ query đến grounded answer với citation.

Ở **Sprint 3**, tôi implement ba Sprint 3 variant: `retrieve_sparse()` (BM25Okapi), `retrieve_hybrid()` (Reciprocal Rank Fusion k=60), `rerank()` (LLM-as-Reranker chọn top-k index), và `transform_query()` (expansion, decomposition, HyDE). Tôi cũng build `app.py` — Streamlit demo cho phép chọn retrieval mode, toggle reranker, và chọn query transformation từ UI.

Ở **Sprint 4**, tôi wire `generate_grading_log()` trong `eval.py` để dùng config hybrid+rerank+expansion, và fix `app.py` để đọc scorecard động từ file thay vì hardcode.

Công việc của tôi là phần lõi mà Duy (eval), Thuc (index), và Ngoc (docs) đều phụ thuộc vào — họ cần `rag_answer()` hoạt động mới chạy được scorecard và viết architecture doc.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Điều tôi hiểu sâu nhất sau lab là **sự đánh đổi giữa retrieval coverage và generation precision**.

Trước lab, tôi nghĩ hybrid (dense + sparse) luôn tốt hơn dense đơn thuần vì nó "lấy được hai cái tốt nhất". Thực tế qua eval cho thấy điều ngược lại: trên corpus 29 chunks, Context Recall baseline đã là 5.00/5 — tức là dense search không bao giờ bỏ sót source. Hybrid không cải thiện recall, nhưng lại đưa thêm chunks có keyword match cao (BM25) vào pool, và LLM reranker đôi khi chọn nhầm chunk đó. Hệ quả: Faithfulness giảm từ 4.70 xuống 4.30.

Điều này dạy tôi một nguyên tắc thực tế: **khi retrieval đã đủ tốt, bước tiếp theo cần cải thiện là generation prompt và knowledge base coverage, không phải thêm độ phức tạp cho retrieval.**

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Phần khó nhất và ngạc nhiên nhất là **LLM reranker không nhất quán với context ngắn**.

Giả thuyết ban đầu của tôi: LLM reranker (gpt-4o-mini chọn top-k index) sẽ thông minh hơn cosine distance thuần vì nó hiểu ngữ nghĩa câu hỏi. Thực tế: với câu hỏi "Ai phải phê duyệt để cấp quyền Level 3?" (q03), reranker chọn một chunk nói về Level 1/2 approval vì chunk đó có keyword "Level" và "approval" dày đặc hơn — dẫn đến generation output sai approval chain, Faithfulness = 2/5.

Bug khác: `_parse_judge_json()` trong eval.py ban đầu dùng regex `r"^```(?:json)?\\s*"` với double backslash — không match code fence thực. Tôi mất 20 phút debug trước khi nhận ra đây là string escape issue trong regex, không phải lỗi LLM output.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi được chọn:** gq07 — "Công ty sẽ phạt bao nhiêu nếu team IT vi phạm cam kết SLA P1?" (câu abstain)

**Phân tích:**

Baseline và variant đều trả lời "Tôi không biết." — đây là kết quả đúng vì thông tin này không có trong bất kỳ tài liệu nào. Theo rubric, đây là Full marks (10/10) cho câu abstain. Pipeline thực hiện đúng nhờ prompt rule: *"If the context is insufficient to answer the question, say you do not know."*

Tuy nhiên, lỗi ở chỗ **pipeline không giải thích vì sao abstain**. Câu trả lời lý tưởng phải là: "Tài liệu `sla_p1_2026.pdf` không đề cập đến mức phạt vi phạm SLA. Chính sách này có thể được quy định trong hợp đồng dịch vụ hoặc tài liệu nội bộ khác chưa được index."

Lỗi nằm ở **generation layer**: prompt không yêu cầu model nêu rõ *lý do* abstain. Fix đơn giản: thêm một dòng vào `build_grounded_prompt()` — "When abstaining, explicitly state which document was searched and confirm the information is absent." Điều này không cần re-index hay thay đổi retrieval, chỉ cần sửa prompt, nhưng sẽ cải thiện Completeness đáng kể cho các câu abstain.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

1. **Cải thiện abstain prompt**: Thêm rule "state which document was searched before saying not found." Scorecard cho thấy q07, q09, q10 đều bị giảm Completeness vì abstain không đủ rõ. Fix một dòng prompt có thể cải thiện Completeness từ 3.80 lên ~4.20.

2. **Thêm metadata chunk per document**: Mỗi file mở đầu bằng chunk tóm tắt tên tài liệu và tên cũ nếu có. Sẽ fix q07 vĩnh viễn mà không đụng retrieval logic.

---

*File: `reports/individual/pham_xuan_khang.md`*
