# Runbook — Lab Day 10 (incident tối giản)

## Symptom

- User hoặc agent Day 08/09 trả lời “14 ngày làm việc” cho câu hỏi refund, hoặc “10 ngày phép năm” cho câu hỏi HR 2026.
- Eval `artifacts/eval/before_after_eval.csv` có `contains_expected=no` hoặc `hits_forbidden=yes` cho `q_refund_window` / `q_leave_version`.

---

## Detection

| Metric | Vị trí | Ngưỡng báo |
|--------|--------|------------|
| `freshness_check` | log pipeline / `freshness` command | `FAIL` nếu `age_hours > FRESHNESS_SLA_HOURS` |
| `expectation[refund_no_stale_14d_window] FAIL` | log `run_*.log` | Bất kỳ violation > 0 → halt |
| `expectation[hr_leave_no_stale_10d_annual] FAIL` | log | Bất kỳ violation > 0 → halt |
| `hits_forbidden=yes` | `artifacts/eval/*.csv` | Có mặt trong bất kỳ câu retrieval golden |
| `quarantine_records` | manifest | Tăng đột biến so với baseline (>3) |

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Mở `artifacts/manifests/manifest_<run-id>.json` | Xác nhận `run_id`, `cleaned_records`, `quarantine_records`, `no_refund_fix` cờ đúng |
| 2 | Mở `artifacts/quarantine/*.csv` | Tìm dòng `reason=stale_hr_policy_effective_date` hoặc `duplicate_chunk_text` tăng bất thường |
| 3 | Chạy `python eval_retrieval.py` | Xác nhận câu nào fail + top-k chunk nào còn stale |
| 4 | Kiểm `log run_<run-id>.log` | Tìm dòng `expectation[...] FAIL` hoặc `embed_prune_removed=0` (nghi prune không chạy) |
| 5 | So `contracts/data_contract.yaml` với thực tế | `allowed_doc_ids` đồng bộ với `transform/cleaning_rules.py::ALLOWED_DOC_IDS` |

---

## Mitigation

1. **Rerun chuẩn**: `python etl_pipeline.py run --run-id fix-<ticket>` (không `--skip-validate`, không `--no-refund-fix`). Upsert + prune sẽ đẩy stale id ra khỏi collection.
2. **Rollback embed**: nếu run mới cũng lỗi, dùng Chroma client để `delete_collection("day10_kb")` rồi chạy lại từ cleaned CSV trước đó đã PASS (manifest lưu `cleaned_csv`).
3. **Tạm banner**: Day 09 agent hiển thị “Policy data đang refresh” bằng cách check env `DATA_STALE=true` (thêm ở integration sau).
4. **Hotfix dữ liệu**: sửa `data/raw/policy_export_dirty.csv` (loại bỏ dòng stale) rồi commit + rerun.

---

## Prevention

- Giữ expectation `refund_no_stale_14d_window`, `hr_leave_no_stale_10d_annual` ở severity **halt** — không hạ warn.
- Thêm alert freshness sang `#data-obs-day10` khi `age_hours > sla_hours * 0.8` (warn) — Day 11 guardrail.
- Đưa cutoff HR vào `contracts/data_contract.yaml` (đã có `policy_versioning.hr_leave_min_effective_date`) để tránh hard-code (Distinction criterion d).
- Monitoring Owner chạy `instructor_quick_check.py --manifest ...` trước mỗi PR đổi data/pipeline.
- Document SLA trong section Detection: hiện **SLA áp cho pipeline run** (so giữa `now` và `latest_exported_at`). CSV mẫu có timestamp 2026-04-10 nên FAIL là hợp lý khi demo sau ngày đó — giữ để minh hoạ debug.
