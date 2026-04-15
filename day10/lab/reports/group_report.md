# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** 25
**Thành viên:**

| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Phạm Xuân Khang | Ingestion / Raw Owner |
| Phạm Thành Duy | Cleaning & Quality Owner |
| Nguyễn Văn Thức | Embed & Idempotency Owner | 
| Nguyễn Thị Ngọc Thư | Monitoring / Docs Owner | 

**Ngày nộp:** 2026-04-15
**Repo:** https://github.com/PhamXuanKhang/Lecture-Day-08-09-10
**run_id chính:** `sprint-final`
**run_id inject (Sprint 3):** `inject-bad`

---

## 1. Pipeline tổng quan

Nguồn raw là `data/raw/policy_export_dirty.csv` (mô phỏng export DB CS + HR) gồm 10 bản ghi có duplicate, missing date, dmy-format, unknown doc_id, HR 2025 stale, refund 14-day stale. Luồng chạy: `etl_pipeline.py run` → `load_raw_csv` → `clean_rows` (10 rule) → `write_cleaned_csv` + `write_quarantine_csv` → `run_expectations` (9 expectations) → nếu không halt thì `cmd_embed_internal` (Chroma upsert `day10_kb` + prune id stale) → viết `artifacts/manifests/manifest_<run_id>.json` → `check_manifest_freshness`.

`run_id` sinh từ `--run-id` hoặc UTC timestamp trong `cmd_run()`; được ghi ở: log `artifacts/logs/run_<id>.log`, manifest JSON, và metadata mỗi vector trong Chroma (`run_id` field).

**Kết quả run sprint-final:**
- `raw_records=10`, `cleaned_records=6`, `quarantine_records=4`
- 9/9 expectations pass, `embed_upsert count=6`, `embed_prune_removed=1` (lần chạy sau inject)
- `freshness_check=FAIL` — CSV mẫu có `exported_at=2026-04-10`, SLA=24h, chạy 2026-04-15 → `age_hours≈122` (kỳ vọng FAIL với dataset tĩnh, giải thích ở mục 4)

**Lệnh chạy một dòng (pipeline + eval + grading):**

```bash
python etl_pipeline.py run --run-id sprint-final && \
python eval_retrieval.py --out artifacts/eval/before_after_eval.csv && \
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

---

## 2. Cleaning & expectation

Baseline có 6 rule + 6 expectations. Nhóm bổ sung:

- **Rule R7 `strip_invisible_chars`** trong `transform/cleaning_rules.py`: loại BOM/zero-width space/NBSP trong `chunk_text` trước dedupe. Ảnh hưởng: khi inject BOM, chunk BOM sẽ không lách dedupe → dedupe đúng.
- **Rule R8 `quarantine_future_effective_date`**: `effective_date > today + 2 năm` → quarantine (`reason=future_effective_date`). Bắt lỗi export kiểu `2099-01-01`.
- **Rule R9 `quarantine_chunk_too_long`**: `len(chunk_text) > 2000` → quarantine. Chặn context bất thường.
- **Rule R10 `normalize_policy_version_marker`**: trong refund v4 thay "policy-v3" → "policy-v4".
- **Expectation E7 `chunk_id_unique`** (halt): phát hiện collision nghi ngờ trước khi upsert Chroma.
- **Expectation E8 `all_required_docs_present`** (warn): cảnh báo khi export thiếu một doc trong allowlist.
- **Expectation E9 `no_invisible_chars`** (warn): sau R7 vẫn còn ký tự lạ → log warn (cross-check R7 chạy đúng).

### 2a. Bảng metric_impact (chống trivial)

| Rule / Expectation mới | Trước | Sau / khi inject | Chứng cứ |
|------------------------|-------|------------------|----------|
| R6 fix refund 14→7 | inject-bad: `hits_forbidden=yes` với `q_refund_window` | sprint-final: `hits_forbidden=no` | `artifacts/eval/after_inject_bad.csv` vs `before_after_eval.csv` |
| R7 strip_invisible_chars | Nếu inject BOM ở text trùng → 2 bản vào cleaned | Sau R7: bản BOM collide key dedupe → 1 bản (`quarantine_records+=1`) | `transform/cleaning_rules.py:_strip_invisible` + E9 OK |
| R8 future_effective_date | effective_date 2099 lọt `eff_norm=2099-…`, embed lỗi version | quarantine `reason=future_effective_date` | `transform/cleaning_rules.py` rule R8 |
| R9 chunk_too_long | Chunk 5000 char → context noise trong top-k | quarantine `reason=chunk_too_long` | `transform/cleaning_rules.py` rule R9 |
| E7 chunk_id_unique | Nếu collision `chunk_id` ngẫu nhiên → upsert overwrite thầm lặng | halt trước khi upsert | `quality/expectations.py` E7 |
| E8 all_required_docs_present | Thiếu doc `sla_p1_2026` vẫn pass → agent trả "không biết" | warn log `missing_docs=['sla_p1_2026']` | `quality/expectations.py` E8 |
| E9 no_invisible_chars | R7 tắt vô tình → ký tự lạ vào vector | warn log `invisible_char_rows>0` | `quality/expectations.py` E9 |
| E3 refund_no_stale_14d_window | inject-bad: `violations=1` (halt) | sprint-final: `violations=0` | log `artifacts/logs/run_inject-bad.log`, `run_sprint-final.log` |

**Ví dụ 1 lần expectation fail và cách xử lý:** Ở `run-id=inject-bad`, log ghi `expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1`. Vì chạy cờ `--skip-validate`, pipeline tiếp tục embed kèm WARN — đây là demo có chủ đích Sprint 3. Xử lý thực tế: bỏ cờ `--skip-validate` → pipeline exit 2 → Cleaning Owner mở quarantine CSV, fix rule, rerun.

---

## 3. Before / after ảnh hưởng retrieval

**Kịch bản inject:** `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`. Rule R6 bị vô hiệu → chunk "14 ngày làm việc" lọt cleaned → expectation E3 FAIL nhưng bị skip → vector stale push vào `day10_kb`.

**Kết quả định lượng (top-k=3):**

`artifacts/eval/after_inject_bad.csv` (trước fix — run_id=inject-bad):
```
q_refund_window,policy_refund_v4,"Yêu cầu được gửi trong vòng 7 ngày...",yes,yes,,3
q_leave_version,hr_leave_policy,"...12 ngày phép năm theo chính sách 2026.",yes,no,yes,3
```
→ `q_refund_window` **`hits_forbidden=yes`** — top-k còn chunk "14 ngày làm việc" stale.

`artifacts/eval/before_after_eval.csv` (sau fix — run_id=sprint-final):
```
q_refund_window,policy_refund_v4,"Yêu cầu được gửi trong vòng 7 ngày...",yes,no,,3
q_leave_version,hr_leave_policy,"...12 ngày phép năm theo chính sách 2026.",yes,no,yes,3
```
→ `hits_forbidden=no` cho cả `q_refund_window` và `q_leave_version`. Merit condition (`q_leave_version`: `contains_expected=yes, hits_forbidden=no, top1_doc_expected=yes`) đạt.

Grading JSONL (`artifacts/eval/grading_run.jsonl`) ba dòng `gq_d10_01..03` đều có `contains_expected=true, hits_forbidden=false, top1_doc_matches=true` — kiểm bằng `instructor_quick_check.py` in ra `MERIT_CHECK[gq_d10_*] OK`.

---

## 4. Freshness & monitoring

SLA `FRESHNESS_SLA_HOURS=24`, đo ở **publish boundary** (`latest_exported_at = max exported_at` cleaned). CSV mẫu có `exported_at=2026-04-10T08:00:00`; chạy 2026-04-15 → `age_hours ≈ 122` → **FAIL**.

Diễn giải: pipeline run chạy đúng nhưng **data snapshot cũ** — runbook khuyến nghị đẩy export mới hoặc nới SLA cho dataset tĩnh. PASS = `age_hours <= sla_hours`; WARN (reserved) khi thiếu timestamp; FAIL khi vượt SLA. Alert channel giả định `#data-obs-day10`.

---

## 5. Liên hệ Day 09

Pipeline Day 10 dùng **cùng corpus `data/docs/`** với Day 09 nhưng publish vào **collection tách** `day10_kb` để tránh tranh chấp grading. Day 09 agent có thể trỏ sang `day10_kb` nếu muốn test dữ liệu "đã clean + version-aware"; mặc định giữ collection Day 09 riêng.

---

## 6. Rủi ro còn lại & việc chưa làm

- Chưa tích hợp Great Expectations / pydantic thật (Bonus +2 bỏ ngỏ).
- Freshness chỉ đo publish; chưa đo ingest boundary (mtime raw file).
- LLM-judge chưa có; eval keyword-only.
- Rule R8 future_effective_date dùng `date.today()` — nên đọc cutoff từ env/contract để tái sản xuất được trong CI.
