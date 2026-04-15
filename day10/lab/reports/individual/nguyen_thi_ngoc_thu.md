# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Thị Ngọc Thư
**Vai trò:** Monitoring / Docs Owner
**Ngày nộp:** 2026-04-15
**run_id chính:** `sprint-final` · **run_id inject:** `inject-bad`

---

## 1. Tôi phụ trách phần nào?

**File / module chính:**

- `monitoring/freshness_check.py` — tôi implement `check_manifest_freshness()`: đọc `latest_exported_at` từ manifest, tính `age_hours = (now - dt).total_seconds() / 3600`, so với `sla_hours`, trả về `PASS/WARN/FAIL` + detail dict.
- `docs/pipeline_architecture.md` — sơ đồ Mermaid, bảng ranh giới trách nhiệm, idempotency note, rủi ro đã biết.
- `docs/data_contract.md` — source map 3 nguồn, schema cleaned, quy tắc quarantine vs drop, phiên bản canonical.
- `docs/runbook.md` — Symptom → Detection → Diagnosis → Mitigation → Prevention.
- `docs/quality_report_template.md` — điền số liệu thực từ run sprint-final và inject-bad.
- `reports/group_report.md` — tôi tổng hợp metric_impact từ Cleaning Owner và Embed Owner, viết toàn bộ nội dung nhóm.
- `note.md` — bảng file↔role, checklist commit từng role.

**Kết nối với thành viên khác:** tôi nhận số liệu `quarantine_records`, `expectation FAIL/OK` từ Cleaning Owner và `hits_forbidden` từ Embed Owner để điền bảng `metric_impact`. Tôi đọc manifest (Ingestion Owner sinh) để minh họa freshness FAIL trong runbook.

**Bằng chứng:** `monitoring/freshness_check.py` function `parse_iso()` + `check_manifest_freshness()`; `docs/runbook.md` có 5 mục đúng thứ tự Symptom→Prevention.

---

## 2. Một quyết định kỹ thuật

Tôi thiết kế `freshness_check` chỉ trả ba trạng thái — `PASS`, `WARN`, `FAIL` — thay vì trả số liệu thô. Lý do: downstream consumer (pipeline log, agent Day 09) cần một tín hiệu rõ ràng, không cần parse số. `WARN` dành riêng cho trường hợp thiếu timestamp (manifest không có `latest_exported_at`) — để phân biệt "không biết freshness" vs "biết và stale".

Trade-off: mất granularity — không biết FAIL cách SLA bao nhiêu giờ nếu chỉ nhìn status. Tôi giải quyết bằng cách trả kèm `detail dict` (`age_hours`, `sla_hours`, `reason`) để caller có thể log đầy đủ khi cần — xem `etl_pipeline.py:125` dòng `log(f"freshness_check={status} {json.dumps(fdetail)}")`.

---

## 3. Một lỗi / anomaly đã xử lý

**Symptom:** khi viết runbook, tôi chạy `python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_sprint-final.json` và nhận `FAIL` — ban đầu tưởng pipeline bị lỗi.

**Detection:** đọc detail: `{"latest_exported_at": "2026-04-10T08:00:00", "age_hours": 122.7, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}`.

**Diagnosis:** FAIL hoàn toàn đúng vì CSV mẫu có timestamp cố định `2026-04-10`, chạy ngày `2026-04-15` → cách nhau 122 giờ, SLA là 24 giờ. Pipeline chạy đúng, data snapshot mới là vấn đề. Đây không phải bug code mà là trạng thái hợp lệ cần giải thích trong tài liệu.

**Fix:** tôi bổ sung mục Prevention trong runbook: *"CSV mẫu có timestamp 2026-04-10 nên FAIL là hợp lý khi demo sau ngày đó — giữ để minh hoạ debug. Trong production: đẩy export mới hoặc nới `FRESHNESS_SLA_HOURS` cho dataset tĩnh."* Đồng thời thêm câu hỏi FAQ này vào `SCORING.md`.

---

## 4. Bằng chứng trước / sau

Từ log `artifacts/logs/run_sprint-final.log` (pipeline chuẩn):
```
freshness_check=FAIL {"latest_exported_at": "2026-04-10T08:00:00",
  "age_hours": 122.711, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
PIPELINE_OK
```

Từ log `artifacts/logs/run_inject-bad.log` (inject demo):
```
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1
WARN: expectation failed but --skip-validate → tiếp tục embed
freshness_check=FAIL {"age_hours": 122.72, ...}
PIPELINE_OK
```

Delta quan sát: `freshness_check=FAIL` nhất quán ở cả hai run (vì timestamp CSV không đổi), nhưng expectation E3 phân biệt rõ run inject vs run sạch. Monitoring Owner dùng **cả hai tín hiệu** — freshness + expectation log — để chẩn đoán đúng trạng thái pipeline.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ: đo freshness ở **2 boundary** — thêm `ingest_boundary` (mtime của `data/raw/policy_export_dirty.csv` lúc load) vào manifest bên cạnh `latest_exported_at` (publish boundary). Log hai giá trị `age_hours_ingest` và `age_hours_publish` → Monitoring Owner có thể phân biệt "raw mới nhưng clean chưa chạy" vs "clean chạy rồi nhưng data cũ" — đạt Bonus (+1) freshness 2 boundary.
