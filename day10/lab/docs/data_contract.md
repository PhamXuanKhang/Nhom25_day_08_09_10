# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — file này mở rộng chú thích, đồng bộ owner + failure modes.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|--------------------|--------------------|----------------|
| `data/raw/policy_export_dirty.csv` (mô phỏng export DB CS + HR) | Batch CSV pull hằng ngày 08:00 ICT, drop vào `data/raw/` | Duplicate dòng, thiếu `effective_date`, format ngày `dd/mm/yyyy`, policy-v3 lẫn v4 | `raw_records`, `quarantine_records` trong log/manifest; alert nếu `quarantine_records > 3` |
| `data/docs/*.txt` (canonical 4 doc) | Commit thẳng repo, đọc lại khi rewrite chunk | Chunk ngữ cảnh cũ còn sót (HR 2025) | Expectation `hr_leave_no_stale_10d_annual` |
| Chroma collection `day10_kb` (publish đích) | Upsert sau clean + validate | Vector stale không được prune → context bẩn | `embed_prune_removed` log; `hits_forbidden` eval |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | `doc_id_seq_sha256[:16]` — ổn định qua rerun khi nội dung không đổi |
| doc_id | string | Có | Phải thuộc `allowed_doc_ids` trong contract |
| chunk_text | string | Có | Đã strip BOM/zero-width; length ≥ 8 (warn), ≤ 2000 (quarantine) |
| effective_date | date | Có | ISO `YYYY-MM-DD`; không được > today+2y |
| exported_at | datetime | Có | Dùng để tính `latest_exported_at` → freshness |

---

## 3. Quy tắc quarantine vs drop

- **Quarantine** (ghi `artifacts/quarantine/*.csv`, giữ record để điều tra): unknown doc_id, missing/invalid effective_date, stale HR (<2026-01-01), future date, chunk rỗng, chunk quá dài, duplicate text.
- **Drop** thật sự: hiện tại không có. Tất cả record “xấu” đều quarantine để Cleaning Owner review.
- **Approve merge**: Cleaning Owner mở quarantine CSV, sửa record sai (vd format ngày) và re-ingest ở run sau (thêm dòng vào `data/raw/`). Monitoring Owner xác nhận ở manifest tiếp theo.

---

## 4. Phiên bản & canonical

- Refund: **`data/docs/policy_refund_v4.txt`** là source-of-truth (7 ngày làm việc). Rule R6 tự fix “14 ngày làm việc” trong CSV về 7 ngày — có annotation `[cleaned: stale_refund_window]`.
- HR leave: cutoff **`2026-01-01`** (định nghĩa ở `contracts/data_contract.yaml` > `policy_versioning.hr_leave_min_effective_date`). Rule 3 quarantine mọi chunk HR effective_date < cutoff.
- SLA P1 (`sla_p1_2026.txt`): không có conflict version hiện tại.
- Helpdesk FAQ: chấp nhận cả `YYYY-MM-DD` và `dd/mm/yyyy` ở raw (parser quy chuẩn về ISO).
