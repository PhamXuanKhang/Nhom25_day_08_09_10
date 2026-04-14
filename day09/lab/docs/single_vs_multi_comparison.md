# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** 25  
**Ngày:** 2026-04-14

> Nguồn số liệu:
> - Single-agent (Day 08): `ab_comparison.csv`, `scorecard_baseline.md`, `scorecard_variant.md`
> - Multi-agent (Day 09): `eval_report.json`, `test_summary.json`, `grading_run.jsonl`

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | N/A | 0.697 | N/A | Day 08 không log confidence; Day 09 lấy từ `eval_report.json` (15 traces) |
| Avg latency (ms) | N/A | 3106 | N/A | Day 08 không log latency; Day 09 avg latency từ `eval_report.json` |
| Abstain rate (%) | 10.0% (1/10) | 20.0% (3/15) | +10.0 điểm % | Day 08 tính từ câu trả lời có mẫu "Tôi không biết" trong `ab_comparison.csv`; Day 09 từ `eval_report.json` |
| Multi-hop accuracy | N/A | 100% (1/1) | N/A | Day 08 không có nhãn multi-hop riêng; Day 09 lấy câu category `Multi-hop` (q15) trong `test_summary.json`, đạt route/sources/abstain đều đúng |
| Routing visibility | ✗ Không có | ✓ Có `supervisor_route` + `route_reason` | N/A | `grading_run.jsonl` ghi route rõ cho 10/10 câu |
| Debug time (estimate) | ~20 phút | ~8 phút | -12 phút | Dựa trên quy trình debug thực tế ở mục 3 |
| Source hit rate | N/A | 100% | N/A | Day 09 `source_hit_rate = 1.0` trong `test_summary.json` |

**Bổ sung Day 08 scorecard (để đối chiếu chất lượng câu trả lời):**
- Baseline: Faithfulness 4.70, Relevance 4.40, Context Recall 5.00, Completeness 3.70
- Variant: Faithfulness 4.30, Relevance 4.30, Context Recall 5.00, Completeness 3.80

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Cao (scorecard baseline: Relevance 4.40/5, Completeness 3.70/5) | Cao theo trace contract (single_worker route_ok: 9/10 = 90%) |
| Latency | N/A (không log trong Day 08) | 3106 ms trung bình toàn bộ 15 câu; nhóm single_worker đa số < 4s |
| Observation | Single-agent trả lời tốt fact đơn lẻ nhưng thiếu quan sát route/debug | Multi-agent giữ chất lượng fact đơn lẻ, đồng thời cho biết vì sao route đến worker nào |

**Kết luận:** Với câu đơn giản, chất lượng trả lời không chênh lệch lớn; lợi thế chính của multi-agent nằm ở khả năng quan sát và debug hơn là tăng mạnh độ đúng nội dung.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | N/A (không có test multi-hop gắn nhãn riêng trong bộ Day 08) | 100% (1/1 câu category Multi-hop trong `test_summary.json`) |
| Routing visible? | ✗ | ✓ |
| Observation | Day 08 không tách route nên khó biết lỗi ở retrieve hay synthesis | Day 09 route sang `policy_tool_worker` ở các câu cross-doc (ví dụ q15), có log worker chain và tool usage |

**Kết luận:** Multi-agent vượt trội ở khả năng xử lý truy vấn cần phối hợp nhiều nguồn vì có supervisor routing + trace đầy đủ.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | 10% (1/10) | 20% (3/15) |
| Hallucination cases | Có dấu hiệu 1 case rõ ở q09 (ERR-403-AUTH trả lời suy diễn thay vì nói thiếu dữ liệu) | Thấp hơn ở bộ test chính: q09/q12/q14 đều abstain đúng theo nhãn trong `test_summary.json` |
| Observation | Day 08 có xu hướng vẫn trả lời khi thiếu bằng chứng | Day 09 bảo thủ hơn khi confidence thấp hoặc thiếu policy cũ (v3) |

**Kết luận:** Multi-agent có xu hướng an toàn hơn ở tình huống thiếu ngữ cảnh, đánh đổi bằng abstain rate cao hơn.

---

## 3. Debuggability Analysis

> Khi pipeline trả lời sai, mất bao lâu để tìm ra nguyên nhân?

### Day 08 — Debug workflow
```
Answer sai -> phải đọc toàn bộ RAG pipeline (index + retrieve + generate)
Không có route_reason/worker-level trace -> khó khoanh vùng nhanh
Thời gian ước tính để isolate 1 lỗi: khoảng 20 phút
```

### Day 09 — Debug workflow
```
Answer sai -> mở trace -> xem supervisor_route + route_reason + workers_called
  -> route sai: sửa supervisor rule
  -> retrieve chưa đúng: sửa retrieval_worker
  -> tổng hợp sai: sửa synthesis_worker
Thời gian ước tính để isolate 1 lỗi: khoảng 8 phút
```

**Câu cụ thể nhóm đã debug (thực tế từ trace):**

- Trường hợp q14 trong `test_summary.json`: hệ thống trả lời "Không đủ thông tin" cho câu probation-remote, trong khi expected answer xác nhận probation không được remote.
- Nhờ trace có `actual_route=retrieval_worker`, `sources_ok=true` nên khoanh vùng nhanh về bước synthesis/diễn giải thay vì lỗi retrieve nguồn.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa prompt/pipeline chính | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Mở rộng prompt monolithic | Thêm worker mới, giữ supervisor orchestration |
| Thay đổi retrieval strategy | Sửa trực tiếp trong luồng chính | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó tách module | Dễ swap từng worker |

**Nhận xét:** Day 09 modular hơn rõ rệt. Bằng chứng là trong trace có thể thấy worker chain khác nhau theo loại câu hỏi (`retrieval_worker` vs `policy_tool_worker`) và có MCP tool call khi cần.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 lần gọi model chính | Thường 2 bước chính (supervisor + synthesis), kèm retrieval |
| Complex query | 1 lần gọi model chính | 3 bước worker (`retrieval_worker` + `policy_tool_worker` + `synthesis_worker`) |
| MCP tool call | N/A | 20% traces có MCP (3/15 ở test set; 2/10 ở grading) |

**Nhận xét về cost-benefit:** Multi-agent tốn orchestration nhiều hơn nên latency trung bình tăng (3106ms), nhưng đổi lại tăng khả năng quan sát, debug và mở rộng chức năng. Với bài toán policy/access có nhiều ngoại lệ, lợi ích vận hành lớn hơn chi phí tăng thêm.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. Quan sát và debug tốt hơn nhờ có `supervisor_route`, `route_reason`, `workers_called`, `mcp_tools_used`.
2. Mở rộng hệ thống dễ hơn (thêm tool/worker không cần sửa toàn bộ pipeline).

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. Với câu đơn giản, chất lượng trả lời không tăng đột biến; trong khi chi phí orchestration và latency cao hơn.

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi phạm vi câu hỏi hẹp, ít ngoại lệ, không cần route phức tạp và ưu tiên latency/cost thấp cho production.

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

1. Thêm evaluator answer-level (exactness/semantic match) để có accuracy trực tiếp thay vì proxy từ route/source.
2. Thêm calibration cho confidence + ngưỡng abstain theo từng category để giảm false-abstain (như case q14).
