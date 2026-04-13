# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Phạm Thành Duy
**Vai trò trong nhóm:** Eval Owner
**Ngày nộp:** 2026-04-13
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Với vai trò Eval Owner, tôi chịu trách nhiệm chính ở Sprint 4 — toàn bộ evaluation framework trong `eval.py` và việc chạy scorecard.

**Commit `585810c`** là đóng góp lớn nhất: implement 4 hàm scoring (305 dòng code mới) —  `score_faithfulness()`, `score_answer_relevance()`, `score_context_recall()`, `score_completeness()`. Cả bốn dùng LLM-as-Judge (gpt-4o-mini, temperature=0) thay vì chấm thủ công. Tôi thiết kế từng prompt để judge chấm theo thang 1–5 và trả về JSON `{"score": int, "reason": string}`. Tôi cũng generate `scorecard_baseline.md` và `scorecard_variant.md` lần đầu tiên cho nhóm.

**Commit `10a0b6f`**: Thêm `_rag_collection_exists()` để kiểm tra ChromaDB trước khi chạy eval (tránh crash khi chưa index), và cập nhật scorecard với metrics từ lần chạy mới nhất.

**Commit `2f1af75`**: Cập nhật `ab_comparison.csv` với đầy đủ per-question scores cho cả baseline và variant.

Tôi cũng merge PR #2 (Duypt branch) vào main sau khi confirm không conflict với code của Khang.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Điều tôi hiểu sâu nhất là **LLM-as-Judge không phải ground truth — nó cần reference answer tốt**.

Ban đầu tôi nghĩ chỉ cần cho LLM judge đọc model answer và retrieved context là đủ. Khi chạy thực tế, judge dễ bị "anchored" bởi từ ngữ: nếu answer dùng từ chính xác từ context, judge cho 5; nếu paraphrase đúng nghĩa nhưng dùng từ khác, judge có thể cho 4.

Điều này gây bias: pipeline bị penalize vì diễn đạt tốt hơn, không phải vì sai. Giải pháp là cung cấp `expected_answer` cho judge làm calibration. Tôi đã implement trong `score_answer_relevance()` và `score_completeness()`, nhưng `score_faithfulness()` không dùng expected_answer — thiếu sót này tôi nhận ra sau khi chạy.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Khó khăn lớn nhất là **parse JSON output từ LLM judge một cách robust**.

Khi tôi gửi prompt yêu cầu `{"score": int, "reason": string}`, LLM đôi khi trả về:
- JSON bọc trong code fence: ` ```json\n{...}\n``` `
- JSON có trailing comma: `{"score": 4, "reason": "...",}`
- Chỉ trả về số: `4` (không có JSON)
- Text explanation trước JSON: `"Based on the context, I rate this 4/5. {"score": 4, ...}`

Tôi viết `_parse_judge_json()` dùng regex để strip code fence trước, rồi `re.search(r"\{[\s\S]*\}")` để extract JSON object từ bất kỳ vị trí nào trong response. Tuy nhiên, regex ban đầu có bug: `r"^```(?:json)?\\s*"` dùng double backslash nên không match. Phải sửa thành single backslash mới hoạt động.

Điều này ngạc nhiên tôi: **robustness của LLM output parsing khó hơn nhiều so với việc design prompt**, và failure mode rất khó debug vì LLM cho output hợp lệ nhưng format không nhất quán.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi được chọn:** q09 — "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Phân tích:**

Đây là câu hỏi "Insufficient Context" — thông tin về ERR-403-AUTH không tồn tại trong bất kỳ tài liệu nào. Pipeline lý tưởng phải abstain hoàn toàn.

**Baseline** (Context Recall = None, Faithfulness = 5, Completeness = 2): Pipeline trả lời "ERR-403-AUTH là lỗi liên quan đến quyền truy cập, thường xảy ra khi người dùng không có quyền..." — hoàn toàn suy luận từ tên lỗi, không từ doc nào. Faithfulness = 5 vì LLM judge đánh giá answer bám context (access control context), nhưng Completeness = 2 vì expected answer là abstain.

**Lỗi nằm ở generation layer**: retrieval đúng (không có source nào có ERR-403-AUTH, nên Context Recall = None/không áp dụng). Nhưng prompt hiện tại nói "if context is insufficient, say you do not know" — LLM tìm thấy context *liên quan* (access control, 403 = forbidden) và tự suy luận thay vì abstain.

**Fix**: Thêm explicit rule vào prompt: "If the exact term or error code from the question does not appear verbatim in the context, treat it as insufficient and abstain." Điều này sẽ ngăn model suy luận từ partial match.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

1. **Calibration set cho LLM judge**: Tạo 5–10 câu chấm tay làm few-shot examples. Scorecard cho thấy variant q03 bị judge cho Faithfulness=2/5 dù answer đúng về nội dung — calibration sẽ giảm false negatives này.

2. **Confidence interval cho metrics**: Chạy judge 3 lần per câu và tính std deviation. Hiện tại mỗi câu chạy một lần — không rõ 4.30 vs 4.70 có ý nghĩa thống kê không trước khi kết luận A/B.

---

*File: `reports/individual/pham_thanh_duy.md`*
