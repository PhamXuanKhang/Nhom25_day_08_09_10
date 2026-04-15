# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| Policy Export (DB/API) | CSV batch export daily | Stale version (HR 2025 vs 2026 chính sách) | `quarantine_records` nếu effective_date < 2026-01-01 |
| Policy Bundle (Upload) | File upload từ admin | Missing effective_date hoặc chunk_text rỗng | `missing_effective_date_count`, `empty_chunk_text_count` |
| Legacy Catalog | Sync cũ | doc_id không trong allowlist (migration lỗi) | `unknown_doc_id_count` trong quarantine |
| Policy Refund v4 | Database snapshot | Wrong policy window (14 ngày vs 7 ngày) | `refund_window_violations` expectation halt |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | … |
| doc_id | string | Có | … |
| chunk_text | string | Có | … |
| effective_date | date | Có | … |
| exported_at | datetime | Có | … |

---

## 3. Quy tắc quarantine vs drop

> Record bị flag đi đâu? Ai approve merge lại?

---

## 4. Phiên bản & canonical

> Source of truth cho policy refund: file nào / version nào?
