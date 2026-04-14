# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nhom25  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| [Điền tên] | Supervisor Owner | [Điền email] |
| [Điền tên] | Worker Owner | [Điền email] |
| [Điền tên] | MCP Owner | [Điền email] |
| [Điền tên] | Trace & Docs Owner | [Điền email] |

**Ngày nộp:** 14/04/2026  
**Repo:** day09/lab  
**Độ dài:** ~900 từ

---

## 1. Kiến trúc nhóm đã xây dựng 

**Hệ thống tổng quan:**

Nhóm triển khai kiến trúc Supervisor-Worker với shared state trong `graph.py`. Luồng chạy gồm: `supervisor_node` phân tích câu hỏi và gán `supervisor_route` + `route_reason`, sau đó `route_decision` chọn nhánh `retrieval_worker`, `policy_tool_worker`, hoặc `human_review`. Dù đi nhánh nào, hệ thống đều kết thúc ở `synthesis_worker` để tạo `final_answer`, `sources`, `confidence`, rồi ghi trace vào `artifacts/traces/*.json`. Worker retrieval dùng ChromaDB (`day09_docs`) để lấy bằng chứng; policy worker xử lý rule/exception và gọi MCP tool khi cần; synthesis worker tổng hợp grounded answer, có cơ chế abstain khi thiếu evidence.

**Routing logic cốt lõi:**

Supervisor dùng rule-based keyword matching. Câu có tín hiệu policy/access như “hoàn tiền”, “level 2/3”, “admin access”, “contractor” sẽ route sang `policy_tool_worker`. Câu thiên về tra cứu fact như “sla”, “ticket”, “remote”, “probation” route sang `retrieval_worker`. Có override cho query rủi ro (ví dụ mã lỗi dạng `ERR-...`) để trigger `human_review` trước khi fallback retrieval trong lab mode.

**MCP tools đã tích hợp:**

- `search_kb`: semantic search từ MCP (được dùng khi policy worker thiếu chunks).
- `get_ticket_info`: trả metadata ticket (priority, assignee, sla_deadline, notifications).
- `check_access_permission`: kiểm tra điều kiện cấp quyền, approvers, emergency override.

Ví dụ trace có MCP call: `gq09` trong `artifacts/grading_run.jsonl` gọi đồng thời `check_access_permission` và `get_ticket_info`.

---

## 2. Quyết định kỹ thuật quan trọng nhất 

**Quyết định:** Chọn routing rule-based có giải thích rõ (`route_reason`) thay vì classifier/LLM router ngay từ đầu.

**Bối cảnh vấn đề:**

Ở đầu sprint, nhóm cân nhắc dùng LLM để phân loại route vì linh hoạt hơn với ngôn ngữ tự nhiên. Tuy nhiên, yêu cầu của lab nhấn mạnh traceability và debug trong thời gian ngắn. Khi pipeline sai, nếu route không giải thích được thì khó biết lỗi nằm ở đâu.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| LLM/classifier router | Linh hoạt với paraphrase, ít phụ thuộc keyword cứng | Khó audit, tốn thêm latency/cost, khó giải thích route cụ thể |
| Rule-based keyword router + override | Nhanh, deterministic, dễ debug và dễ log lý do | Có thể false-positive/false-negative khi câu hỏi mơ hồ |

**Phương án đã chọn và lý do:**

Nhóm chọn rule-based router vì phù hợp mục tiêu sprint: route đúng ở mức cao và dễ quan sát. Kết quả test cho thấy route accuracy đạt `14/15` (`93.33%`) theo `artifacts/test_summary.json`, chứng minh cách tiếp cận này đủ hiệu quả cho domain hẹp của lab. Đồng thời `route_reason` ghi đầy đủ keyword hit, risk signal, override, giúp nhóm khoanh vùng lỗi nhanh hơn.

**Bằng chứng từ trace/code:**

```text
Trace gq09 (grading_run.jsonl):
route_reason = "matches policy/access keywords: ['level 2', 'contractor'] |
risk signals: ['emergency', '2am'] | access question -> will call MCP check_access_permission |
multi-hop SLA+access -> policy_tool_worker with MCP"
workers_called = ["retrieval_worker", "policy_tool_worker", "synthesis_worker"]
mcp_tools_used = ["check_access_permission", "get_ticket_info"]
```

---

## 3. Kết quả grading questions 

**Tổng điểm raw ước tính:** `86 / 96` (ước tính nội bộ, điểm chính thức theo rubric giảng viên)

**Câu pipeline xử lý tốt nhất:**
- ID: `gq09` — Lý do tốt: trả lời đầy đủ cả 2 phần multi-hop (SLA notification + Level 2 emergency access), route đúng sang policy worker, và trace có đủ worker chain + MCP tools.

**Câu pipeline fail hoặc partial:**
- ID: `gq06` — Fail ở đâu: hệ thống abstain thay vì kết luận rõ điều kiện probation/remote.  
  Root cause: synthesis quá bảo thủ với ngưỡng abstain khi context có phần gián tiếp, dẫn đến bỏ lỡ suy luận “sau probation mới được remote”.

**Câu gq07 (abstain):** Nhóm xử lý thế nào?

Pipeline trả lời “Không đủ thông tin trong tài liệu nội bộ...” và không bịa mức phạt tài chính. Đây là hành vi đúng mục tiêu anti-hallucination cho câu bẫy thiếu dữ liệu.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?

Có. Trace ghi `retrieval_worker -> policy_tool_worker -> synthesis_worker`, đồng thời log 2 MCP calls (`check_access_permission`, `get_ticket_info`). Nội dung trả lời bao gồm timeline notify P1 và điều kiện cấp quyền khẩn cấp (24h, phê duyệt, audit log).

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được 

**Metric thay đổi rõ nhất (có số liệu):**

Day09 có observability rõ rệt: route accuracy `93.33%`, MCP usage `20.0%` (`3/15`), HITL `6.7%` (`1/15`), avg latency `3106ms` (nguồn: `artifacts/eval_report.json`, `artifacts/test_summary.json`). Day08 không có trường route/worker-level trace nên không đo trực tiếp routing quality.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Giá trị lớn nhất không phải tăng chất lượng trả lời tuyệt đối, mà là khả năng xác định lỗi nhanh. Với Day09, chỉ cần mở trace là biết lỗi thuộc route, retrieval, policy hay synthesis; trước đó Day08 phải đọc toàn pipeline để đoán nguyên nhân.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Với câu hỏi fact đơn giản, multi-agent không cải thiện mạnh độ đúng nhưng vẫn tốn orchestration overhead (supervisor + worker chain), làm latency cao hơn so với kỳ vọng single flow. Ngoài ra rule-based routing vẫn có 1 false route (q02), cho thấy multi-agent chưa tự động tốt nếu tầng routing chưa đủ tinh.

---

## 5. Phân công và đánh giá nhóm 

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| [Điền tên] | `graph.py`, routing rules, HITL fallback | 1 |
| [Điền tên] | `workers/retrieval.py`, `workers/synthesis.py`, contracts | 2 |
| [Điền tên] | `mcp_server.py`, tích hợp MCP trong `workers/policy_tool.py` | 3 |
| [Điền tên] | `eval_trace.py`, `docs/*`, `reports/group_report.md` | 4 |

**Điều nhóm làm tốt:**

Giữ contract rõ giữa supervisor và workers, nên tích hợp nhanh và ít conflict khi merge. Mỗi sprint đều có artifact kiểm chứng (trace, summary, docs).

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

Một số quyết định threshold (abstain/confidence) thống nhất muộn, làm phải chạy lại eval ở cuối sprint.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

Chốt tiêu chí đánh giá từng category ngay từ Sprint 1 và có checklist regression cho routing trước khi chạy full 15 câu.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?

1. Nâng cấp routing từ keyword sang hybrid rule + lightweight classifier để giảm false route ở các câu chứa từ policy nhưng thực chất là fact retrieval (bằng chứng: q02 route mismatch trong `test_summary.json`).
2. Triển khai HITL thực thay vì auto-approve lab mode, gồm hàng chờ review và resume flow, nhằm xử lý tốt các query rủi ro như mã lỗi không có trong KB.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
