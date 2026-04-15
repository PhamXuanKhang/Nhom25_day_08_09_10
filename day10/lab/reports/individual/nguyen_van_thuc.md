# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Văn Thức
**Vai trò:** Embed & Idempotency Owner
**Ngày nộp:** 2026-04-15
**run_id chính:** `sprint-final` · **run_id inject:** `inject-bad`

---

## 1. Tôi phụ trách phần nào?

**File / module chính:**

- `eval_retrieval.py` — tôi thiết kế luồng eval: query Chroma với 4 câu test, so sánh `must_contain_any` / `must_not_contain`, ghi CSV với cột `contains_expected`, `hits_forbidden`, `top1_doc_expected`. File `artifacts/eval/before_after_eval.csv` và `after_inject_bad.csv` đều do script này sinh.
- `contracts/data_contract.yaml` — tôi điền `owner_team`, `owner_primary`, `owner_escalation`, `alert_channel`, và xác nhận `allowed_doc_ids` khớp với `ALLOWED_DOC_IDS` trong `cleaning_rules.py`.
- `artifacts/eval/before_after_eval.csv`, `after_inject_bad.csv`, `grading_run.jsonl` — artifact eval thuộc sub-folder của tôi.

**Kết nối với thành viên khác:** tôi nhận `cleaned_csv` path từ manifest (Ingestion Owner) để biết run nào cần eval. Kết quả `hits_forbidden` tôi gửi cho Monitoring Owner để điền bảng `metric_impact` trong group_report.

**Bằng chứng:** `eval_retrieval.py` function `main()` đọc `test_questions.json`, query Chroma collection `day10_kb`; `contracts/data_contract.yaml` có comment `owner_primary: "Cleaning & Quality Owner"` và `alert_channel`.

---

## 2. Một quyết định kỹ thuật

Tôi quyết định kiểm tra `hits_forbidden` trên **toàn bộ top-k chunk ghép lại** (`blob = " ".join(docs).lower()`) thay vì chỉ top-1. Lý do: grading bắt "context bẩn" — nếu chunk stale "14 ngày làm việc" nằm ở vị trí 2 hoặc 3, agent vẫn nhìn thấy nó trong context window và có thể trả sai. Chỉ check top-1 sẽ cho false PASS trong trường hợp này.

Trade-off: tiêu chí nghiêm hơn → khó đạt `hits_forbidden=false` hơn. Nhưng đây đúng là tinh thần của observability: phát hiện "câu trả lời nhìn đúng nhưng context vẫn còn chunk stale" — khớp với chú thích trong `README.md` mục "Ghi chú chấm điểm".

---

## 3. Một lỗi / anomaly đã xử lý

**Symptom:** lần đầu chạy `eval_retrieval.py` sau run sprint-final, `q_refund_window` báo `hits_forbidden=yes` dù log pipeline ghi `refund_no_stale_14d_window OK`.

**Detection:** tôi mở `artifacts/eval/before_after_eval.csv` và thấy `hits_forbidden=yes`. Log pipeline có `embed_prune_removed=0` — dấu hiệu không có gì bị prune.

**Diagnosis:** collection `day10_kb` còn vector từ test chạy tay trước đó (không có run_id chuẩn). Các vector đó có chunk_id khác với sprint-final nên không bị upsert overwrite, cũng không bị prune vì `prev_ids - ids = {}` (chưa chạy inject trước đó).

**Fix:** xóa collection và rerun: `python etl_pipeline.py run --run-id sprint-final`. Lần này `embed_prune_removed=1` (stale id bị xóa) → eval lại → `hits_forbidden=no`. Từ đó tôi hiểu: **prune chỉ xóa id trong prev_ids mà không có trong cleaned batch hiện tại** — nên nếu collection chứa id hoàn toàn khác (từ run test cũ), vẫn cần rerun để prune phát hiện.

---

## 4. Bằng chứng trước / sau

Từ `artifacts/eval/after_inject_bad.csv` (run_id=inject-bad):
```
q_refund_window,policy_refund_v4,...,yes,yes,,3
```
→ top-k chứa "14 ngày làm việc" — `hits_forbidden=yes`.

Từ `artifacts/eval/before_after_eval.csv` (run_id=sprint-final):
```
q_refund_window,policy_refund_v4,...,yes,no,,3
q_leave_version,hr_leave_policy,...,yes,no,yes,3
```
→ `hits_forbidden=no` cho cả 2 câu. `q_leave_version` đạt Merit: `contains_expected=yes, hits_forbidden=no, top1_doc_expected=yes`.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ: thêm **LLM-judge** vào `eval_retrieval.py` — thay vì chỉ so keyword, gọi Claude API với prompt "Does this context answer the question correctly? Does it contain outdated information?" → nhận `pass/fail` có giải thích. Keyword match không bắt được lỗi ngữ nghĩa tinh vi (vd chunk nói "7 ngày" nhưng trong ngữ cảnh khác). Đây là hướng đạt Distinction (c).
