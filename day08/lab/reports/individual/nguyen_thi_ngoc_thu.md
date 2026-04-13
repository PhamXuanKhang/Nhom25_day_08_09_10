# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Thị Ngọc Thu  
**Vai trò trong nhóm:** Documentation Owner  
**Ngày nộp:** 13/04/2026  

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong vai trò Documentation Owner, tôi chịu trách nhiệm chính trong Sprint 4 — giai đoạn hoàn thiện toàn bộ pipeline RAG. Cụ thể, tôi đã:

1. **Viết tài liệu kiến trúc pipeline** (`docs/architecture.md`): Mô tả cấu trúc end-to-end từ indexing → retrieval → generation → evaluation. Ghi lại các quyết định thiết kế: lựa chọn embedding model, strategy chunking với metadata (source, section, effective_date), và lý do chọn variant retrieval.

2. **Ghi lại tuning log** (`docs/tuning-log.md`): Tổng hợp kết quả A/B comparison giữa baseline (dense retrieval) và variant. Phân tích delta trong F1-score, context recall, và faithfulness giữa hai approach, kèm giải thích tại sao variant hiệu quả hơn.

3. **Điều phối sprint 4 để hoàn chỉnh**: Đảm bảo Eval Owner hoàn thành scorecard cho baseline/variant, Tech Lead verify end-to-end pipeline chạy được, và tất cả thành viên hoàn thành báo cáo cá nhân.

4. **Tổng hợp và trình bày kết quả**: Viết báo cáo nhóm tóm tắt những gì đạt được, những thử thách, và insight rút ra từ RAG pipeline này.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab, tôi hiểu rõ hơn về **evaluation loop trong RAG systems**. Ban đầu tôi nghĩ chỉ cần kiểm tra xem LLM trả lời "giống" expected answer là đủ. Nhưng qua lab, tôi thấy cần evaluate theo 3 khía cạnh riêng biệt:

- **Context Recall**: Dữ liệu cần lấy có được retrieve không? (Lỗi indexing/retrieval)
- **Faithfulness**: Answer có bám context không? (Lỗi generation/hallucination)
- **Answer Relevance**: Câu trả lời có trả lời đúng câu hỏi không? (Lỗi understanding)

Điều này giúp tôi pinpoint vấn đề chính xác: nếu retrieval tốt nhưng answer sai, là do LLM hallucinate, chứ không phải do data không đủ. Việc tách rời này rất quan trọng trong debug RAG pipeline và lựa chọn improvement strategy (chọn tuning retrieval vs. tuning prompt/model).

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

**Ngạc nhiên nhất**: Là một câu hỏi đơn giản "SLA ticket P1 là bao lâu?" nhưng baseline trả lời **sai điểm** chỉ vì metadata chunking không tốt. Chunk bị cắt ở giữa bảng SLA, làm mất dữ liệu quan trọng. Sau khi tối ưu lại chunking strategy (tăng chunk size, preserve table boundaries), câu hỏi này được trả lời 100% đúng. Điều này cho thấy **indexing quality** quyết định trực tiếp success của cả pipeline.

**Khó khăn**: Khi so sánh baseline vs variant (hybrid retrieval), tôi phải quyết định ngưỡng nào để cân bằng dense vs sparse results. Ban đầu cân nặng dense quá cao, hybrid không cải thiện. Sau khi tune lại weights (60-40), hybrid tìm thêm được những keyword queries mà dense miss. Việc này consuming time nhưng dạy tôi rằng tuning RAG không phải "set and forget" mà cần empirical testing.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?"

**Baseline kết quả**:   
Baseline trả lời: "Khách hàng có quyền yêu cầu hoàn tiền trong vòng 30 ngày kể từ mua hàng" — nhưng expected answer từ `policy_refund_v4.txt` là "45 ngày".

**Root cause analysis**:
1. **Retrieval không lỗi**: Chunk từ refund policy được retrieve đúng với high score
2. **Lỗi nằm ở Generation**: LLM hallucinate số "30" thay vì "45" từ context (faithfulness score = 0.3)
3. **Giả thuyết**: Prompt không đủ "grounding" — LLM dùng world knowledge mặc định thay vì strictly follow context

**Variant (Rerank)**:  
Khi thêm reranker (cross-encoder), chunk refund policy được rank cao hơn, làm cho LLM context window limpid không bị noise từ docs khác. Prompt clarity cũng tăng, trả lời text-to-text "45 ngày".

**Kết luận**: Câu hỏi này chứng tỏ **retrieval không phải always bottleneck** — generation quality (grounding + rerank) cũng critical. Variant rerank improve từ 50% → 100% accuracy cho question này.

---

## Tóm tắt

Qua Sprint 4, tôi không chỉ hoàn thành tài liệu như assigned mà còn học được cách systematic debug RAG, cách evaluate đa chiều, và cách tuning là iterative process. Documentation Owner không chỉ "ghi lại kết quả" mà phải **hiểu sâu pipeline để giải thích tại sao những chọn lựa đó lại đúng**.
