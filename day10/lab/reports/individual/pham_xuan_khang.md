# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Phạm Xuân Khang
**Vai trò:** Ingestion / Raw Owner
**Ngày nộp:** 2026-04-15
**run_id chính:** `sprint-final` · **run_id inject:** `inject-bad`

---

## 1. Tôi phụ trách phần nào?

**File / module chính:**

- `etl_pipeline.py` — entrypoint `cmd_run`, `cmd_freshness`, thiết kế `run_id`, log, manifest.
- `data/raw/policy_export_dirty.csv` — raw mẫu + 1 dòng dd/mm/yyyy tôi giữ lại để test parser.
- `data/test_questions.json`, `data/grading_questions.json` — tôi chuẩn hoá schema câu hỏi golden (key `expect_top1_doc_id`, `must_not_contain`).
- `instructor_quick_check.py` — tôi check format JSONL + manifest trước khi commit.

**Kết nối với thành viên khác:** tôi sinh `run_id` và truyền xuống Cleaning Owner (log + cleaned_csv), Embed Owner (metadata Chroma), Monitoring Owner (manifest `latest_exported_at`).

**Bằng chứng:** commit trên branch main, dòng `etl_pipeline.py:50 run_id = args.run_id or datetime.now(...)`; manifest `artifacts/manifests/manifest_sprint-final.json` có `run_id=sprint-final`.

---

## 2. Một quyết định kỹ thuật

Tôi quyết định đo **freshness tại publish boundary** thay vì ingest boundary. Lý do: SLA quan trọng với agent Day 09 là “dữ liệu đang phục vụ trong Chroma có stale không”, chứ không phải “file raw đã drop vào S3 bao lâu”. Nếu đo ingest, một clean fail lâu ngày sẽ vẫn báo PASS (vì raw mới). Đo publish: `latest_exported_at = max exported_at cleaned` khớp với dữ liệu thực sự lên vector. Trade-off: khi dataset tĩnh (CSV mẫu có `exported_at=2026-04-10`), báo FAIL là kỳ vọng — tôi ghi lại trong runbook mục Prevention để tránh alert fatigue.

---

## 3. Một lỗi / anomaly đã xử lý

**Symptom:** run đầu tiên có `embed_prune_removed=0` nhưng `q_refund_window` báo `hits_forbidden=yes` dù chạy pipeline chuẩn. **Detection:** tôi mở `artifacts/eval/before_after_eval.csv` sau mỗi run. **Diagnosis:** Chroma collection còn vector từ test `inject-bad` trước đó. **Fix:** rerun `python etl_pipeline.py run --run-id sprint-final` — logic `col.get(include=[])` trong `cmd_embed_internal` sau đó prune `embed_prune_removed=1` (chính xác id 14-ngày stale). Evidence: log `artifacts/logs/run_sprint-final.log` dòng `embed_prune_removed=1`. Từ đó tôi khẳng định: **prune là phần không thể bỏ** nếu ta muốn collection là snapshot publish thực.

---

## 4. Bằng chứng trước / sau

Từ `artifacts/eval/after_inject_bad.csv` (run_id=inject-bad):
```
q_refund_window,policy_refund_v4,"...7 ngày...",yes,yes,,3
```

Từ `artifacts/eval/before_after_eval.csv` (run_id=sprint-final):
```
q_refund_window,policy_refund_v4,"...7 ngày...",yes,no,,3
q_leave_version,hr_leave_policy,"...12 ngày phép năm theo chính sách 2026.",yes,no,yes,3
```

Delta: `hits_forbidden` chuyển từ `yes → no`; `top1_doc_expected=yes` cho câu HR versioning (Merit).

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ: chuyển cutoff HR (`2026-01-01`) và `FUTURE_DATE_SLACK_DAYS` sang đọc từ `contracts/data_contract.yaml` (đã có key `policy_versioning.hr_leave_min_effective_date`) thay vì hard-code trong `cleaning_rules.py`. Giúp đạt tiêu chí Distinction (d) và tái sản xuất được trong CI khi `today` không cố định.
