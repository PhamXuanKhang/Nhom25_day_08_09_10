# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nhóm 25  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Phạm Xuân Khang | Supervisor Owner | khang.px@vinuni.edu.vn |
| Phạm Thành Duy | Worker Owner | duy.pt@vinuni.edu.vn |
| Văn Thức | MCP Owner | thuc.v@vinuni.edu.vn |
| Nguyễn Thị Thu | Trace & Docs Owner | thu.nt@vinuni.edu.vn |

**Ngày nộp:** 2026-04-14  
**Repo:** https://github.com/PhamXuanKhang/Nhom25_day_08_09_10  
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

**Hệ thống tổng quan:**

Nhóm xây dựng hệ thống Supervisor-Worker multi-agent bằng Python thuần (không dùng LangGraph) gồm 4 thành phần chính: Supervisor (`graph.py`), 3 Workers (`retrieval.py`, `policy_tool.py`, `synthesis.py`) và MCP server (`mcp_server.py`).

Knowledge base gồm 5 file `.txt` được index vào ChromaDB với embedding OpenAI `text-embedding-3-small` (1536-dim). Tổng cộng có 15 câu test questions đã chạy thành công.

**Routing logic cốt lõi:**

Supervisor dùng keyword matching theo 3 bảng: `POLICY_KEYWORDS` (hoàn tiền, flash sale, license, access level, ...), `RETRIEVAL_HINT_KEYWORDS` (sla, ticket, p1, helpdesk, ...), và `RISK_KEYWORDS` (override, emergency, bypass, ...). Nếu câu hỏi có dấu hiệu multi-hop hoặc cần tool (ví dụ access + ticket) thì ưu tiên route sang `policy_tool_worker` để gọi MCP.

**MCP tools đã tích hợp:**

- `search_kb`: Tìm kiếm KB nội bộ — delegate sang `retrieve_dense()` từ retrieval worker (cùng ChromaDB collection)
- `get_ticket_info`: Tra cứu ticket mock — trả `ticket_id, priority, status, assignee, sla_deadline, notifications_sent`
- `check_access_permission`: Kiểm tra access rules Level 1–4 + emergency bypass logic
- `create_ticket`: Tạo ticket mock với SLA deadline tự động theo priority (P1=4h, P2=24h, P3=120h)

---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Dùng keyword-based routing thuần Python thay vì LLM classifier để supervisor quyết định route

**Bối cảnh vấn đề:**

Nhóm cần quyết định làm thế nào để supervisor phân tích task và chọn worker phù hợp. Hai lựa chọn chính là: (1) Gọi LLM để classify intent, hoặc (2) Dùng keyword matching deterministic.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| LLM classifier (gpt-4o-mini) | Hiểu ngữ nghĩa tốt hơn, xử lý paraphrase | Thêm 800–1200ms latency, chi phí thêm API call, không deterministic |
| Keyword matching (đã chọn) | ~5ms latency, deterministic, dễ audit và debug, không cần API key | Miss khi câu diễn đạt khác, cần maintain bảng keyword |

**Phương án đã chọn và lý do:**

Nhóm chọn keyword matching vì: (1) Scope 5 domain docs có vocabulary ổn định — từ khóa như "hoàn tiền", "sla", "access level" xuất hiện nhất quán; (2) Latency supervisor gần như không đáng kể; (3) Quy tắc route minh bạch, dễ giải thích bằng `route_reason` trong trace.

**Bằng chứng từ trace/code:**

```text
# q01 trace — retrieval_worker route, latency supervisor ~5ms
route_reason: "matches knowledge keywords: ['sla', 'ticket', 'p1']"
workers_called: ["retrieval_worker", "synthesis_worker"]
latency_ms: 6248  # bottleneck là OpenAI embedding + synthesis, supervisor <5ms

# q13 trace — multi-hop override
route_reason: "matches policy/access keywords: ['cấp quyền', 'level 3'] | 
               access question → will call MCP check_access_permission |
               multi-hop SLA+access → policy_tool_worker with MCP"
workers_called: ["retrieval_worker", "policy_tool_worker", "synthesis_worker"]
mcp_tools_used: ["check_access_permission", "get_ticket_info"]

Route accuracy đạt 93.3% (14/15) với keyword approach. Câu duy nhất route sai là q02 ("Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?").
```

---

## 3. Kết quả grading questions

**Tổng điểm raw ước tính:** Dựa trên 15 test questions — route_accuracy 93.3%, source_hit_rate 100%, avg_confidence 0.70.

Từ `artifacts/grading_run.jsonl` đã chạy sau 17:00:

**Câu pipeline xử lý tốt nhất:**
- ID: q15 — Pipeline route đúng `policy_tool_worker`, gọi đủ 2 MCP tools (`check_access_permission` + `get_ticket_info`), cite đúng 2 sources (`sla_p1_2026.txt` + `access_control_sop.txt`).

**Câu pipeline fail hoặc partial:**
- ID: q14 — Abstain sai. Câu hỏi về nhân viên probation, answer đúng là "KHÔNG được remote" nhưng pipeline trả "Không đủ thông tin". Root cause: retrieval worker không tìm được chunk phù hợp.

**Câu gq07 (abstain):** Pipeline xử lý đúng — keyword "phạt tài chính" không có trong `POLICY_KEYWORDS` nên route sang `retrieval_worker`. ChromaDB không tìm được chunk nên abstain đúng.

**Câu gq09 (multi-hop khó nhất):** Trace ghi đủ 2 workers — `retrieval_worker` + `policy_tool_worker`, và gọi cả `check_access_permission` + `get_ticket_info`. Answer đầy đủ các bước và cite đúng nguồn.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

**Metric thay đổi rõ nhất (có số liệu):**

Từ `artifacts/eval_report.json`:
- Day 09 avg latency ~3.200ms/câu (bottleneck: OpenAI embedding + synthesis LLM). Day 08 chỉ có 1 LLM call nên latency thấp hơn ~20–30%.
- Day 09 abstain rate = 3/15 = **20%** (q09 ERR-403, q12 temporal scoping, q14 probation) — cao hơn Day 08 do có nhiều lớp bảo vệ (HITL, signal `chunks=[]`, grounded prompt).
- Route visibility: Day 09 có `route_reason` mỗi câu; Day 08 không có concept này.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Giá trị lớn nhất không phải tăng chất lượng trả lời tuyệt đối, mà là khả năng xác định lỗi nhanh. Với Day 09, chỉ cần mở trace là biết lỗi thuộc routing, retrieval, tool hay synthesis.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Với câu hỏi fact đơn giản, multi-agent không cải thiện mạnh độ đúng nhưng vẫn tốn orchestration overhead (supervisor + worker chain), làm latency cao hơn so với kỳ vọng.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Phạm Xuân Khang | `graph.py` — AgentState, supervisor_node, build_graph, save_trace, setup_index.py, app.py (Streamlit UI), OpenAI embedding migration | Sprint 1 + Bonus |
| Phạm Thành Duy | `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`, `contracts/worker_contracts.yaml` | Sprint 2 |
| Văn Thức | `mcp_server.py` (4 tools + dispatcher), `mcp_http_server.py` (bonus HTTP server), phần `_call_mcp_tool` trong policy_tool.py | Sprint 3 |
| Nguyễn Thị Thu | `eval_trace.py`, `docs/system_architecture.md`, `docs/routing_decisions.md`, `docs/single_vs_multi_comparison.md`, artifacts/ | Sprint 4 |

**Điều nhóm làm tốt:**

Phân công rõ theo sprint + file owner. Nhờ `contracts/worker_contracts.yaml` định nghĩa I/O trước, các member có thể implement độc lập rồi integrate. Không có merge conflict lớn.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

Embedding model ban đầu dùng SentenceTransformer local (MiniLM), phải refactor sang OpenAI `text-embedding-3-small` gần cuối — mất thời gian re-index và align retrieval + indexing.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

Định nghĩa embedding model và ChromaDB schema trước khi bắt đầu Sprint 2 — để retrieval và indexing không phải sync lại sau khi đã implement xong.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?

**Cải tiến 1:** Thêm LLM-as-Judge để đánh giá confidence (bonus +1 theo SCORING.md). Hiện tại confidence = heuristic `weighted_avg(chunk_scores) - penalties`.

**Cải tiến 2:** Cache retrieval result cho câu trùng topic (q01 và gq05 đều hỏi SLA P1) — giảm 30–40% latency khi batch grading qua cosine similarity threshold trên query embedding.