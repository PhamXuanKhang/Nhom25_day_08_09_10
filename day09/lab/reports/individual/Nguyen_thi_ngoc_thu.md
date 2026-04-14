# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Thị Ngọc Thư
**Vai trò trong nhóm:** Trace & Docs Owner  
**Ngày nộp:** 2026-04-14  

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi chịu trách nhiệm Sprint 4 — evaluation framework, documentation, và artifacts. Đây là phần quan trọng nhất để nhóm hiểu được hệ thống đang hoạt động đúng ở đâu, sai ở đâu, và để chuẩn bị nộp grading.

**Module/file tôi chịu trách nhiệm:**
- File chính: `eval_trace.py` — toàn bộ pipeline evaluation
- File phụ: `docs/system_architecture.md`, `docs/routing_decisions.md`, `docs/single_vs_multi_comparison.md`, `reports/group_report.md`

**Functions tôi implement trong `eval_trace.py`:**
- `run_test_questions(questions_file)` — chạy 15 câu, ghi trace, tính route_ok/sources_ok/abstain_ok
- `run_grading_questions()` — chạy grading questions, xuất JSONL log
- `analyze_traces(traces_dir)` — tính routing_distribution, avg_confidence, abstain_rate, MCP usage
- `compare_single_vs_multi()` — so sánh Day 08 vs Day 09 baseline
- `save_eval_report()` — ghi `artifacts/eval_report.json`
- CLI với 3 flags: `--grading`, `--analyze`, `--compare`

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`run_test_questions()` gọi `run_graph()` của Khang và `save_trace()` để lưu output. Tôi đọc `AgentState` fields như `route_reason` (Khang ghi), `mcp_tools_used` (Thức ghi), `worker_io_logs` (Duy ghi) để tính metrics. Kết quả phân tích được điền vào 3 file docs và group_report.

**Bằng chứng:** Commit `88f5728 vanthuc — running grading question done`, commit `3f3c524 thungoc123 — Thu's report`, commit `9e03d77 thungoc123 — Update document`, commit `00b389d thungoc123 — Add detailed Mermaid charts for indexing and retrieval pipelines`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Dùng append-only JSONL format cho grading log thay vì JSON array

Khi implement `run_grading_questions()`, tôi cần chọn format output file cho `artifacts/grading_run.jsonl`. Hai lựa chọn chính: JSON array (`[{...}, {...}]`) hoặc JSONL (một record mỗi dòng).

**Các lựa chọn thay thế:**
- JSON array: cần load toàn bộ vào memory, nếu crash giữa chừng mất data, cần serialize lại toàn bộ
- JSONL (đã chọn): ghi từng record ngay sau khi pipeline xử lý xong câu đó — nếu crash ở câu q08, đã có q01-q07 trong file

**Phương án đã chọn:**

```python
with open(output_file, "w", encoding="utf-8") as out:
    for i, q in enumerate(questions, 1):
        ...
        result = run_graph(question_text)
        record = {
            "id": q_id, "answer": result.get("final_answer"), 
            "supervisor_route": ..., "confidence": ...,
        }
        out.write(json.dumps(record, ensure_ascii=False) + "\n")  # flush ngay
```

**Trade-off đã chấp nhận:** JSONL không parse được bằng `json.load()` thẳng, cần đọc từng dòng. Chấp nhận vì grading script của giảng viên ghi rõ định dạng này trong SCORING.md.

**Bằng chứng từ trace/code:**

```bash
# Sau khi chạy run_grading_questions():
wc -l artifacts/grading_run.jsonl
# → 10 (mỗi dòng = 1 grading question)

# Nếu dùng JSON array và crash, file corrupt hoàn toàn.
# Với JSONL, câu nào đã chạy xong đã được lưu.
```

Grading run hoàn thành không lỗi, file `grading_run.jsonl` có đủ records với format đúng.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** `analyze_traces()` đọc nhầm traces cũ khi chạy lại eval

**Symptom:**

Sau khi nhóm fix bug trong `synthesis.py` và chạy lại `eval_trace.py`, metrics trong `test_summary.json` vẫn không thay đổi — route_accuracy vẫn là giá trị cũ. Tưởng fix không có effect nhưng thực ra là eval đang đọc trace files cũ.

**Root cause:**

`analyze_traces()` dùng `traces_dir.glob("*.json")` nhưng `TRACES_DIR` được set mặc định và không được xóa trước khi chạy lại. Traces từ run cũ vẫn còn trong thư mục và được tính vào metrics. Tổng số traces tăng lên mỗi lần chạy (run-based filename theo timestamp), không override.

**Cách sửa:**

Thêm `run_id` timestamp vào tên file để identify đúng traces của run hiện tại. Trong `run_test_questions()`, collect list of trace files từ run này và dùng cho `analyze_traces()`:

```python
# Sau khi chạy xong, chỉ analyze traces từ run hiện tại
# (hoặc dùng test_summary.json thay vì scan thư mục)
summary_file = ARTIFACTS_DIR / "test_summary.json"
with open(summary_file, "w", encoding="utf-8") as f:
    json.dump({
        "generated_at": datetime.now().isoformat(),
        "route_accuracy": ...,
        "results": results,  # chỉ kết quả run này
    }, f, ensure_ascii=False, indent=2)
```

**Bằng chứng trước/sau:**

Trước: Route accuracy không thay đổi sau fix → debugging mất ~20 phút tưởng fix sai.  
Sau: `test_summary.json` phản ánh đúng run hiện tại. Route accuracy 93.3% (14/15) khớp với manual check từng câu trong `results` array.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Viết documentation đủ chi tiết để cả nhóm và giảng viên hiểu được system mà không cần đọc code. `docs/routing_decisions.md` ghi đủ 4 routing cases thực tế từ trace với `route_reason` copy từ trace thật, không phải minh họa giả. `docs/single_vs_multi_comparison.md` có số liệu cụ thể (abstain rate 20%, debug time ~-60%) thay vì nhận xét chung chung.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Chưa điền được số liệu Day 08 baseline vào comparison table — artifact Day 08 không có `eval.py` output chuẩn format để load. Phần `<<DAY08_CONF>>` trong comparison vẫn là N/A, nên delta analysis chỉ định tính.

**Nhóm phụ thuộc vào tôi ở đâu?**

`artifacts/grading_run.jsonl` — đây là file nộp chính cho giảng viên chấm. Nếu tôi không chạy `python eval_trace.py --grading` sau 17:00 hoặc file format sai, cả nhóm mất điểm phần grading.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần cả 3 member khác hoàn thành code trước 17:00 để có thể chạy pipeline end-to-end. Đặc biệt cần Thức fix `mcp_server.py` import bug trước vì nếu MCP fail, câu q13 và q15 sẽ thiếu MCP tool call trong trace.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ bổ sung Day 08 baseline metrics vào `eval_report.json`. Hiện tại comparison table chỉ có Day 09 metrics. Nếu có thể chạy `day08/lab/eval.py` và export `avg_confidence`, `avg_latency`, `abstain_rate`, bảng so sánh sẽ có số thật thay vì `N/A`. Từ trace q14 (abstain sai, confidence=0.54) và q09 (abstain đúng, confidence=0.44), tôi nghi Day 09 có abstain rate cao hơn Day 08 rõ rệt — đây sẽ là evidence mạnh nhất cho lợi ích multi-agent anti-hallucination.

---
