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

**Ví dụ: Expectation `refund_no_stale_14d_window` fail khi inject-bad:**

Log từ `run_sprint3-inject-bad.log`:
```
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1
WARN: expectation failed but --skip-validate → tiếp tục embed (chỉ dùng cho demo Sprint 3).
```

**Giải thích:** Row 2 của raw CSV chứa "14 ngày làm việc" (cũ). Khi chạy `--no-refund-fix`, rule fix không chạy → chunk text vẫn giữ "14 ngày" → expectation phát hiện 1 violation. Điều này chứng minh:
1. Expectation rule `refund_no_stale_14d_window` hoạt động
2. Khi `--skip-validate`, pipeline không halt → tiếp tục embed (để demo)
3. Retrieval sẽ phát hiện stale content qua cột `hits_forbidden`

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

Sprint 3 inject corruption nhằm chứng minh luồng xử lý refund policy.
- **Run A (inject-bad):** `python etl_pipeline.py run --run-id sprint3-inject-bad --no-refund-fix --skip-validate`
  - Không áp dụng rule fix refund 14→7 ngày
  - Expectation `refund_no_stale_14d_window` FAIL (phát hiện 1 violation)
  - Pipeline vẫn embed dữ liệu do `--skip-validate`
  
- **Run B (normal):** `python etl_pipeline.py run --run-id sprint3-normal`
  - Áp dụng rule fix refund: "14 ngày" → "7 ngày" + tag marker
  - Expectation PASS (không violation)
  - Embed dữ liệu sạch

**Kết quả định lượng (từ CSV / bảng):**

| Metric | sprint3-inject-bad | sprint3-normal | Kết luận |
|--------|---------------|-------------|----------|
| **Expectation refund_no_stale_14d_window** | FAIL (violations=1) | PASS (violations=0) | Policy enforcement hoạt động ✅ |
| **q_refund_window top1** | "7 ngày" | "7 ngày" | Cả 2 đều rank 7 ngày (semantic) |
| **q_refund_window hits_forbidden** | **yes** ❌ | **no** ✅ | Detect stale 14d ở top-k vs sạch |
| **cleaned_records** | 6 | 6 | Cùng số lượng (không loại thêm) |
| **cleaned_csv** | có marker "14 ngày" ở row 2 | có marker "[cleaned: stale_refund_window]" ở row 2 | Content khác (fix applied) |

**Chứng cứ:**
- `artifacts/logs/run_sprint3-inject-bad.log`: expectation FAIL + marker "WARN: --skip-validate"
- `artifacts/logs/run_sprint3-normal.log`: expectation PASS
- `artifacts/eval/sprint3_inject_bad.csv`: `hits_forbidden=yes` (row 1: q_refund_window)
- `artifacts/eval/sprint3_normal.csv`: `hits_forbidden=no` (row 1: q_refund_window)

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

**SLA Freshness:** Chọn `FRESHNESS_SLA_HOURS = 24` (1 ngày — thời gian xuất dữ liệu không được cũ hơn 24 giờ).

**Kết quả từ 3 run:**

| Run | latest_exported_at | age_hours | Status | Ý nghĩa |
|-----|-------------------|----------|--------|---------|
| sprint2-v1 | 2026-04-10T08:00:00 | 120.87 | **FAIL** | Data exported 5 ngày trước → exceed SLA 24h |
| sprint3-inject-bad | 2026-04-10T08:00:00 | 121.30 | **FAIL** | Cùng dữ liệu → exceed SLA |
| sprint3-normal | 2026-04-10T08:00:00 | 121.61 | **FAIL** | Cùng dữ liệu → exceed SLA |

**Giải thích FAIL:**
- Mẫu CSV (`policy_export_dirty.csv`) có exported_at = 2026-04-10 (5 ngày trước ngày chạy 2026-04-15)
- Exceed SLA 24h → cảnh báo "Data stale, need re-export"
- Trong production, chạy pipeline lại với raw file mới sẽ reset freshness timer

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

**Tích hợp Day 09:**

Dữ liệu sau clean + embed được lưu vào Chroma DB collection `day10_kb` (tách riêng từ Day 09). Collection này phục vụ:
1. **Retrieval trong lab Day 10:** Eval 4 test questions (q_refund_window, q_p1_sla, q_lockout, q_leave_version)
2. **Có thể dùng lại Day 09:** Nếu agent Day 09 cần update knowledge base mới, có thể:
   - Chỉ định `CHROMA_COLLECTION=day09_kb` trong `.env`
   - Hoặc merge dữ liệu từ `day10_kb` sang `day09_kb` bằng Chroma API

**Lý do tách collection:** Day 10 là pipeline mới với dữ liệu "policy_export_dirty" — cần kiểm soát quality riêng + eval riêng trước khi merge vào production Day 09 collection.

---

## 6. Rủi ro còn lại & việc chưa làm

- **SLA Freshness FAIL:** CSV mẫu đã cũ 5 ngày → production cần setup auto-export hoặc schedule re-ingest
- **Rules tác động nhỏ:** R1 (test_markers) không tìm thấy `[TEST]` trong data → chưa chứng minh catch lỗi, cần inject test data bổ sung
- **Expectation threshold:** Hiện tại tuỳ ý pick ngưỡng (chunk_max_length_5000) → cần review lại trên production data
- **Vector DB stability:** Chroma DB chạy local (file-based) — cần evaluate scaling + backup strategy nếu production
- **TODO Sprint 4:** Điền docs/pipeline_architecture.md, docs/runbook.md, peer review 3 questions (slide Phần E)
