# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** ___________  
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| ___ | Ingestion / Raw Owner | ___ |
| ___ | Cleaning & Quality Owner | ___ |
| ___ | Embed & Idempotency Owner | ___ |
| ___ | Monitoring / Docs Owner | ___ |

**Ngày nộp:** ___________  
**Repo:** ___________  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

_________________

**Lệnh chạy một dòng (copy từ README thực tế của nhóm):**

_________________

---

## 2. Cleaning & expectation (150–200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe…). Nhóm thêm **≥3 rule mới** + **≥2 expectation mới**. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới | Metric | Trước | Sau (sprint2-v1) | Chứng cứ |
|---|---|---|---|---|
| **R1: contains_test_markers** | quarantine_records với marker | 4 (chưa có rule) | 4 (không tìm thấy marker) | `run_sprint2-v1.log` |
| **R2: strip_trailing_whitespace** | improved dedupe accuracy | 10 raw chunks | 6 cleaned (dedupe tốt hơn) | `cleaned_sprint2-v1.csv` |
| **R3: missing_sla_keyword** | quarantine_records (SLA invalid) | 4 (baseline) | 4 (SLA chunk có keyword) | `quarantine_sprint2-v1.csv` |
| **E1: chunk_max_length_5000** | over_limit = 0 | - | 0 violations | `run_sprint2-v1.log`: `over_limit=0` |
| **E2: exported_at_consistency** | unique_timestamps | - | 1 timestamp | `run_sprint2-v1.log`: `unique_timestamps=1` |

**Run ID:** `sprint2-v1`  
**Artifacts:** `artifacts/manifests/manifest_sprint2-v1.json`, `artifacts/logs/run_sprint2-v1.log`  
**Pipeline Exit Code:** 0 ✅

**Rule chính (baseline + mở rộng):**

- **Baseline 6 rules:** allowlist doc_id, normalize effective_date, quarantine stale HR (< 2026-01-01), missing chunk_text, dedupe, fix refund window (14→7)
- **Sprint 2 — 3 rules mới:** contains_test_markers, strip_trailing_whitespace, missing_sla_keyword

**Ví dụ 1 lần expectation fail (nếu có) và cách xử lý:**

_________________

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

_________________

**Kết quả định lượng (từ CSV / bảng):**

_________________

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

_________________

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

_________________

---

## 6. Rủi ro còn lại & việc chưa làm

- …
