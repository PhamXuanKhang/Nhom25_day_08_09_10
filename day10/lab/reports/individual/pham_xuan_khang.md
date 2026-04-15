# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Phạm Xuân Khang
**Vai trò:** Ingestion / Raw Owner
**Ngày nộp:** 2026-04-15
**run_id chính:** `sprint-final` · **run_id inject:** `inject-bad`

---

## 1. Tôi phụ trách phần nào?

**File / module chính:**

- `etl_pipeline.py` — entrypoint `cmd_run`, `cmd_freshness`, `cmd_embed_internal`: thiết kế `run_id`, điều phối toàn bộ luồng ingest → clean → validate → embed → manifest.
- `data/raw/policy_export_dirty.csv` — raw mẫu 10 dòng: tôi giữ lại 1 dòng dmy-format (`01/02/2026`) và 1 dòng "14 ngày làm việc" để test parser và rule R6.
- `data/test_questions.json`, `data/grading_questions.json` — tôi chuẩn hoá schema câu hỏi golden (key `expect_top1_doc_id`, `must_not_contain`), viết 3 câu `gq_d10_01..03`.
- `instructor_quick_check.py` — tôi check format JSONL + manifest trước khi commit.

**Kết nối với thành viên khác:** tôi sinh `run_id` và truyền xuống Cleaning Owner (đường dẫn log + cleaned_csv), Embed Owner (metadata Chroma `run_id` field), Monitoring Owner (trường `latest_exported_at` trong manifest để check freshness SLA).

**Bằng chứng:** `etl_pipeline.py:50` dòng `run_id = args.run_id or datetime.now(...)`; manifest `artifacts/manifests/manifest_sprint-final.json` có `"run_id": "sprint-final"`, `"raw_records": 10`, `"cleaned_records": 6`.

---

## 2. Một quyết định kỹ thuật

Tôi quyết định đo **freshness tại publish boundary** thay vì ingest boundary. Lý do: SLA quan trọng với agent Day 09 là "dữ liệu đang phục vụ trong Chroma có stale không", chứ không phải "file raw đã drop vào S3 bao lâu". Nếu đo ingest, một pipeline có clean fail kéo dài sẽ vẫn báo PASS (vì raw mới) dù vector store không được cập nhật. Đo publish: `latest_exported_at = max(exported_at của cleaned rows)` khớp với dữ liệu thực sự đã lên vector.

Trade-off: khi dataset tĩnh (CSV mẫu có `exported_at=2026-04-10`), chạy ngày 2026-04-15 → `age_hours≈122` → **FAIL** dù pipeline chạy hoàn toàn đúng. Tôi ghi lại điều này trong runbook mục Prevention và SCORING FAQ để tránh nhầm lẫn khi chấm.

---

## 3. Một lỗi / anomaly đã xử lý

**Symptom:** sau khi chạy inject-bad rồi chạy lại sprint-final, `instructor_quick_check.py` vẫn báo `MERIT_CHECK[gq_d10_01] FAIL` với `hits_forbidden=true` dù pipeline sprint-final exit 0 và expectation E3 OK.

**Detection:** mở `artifacts/eval/grading_run.jsonl` — dòng `gq_d10_01` có `"hits_forbidden": true`, trong khi log sprint-final ghi `refund_no_stale_14d_window OK`.

**Diagnosis:** grading_run.jsonl được tạo **trước khi** rerun sprint-final prune vector cũ — file JSONL vẫn phản ánh Chroma còn vector "14 ngày" từ inject-bad. `embed_prune_removed=1` xuất hiện trong log sprint-final xác nhận prune chạy đúng, nhưng grading_run.py chưa được chạy lại sau đó.

**Fix:** chạy lại `py -3.12 grading_run.py --out artifacts/eval/grading_run.jsonl` sau khi sprint-final hoàn tất → tất cả 3 MERIT_CHECK OK.

**Bài học:** luôn regenerate grading JSONL **sau** run sạch cuối cùng, không dùng JSONL cũ từ trước inject.

---

## 4. Bằng chứng trước / sau

Từ `artifacts/eval/after_inject_bad.csv` (run_id=inject-bad, `--no-refund-fix`):
```
q_refund_window,policy_refund_v4,...,yes,yes,,3
```

Từ `artifacts/eval/before_after_eval.csv` (run_id=sprint-final, pipeline chuẩn):
```
q_refund_window,policy_refund_v4,...,yes,no,,3
q_leave_version,hr_leave_policy,...,yes,no,yes,3
```

Delta: `hits_forbidden` của `q_refund_window` chuyển từ `yes → no` sau khi rule R6 + prune hoạt động đúng. `q_leave_version` đạt Merit condition: `contains_expected=yes, hits_forbidden=no, top1_doc_expected=yes`.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ: chuyển cutoff HR (`2026-01-01`) và `FUTURE_DATE_SLACK_DAYS` sang đọc từ `contracts/data_contract.yaml` (đã có key `policy_versioning.hr_leave_min_effective_date`) thay vì hard-code trong `cleaning_rules.py`. Khi đó rule R3 và R8 không phụ thuộc `date.today()` cố định, CI có thể rerun đúng kết quả ở bất kỳ ngày nào — đạt tiêu chí Distinction (d).
