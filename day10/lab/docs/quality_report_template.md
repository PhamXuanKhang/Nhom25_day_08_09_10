# Quality report — Lab Day 10 (nhóm)

**run_id (baseline good):** `sprint-final`
**run_id (inject bad):** `inject-bad`
**Ngày:** 2026-04-15

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (inject-bad) | Sau (sprint-final) | Ghi chú |
|--------|--------------------|--------------------|---------|
| raw_records | 10 | 10 | Cùng file `data/raw/policy_export_dirty.csv` |
| cleaned_records | ~8 | ~7 | Sau fix refund 14→7 một số text trùng sẽ dedupe |
| quarantine_records | ~2 | ~3 | Tăng do stale HR + unknown doc_id (+ duplicate khi inject) |
| Expectation halt? | skipped (`--skip-validate`) | Không halt | `refund_no_stale_14d_window` fail ở inject-bad |

> Con số chính xác xem `artifacts/manifests/manifest_<run-id>.json` và `artifacts/logs/run_<run-id>.log`.

---

## 2. Before / after retrieval (bắt buộc)

Nguồn: `artifacts/eval/before_after_eval.csv` (sprint-final) + `artifacts/eval/after_inject_bad.csv` (inject-bad).

**Câu hỏi then chốt:** refund window (`q_refund_window`)

**Trước (inject-bad, `--no-refund-fix --skip-validate`):**
```
question_id=q_refund_window, top1_doc_id=policy_refund_v4,
contains_expected=yes, hits_forbidden=yes
```
→ Top-k chứa chunk stale “14 ngày làm việc” (row 3 CSV) — agent có thể trả sai.

**Sau (sprint-final, rule R6 + prune):**
```
question_id=q_refund_window, top1_doc_id=policy_refund_v4,
contains_expected=yes, hits_forbidden=no
```

**Merit:** versioning HR — `q_leave_version`

**Trước:** `contains_expected=no` hoặc `hits_forbidden=yes` (chunk HR 2025 “10 ngày phép năm” còn trong index khi skip validate).
**Sau:** `contains_expected=yes, hits_forbidden=no, top1_doc_expected=yes` — cutoff HR 2026-01-01 quarantine bản cũ, prune xoá vector stale.

---

## 3. Freshness & monitor

- SLA: `FRESHNESS_SLA_HOURS=24` đo **publish boundary** (`latest_exported_at` = max `exported_at` cleaned).
- CSV mẫu có `exported_at=2026-04-10T08:00:00`. Chạy ngày 2026-04-15 → `age_hours ≈ 120` → **FAIL** là kỳ vọng.
- Cách diễn giải: pipeline run chạy đúng nhưng **data snapshot cũ** → cần đẩy export mới hoặc giảm SLA cho dataset tĩnh.
- Runbook (`docs/runbook.md`) ghi rõ cách xử lý khi FAIL mà không rollback code.

---

## 4. Corruption inject (Sprint 3)

- **Cách inject:** chạy `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`. Hệ quả:
  - Rule R6 (fix refund 14→7) bị tắt → chunk 14 ngày lọt vào cleaned → expectation `refund_no_stale_14d_window` FAIL (halt) nhưng `--skip-validate` buộc embed vẫn chạy.
  - Vector stale được push vào Chroma `day10_kb`, `hits_forbidden=yes` trong eval.
- **Phát hiện:** 2 dấu hiệu độc lập:
  1. Log pipeline có `expectation[refund_no_stale_14d_window] FAIL (halt)` + `WARN: ... --skip-validate → tiếp tục embed`.
  2. `eval_retrieval.py` chạy sau đó ghi `hits_forbidden=yes` cho `q_refund_window`.
- **Khôi phục:** rerun không cờ inject (`python etl_pipeline.py run`). Pipeline prune id stale khỏi collection → eval trở lại sạch.

---

## 5. Hạn chế & việc chưa làm

- Chưa tích hợp Great Expectations thật, expectation hiện viết thuần Python (Bonus +2 bỏ ngỏ).
- Freshness chỉ đo publish boundary; chưa đo ingest boundary (file mtime raw).
- LLM-judge chưa có; eval dùng keyword match (không phát hiện sai ngữ nghĩa tinh vi).
- Rule `future_effective_date` dùng `date.today()` thay vì đọc cutoff từ contract/env (cải tiến 2h).
