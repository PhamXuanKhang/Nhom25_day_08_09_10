# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Văn Thức  
**Vai trò trong nhóm:** MCP Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi chịu trách nhiệm Sprint 3 — thiết kế và implement MCP Server. MCP (Model Context Protocol) là lớp abstraction cho phép agent gọi external tools theo chuẩn mà không cần hard-code từng API call. Đây là thành phần cho phép pipeline mở rộng capability mà không phải sửa core logic.

**Module/file tôi chịu trách nhiệm:**
- File chính: `mcp_server.py` — toàn bộ (4 tools + dispatcher + discovery)
- File phụ: `mcp_http_server.py` — bonus HTTP server (FastAPI), phần `_call_mcp_tool()` trong `workers/policy_tool.py`

**Functions tôi implement:**
- `TOOL_SCHEMAS` dict — 4 tool schemas chuẩn MCP format (inputSchema, outputSchema)
- `tool_search_kb(query, top_k)` — delegate sang `retrieve_dense()` của retrieval worker
- `tool_get_ticket_info(ticket_id)` — mock ticket database (IT-9847, IT-1234, P1-LATEST alias)
- `tool_check_access_permission(access_level, requester_role, is_emergency)` — ACCESS_RULES logic
- `tool_create_ticket(priority, title, description)` — mock ticket creation với SLA calculation
- `list_tools()` / `dispatch_tool(tool_name, tool_input)` — MCP protocol interface
- `_call_mcp_tool()` trong policy_tool.py — switch giữa in-process (mock) và HTTP mode

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`dispatch_tool()` được Duy gọi qua `_call_mcp_tool()` trong `policy_tool.py`. Kết quả MCP tool call được ghi vào `mcp_tools_used` trong `AgentState` (schema do Khang định nghĩa) và hiển thị trong UI demo (app.py của Khang). Thư analyze `mcp_tools_used` field trong `eval_trace.py`.

**Bằng chứng:** Commit `5dda549 vanthuc — Refactor mcp_server.py: Update tool schemas with improved descriptions`, commit `2a85943 vanthuc — ADd mcp http server for repo`, commit `0629263 vanthuc — Fix syntax errors in mcp_server.py`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Implement `check_access_permission` với explicit emergency bypass logic per level, thay vì boolean flag đơn giản

Khi thiết kế `tool_check_access_permission()`, tôi cần quyết định cách xử lý emergency cases. Cách đơn giản nhất là: nếu `is_emergency=True`, return `can_grant=True`. Nhưng đọc kỹ `data/docs/access_control_sop.txt`, tôi thấy rules phức tạp hơn: Level 2 có emergency bypass, Level 3 và 4 thì không.

**Các lựa chọn thay thế:**
- Boolean global emergency override (đơn giản): miss sự khác biệt giữa Level 2 vs Level 3
- Per-level rule table (đã chọn): chính xác, testable, đồng bộ với SOP doc
- Gọi LLM để interpret SOP: over-engineering, không cần thiết khi rule đã explicit

**Phương án đã chọn:**

```python
ACCESS_RULES: Dict[int, Dict[str, Any]] = {
    2: {
        "emergency_can_bypass": True,
        "emergency_bypass_note": "Level 2 có emergency bypass — On-call IT Admin có thể cấp tạm thời (max 24h) sau khi được Tech Lead phê duyệt.",
    },
    3: {
        "emergency_can_bypass": False,
        "notes": ["Level 3 KHÔNG có emergency bypass — phải follow quy trình chuẩn đủ 3 approvers."],
    },
}
```

**Trade-off đã chấp nhận:** Rules hardcoded trong Python dict — nếu SOP thay đổi phải sửa code. Chấp nhận vì đây là lab với docs cố định; production cần load từ config file.

**Bằng chứng từ trace/code:**

```
# Trace q13 (Level 3 emergency):
MCP check_access_permission(level=3, role=contractor, is_emergency=True)
→ emergency_override: False
→ notes: ["Level 3 KHÔNG có emergency bypass theo SOP. Phải follow 3 approvers."]
→ required_approvers: [Line Manager, IT Admin, IT Security]

# Trace q15 (Level 2 emergency):  
MCP check_access_permission(level=2, role=contractor, is_emergency=True)
→ emergency_override: True
→ notes: ["Level 2 có emergency bypass — max 24h sau Tech Lead approval."]
confidence: 0.82 (cao nhất trong multi-hop cases)
```

Hai câu q13 và q15 đều route và answer đúng nhờ `emergency_override` field phân biệt rõ Level 2 vs Level 3.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Import error trong `mcp_server.py` — `_file_` thay vì `__file__`

**Symptom:**

Khi chạy `python mcp_server.py` hoặc khi policy_tool.py import `from mcp_server import dispatch_tool`:
```
NameError: name '_file_' is not defined
```

Tool `search_kb` luôn trả về `{"chunks": [], "error": "search_kb failed: name '_file_' is not defined"}`.

**Root cause:**

Trong function `tool_search_kb()`, code cần resolve project root để import `workers.retrieval`:
```python
# Sai:
sys.path.insert(0, os.path.dirname(os.path.abspath(_file_)))
# Đúng:
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

Python magic variable là `__file__` (hai dấu gạch dưới mỗi bên), không phải `_file_` (một dấu gạch dưới). Lỗi này không bị bắt ở import time vì function chỉ chạy khi `search_kb` được gọi thực sự.

**Cách sửa:**

```python
def tool_search_kb(query: str, top_k: int = 3) -> dict:
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # __file__ đúng
        from workers.retrieval import retrieve_dense
        ...
```

**Bằng chứng trước/sau:**

Trước: Commit `0629263 — Fix syntax errors in mcp_server.py: Correct import statement and main guard`. MCP smoke test `python mcp_server.py` → test `search_kb` trả `total_found: 0, error: NameError`.

Sau: `search_kb` delegate thành công sang `retrieve_dense()`, trả đúng chunks từ ChromaDB. Trace q13 và q15 có `mcp_tools_used: ["check_access_permission", "get_ticket_info"]` — nếu `search_kb` vẫn lỗi, pipeline cũng không ổn định.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Thiết kế MCP interface rõ ràng với `dispatch_tool()` không raise exception — luôn trả `dict` với `{"error": ...}` thay vì crash. Điều này bảo vệ pipeline: nếu MCP tool fail, policy_tool_worker vẫn tiếp tục với `mcp_result["output"] = None`, và synthesis vẫn chạy được (có thể với ít context hơn). Không có một câu nào trong 15 test questions fail do MCP error.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

`mcp_http_server.py` là bonus nhưng chưa có integration test end-to-end với `MCP_SERVER_MODE=http`. Tôi chỉ test HTTP server standalone với curl, không test qua pipeline thực tế với policy_tool.py. Nếu có thêm thời gian, tôi sẽ viết test case so sánh kết quả mock mode vs http mode.

**Nhóm phụ thuộc vào tôi ở đâu?**

Câu q03, q13, q15 (multi-hop với access check) phụ thuộc vào `check_access_permission` trả đúng `emergency_override` field. Nếu logic này sai, synthesis sẽ đưa ra kết luận sai về quy trình khẩn cấp.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần Duy implement `retrieve_dense()` trong `workers/retrieval.py` trước để `tool_search_kb()` có gì để delegate. Và cần Khang định nghĩa `AgentState.mcp_tools_used` field để kết quả MCP call được lưu đúng cách.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ implement end-to-end test cho HTTP mode: thay vì chỉ test `python mcp_server.py` standalone, tôi sẽ start `mcp_http_server.py`, set `MCP_SERVER_MODE=http` trong `.env`, chạy `python eval_trace.py` với câu q13 và q15 rồi so sánh `mcp_tools_used` output. Trace q13 hiện tại (`mcp_tools_used: ["check_access_permission", "get_ticket_info"]`) sẽ là baseline. HTTP mode phải cho cùng kết quả — đây là regression test đơn giản nhất để validate bonus feature.

---
