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

Nhóm xây dựng hệ thống Supervisor-Worker multi-agent bằng Python thuần (không dùng LangGraph) gồm 4 thành phần chính: Supervisor (`graph.py`), 3 Workers (`retrieval.py`, `policy_tool.py`, `synthesis.py`) và MCP Server (`mcp_server.py`). Toàn bộ trạng thái hệ thống đi qua `AgentState` TypedDict với 18 fields, được truyền xuyên suốt các bước xử lý.

Knowledge base gồm 5 file `.txt` được index vào ChromaDB với embedding OpenAI `text-embedding-3-small` (1536-dim). Tổng cộng có 15 câu test questions đã chạy thành công, đạt route_accuracy = **93.3%** (14/15 câu route đúng) và source_hit_rate = **100%**.

**Routing logic cốt lõi:**

Supervisor dùng keyword matching theo 3 bảng: `POLICY_KEYWORDS` (hoàn tiền, flash sale, license, access level, ...), `RETRIEVAL_HINT_KEYWORDS` (sla, ticket, p1, helpdesk, ...), và `RISK_KEYWORDS` (emergency, err-, khẩn cấp). Có 2 override rule: (1) pattern `err-` → force `human_review`; (2) multi-hop SLA+access → force `policy_tool_worker` với `needs_tool=True`. Mỗi quyết định được ghi vào `route_reason` ở dạng `signal1 | signal2 | override_note`.

**MCP tools đã tích hợp:**

- `search_kb`: Tìm kiếm KB nội bộ — delegate sang `retrieve_dense()` từ retrieval worker (cùng ChromaDB collection)
- `get_ticket_info`: Tra cứu ticket mock — trả `ticket_id, priority, status, assignee, sla_deadline, notifications_sent` (ví dụ trace q15: `ticket_id=IT-9847, assignee=nguyen.van.a@company.internal`)
- `check_access_permission`: Kiểm tra access rules Level 1–4 + emergency bypass logic (trace q13: `level=3, emergency_override=False, approvers=[Line Manager, IT Admin, IT Security]`)
- `create_ticket`: Tạo ticket mock với SLA deadline tự động theo priority (P1=4h, P2=24h, P3=120h)

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

**Quyết định:** Dùng keyword-based routing thuần Python thay vì LLM classifier để supervisor quyết định route

**Bối cảnh vấn đề:**

Nhóm cần quyết định làm thế nào để supervisor phân tích task và chọn worker phù hợp. Hai lựa chọn chính là: (1) Gọi LLM để classify intent, hoặc (2) Dùng keyword matching với bảng cứng. Với scope 5 domain docs và 3 route types, đây là quyết định có ảnh hưởng lớn đến latency và predictability.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| LLM classifier (gpt-4o-mini) | Hiểu ngữ nghĩa tốt hơn, xử lý paraphrase | Thêm 800–1200ms latency, chi phí thêm API call, không deterministic |
| Keyword matching (đã chọn) | ~5ms latency, deterministic, dễ audit và debug, không cần API key | Miss khi câu diễn đạt khác, cần maintain bảng keyword |

**Phương án đã chọn và lý do:**

Nhóm chọn keyword matching vì: (1) Scope 5 domain docs có vocabulary ổn định — từ khóa như "hoàn tiền", "sla", "access level" xuất hiện nhất quán; (2) Latency supervisor < 5ms so với 800ms+ nếu dùng LLM — tiết kiệm đáng kể khi pipeline chạy 15 câu; (3) `route_reason` luôn explainable — giảng viên đọc trace thấy ngay tại sao route đó được chọn.

**Bằng chứng từ trace/code:**

```
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
```

Route accuracy đạt 93.3% (14/15) với keyword approach. Câu duy nhất route sai là q02 ("Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?" — route thành `policy_tool_worker` thay vì `retrieval_worker` vì keyword "hoàn tiền"), nhưng answer vẫn đúng vì source_hit_rate = 100%.

---

## 3. Kết quả grading questions (150–200 từ)

**Tổng điểm raw ước tính:** Dựa trên 15 test questions — route_accuracy 93.3%, source_hit_rate 100%, avg_confidence 0.70.

Từ `artifacts/grading_run.jsonl` đã chạy sau 17:00:

**Câu pipeline xử lý tốt nhất:**
- ID: q15 — Pipeline route đúng `policy_tool_worker`, gọi đủ 2 MCP tools (`check_access_permission` + `get_ticket_info`), cite đúng 2 sources (`sla_p1_2026.txt` + `access_control_sop.txt`), confidence=0.82, answer đầy đủ cả 2 quy trình Level 2 emergency bypass và SLA notifications. Đây là câu multi-hop khó nhất và pipeline xử lý hoàn chỉnh.

**Câu pipeline fail hoặc partial:**
- ID: q14 — Abstain sai. Câu hỏi về nhân viên probation, answer đúng là "KHÔNG được remote" nhưng pipeline trả "Không đủ thông tin". Root cause: retrieval worker không tìm được chunk chứa nội dung cấm probation period làm remote, chunking section-based đã tách nội dung này vào sub-chunk không đủ context.

**Câu gq07 (abstain):** Pipeline xử lý đúng — keyword "phạt tài chính" không có trong POLICY_KEYWORDS nên route sang `retrieval_worker`. ChromaDB không tìm được chunk về mức phạt tài chính vi phạm SLA, synthesis abstain với "Không đủ thông tin trong tài liệu nội bộ." — đúng hành vi, tránh hallucinate.

**Câu gq09 (multi-hop khó nhất):** Trace ghi đủ 2 workers — `retrieval_worker` + `policy_tool_worker`, và gọi cả `check_access_permission` + `get_ticket_info`. Answer đầy đủ cross-reference giữa 2 documents.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

**Metric thay đổi rõ nhất (có số liệu):**

Từ `artifacts/eval_report.json`:
- Day 09 avg latency ~3.200ms/câu (bottleneck: OpenAI embedding + synthesis LLM). Day 08 chỉ có 1 LLM call nên latency thấp hơn ~20-30%.
- Day 09 abstain rate = 3/15 = **20%** (q09 ERR-403, q12 temporal scoping, q14 probation) — cao hơn Day 08 do 3 lớp bảo vệ: supervisor HITL, chunks=[] signal, grounded system prompt. Đây là tốt vì tránh penalty −50% từ hallucination.
- Route visibility: Day 09 có `route_reason` mỗi câu; Day 08 không có concept này.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Câu q09 (ERR-403-AUTH): single agent Day 08 khả năng cao sẽ cố trả lời và bịa thông tin về auth error. Multi-agent force HITL → retrieval → abstain hoàn toàn tự động, không cần thêm prompt engineering. Chi phí abstain còn **rẻ hơn** vì không gọi LLM synthesis (local fallback template, ~1.584ms tổng latency).

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Câu q01, q04, q05 (single-doc, easy): supervisor + routing overhead thêm ~100-200ms mà không mang lại accuracy gain so với Day 08. Multi-agent code cũng phức tạp hơn đáng kể: 6 file Python + contracts YAML vs 1 monolithic script.

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

Phân công rõ theo sprint + file owner. Nhờ `contracts/worker_contracts.yaml` định nghĩa I/O trước, các member có thể implement độc lập rồi integrate. Không có merge conflict lớn vì file ownership tách biệt.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

Embedding model ban đầu dùng SentenceTransformer local (MiniLM), phải refactor sang OpenAI `text-embedding-3-small` gần cuối — mất thời gian re-index và align cả retrieval.py lẫn setup_index.py. Nếu đồng nhất stack ngay từ đầu sẽ tiết kiệm hơn.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

Định nghĩa embedding model và ChromaDB schema trước khi bắt đầu Sprint 2 — để retrieval và indexing không phải sync lại sau khi đã implement xong.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

**Cải tiến 1:** Thêm LLM-as-Judge để đánh giá confidence (bonus +1 theo SCORING.md). Hiện tại confidence = heuristic `weighted_avg(chunk_scores) - penalties`. Trace câu q14 (confidence=0.54 nhưng abstain sai) cho thấy công thức chưa đủ tinh tế — LLM judge có thể cross-check answer vs chunks để phát hiện mismatch.

**Cải tiến 2:** Cache retrieval result cho câu trùng topic (q01 và gq05 đều hỏi SLA P1) — giảm 30-40% latency khi batch grading qua cosine similarity threshold trên query embedding.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
