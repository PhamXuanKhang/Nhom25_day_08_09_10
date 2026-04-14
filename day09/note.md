# Phân công vai trò — Day 09 Lab Multi-Agent Orchestration

> Tài liệu này chia rõ từng **role** chịu trách nhiệm những file/function nào,
> để các thành viên commit riêng biệt (tách tác giả theo `git blame` / commit author),
> và để báo cáo cá nhân khớp với code thực tế (tránh phạt `0/40` vì report mismatch).

---

## Tổng quan 4 role

| Role | Sprint lead | File chính | File phụ |
|------|-------------|------------|----------|
| **Supervisor Owner** | Sprint 1 | `graph.py` | `contracts/worker_contracts.yaml` (section `supervisor`) |
| **Worker Owner** | Sprint 2 | `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py` | `contracts/worker_contracts.yaml` (3 worker sections), `setup_index.py` |
| **MCP Owner** | Sprint 3 | `mcp_server.py`, `mcp_http_server.py` | `contracts/worker_contracts.yaml` (section `mcp_server`), phần `_call_mcp_tool` trong `policy_tool.py` |
| **Trace & Docs Owner** | Sprint 4 | `eval_trace.py`, `docs/*.md`, `reports/group_report.md` | `artifacts/traces/*`, `artifacts/grading_run.jsonl`, `artifacts/eval_report.json` |

---

## Chi tiết phân công

### 🟦 Role 1 — Supervisor Owner (Sprint 1)

**File bạn sở hữu 100%:**
- `graph.py` — toàn bộ file

**Function bạn implement:**
- `AgentState` TypedDict — schema state dùng chung
- `make_initial_state(task)` — khởi tạo state
- `supervisor_node(state)` — đọc task, quyết định route + `route_reason` + `risk_high` + `needs_tool`
- `route_decision(state)` — conditional edge (chỉ trả tên worker)
- `human_review_node(state)` — HITL placeholder (auto-approve trong lab mode)
- `build_graph()` — orchestrator logic (if/else hoặc LangGraph)
- `run_graph(task)` — public entry point
- `save_trace(state, output_dir)` — ghi trace ra JSON

**Contract section bạn cập nhật:**
- `contracts/worker_contracts.yaml` → block `supervisor` (routing rules + constraints)

**Không được động vào:**
- Nội dung các `workers/*.py` (chỉ import `run` function)
- `mcp_server.py`
- `eval_trace.py`

**Commit pattern (gợi ý):**
```
[sprint1] supervisor: implement supervisor_node routing
[sprint1] supervisor: add human_review HITL node
[sprint1] supervisor: improve route_reason logging
```

---

### 🟩 Role 2 — Worker Owner (Sprint 2)

**File bạn sở hữu 100%:**
- `workers/retrieval.py`
- `workers/policy_tool.py` (phần `analyze_policy` + `run`, KHÔNG phần `_call_mcp_tool` — MCP Owner sở hữu)
- `workers/synthesis.py`
- `setup_index.py` (script indexing ChromaDB)

**Function bạn implement:**

*retrieval.py:*
- `_get_embedding_fn()` — fallback chain: SentenceTransformer → OpenAI → random
- `_get_collection()` — kết nối ChromaDB persistent client
- `retrieve_dense(query, top_k)` — embed + query + format chunks
- `run(state)` — entry point, đọc `task`, ghi `retrieved_chunks` + `retrieved_sources` + `worker_io_logs`

*policy_tool.py:*
- `analyze_policy(task, chunks)` — rule-based exception detection (flash_sale, digital_product, activated, temporal_scoping v3/v4)
- `_check_access_question(task)` — detect câu hỏi về access level → dispatch MCP `check_access_permission`
- `run(state)` — entry point

*synthesis.py:*
- `_call_llm(messages)` — OpenAI / Gemini / fallback không hallucinate
- `_build_context(chunks, policy_result)` — format context string
- `_estimate_confidence(chunks, answer, policy_result)` — công thức confidence
- `synthesize(task, chunks, policy_result)` — tổng hợp
- `run(state)` — entry point

**Contract section bạn cập nhật:**
- `contracts/worker_contracts.yaml` → blocks `retrieval_worker`, `policy_tool_worker`, `synthesis_worker`

**Commit pattern (gợi ý):**
```
[sprint2] retrieval: implement dense retrieval with ChromaDB
[sprint2] policy: implement rule-based exception detection
[sprint2] synthesis: wire OpenAI/Gemini fallback with grounded prompt
[sprint2] setup: add ChromaDB indexing script
```

---

### 🟨 Role 3 — MCP Owner (Sprint 3)

**File bạn sở hữu 100%:**
- `mcp_server.py` — toàn bộ
- `mcp_http_server.py` — (bonus +2) real HTTP server với FastAPI

**Phần trong file của người khác bạn được phép chỉnh:**
- `workers/policy_tool.py` → **chỉ** function `_call_mcp_tool(...)` và các điểm gọi MCP trong `run(state)` (import mcp_server, dispatch qua HTTP hoặc in-process)

**Function bạn implement:**
- `TOOL_SCHEMAS` — 4 tool schemas đúng MCP format
- `tool_search_kb(query, top_k)` — wrap retrieval
- `tool_get_ticket_info(ticket_id)` — mock ticket DB (IT-9847 P1-LATEST, IT-1234)
- `tool_check_access_permission(level, role, is_emergency)` — ACCESS_RULES logic
- `tool_create_ticket(priority, title, description)` — mock create
- `list_tools()` — MCP discovery
- `dispatch_tool(tool_name, tool_input)` — MCP execution
- `mcp_http_server.py` (bonus): FastAPI app expose `/tools/list` và `/tools/call`

**Contract section bạn cập nhật:**
- `contracts/worker_contracts.yaml` → block `mcp_server`

**Commit pattern (gợi ý):**
```
[sprint3] mcp: implement 4 tools + dispatcher
[sprint3] mcp: wire policy_tool to dispatch_tool
[sprint3] mcp: add FastAPI HTTP server (bonus)
```

---

### 🟪 Role 4 — Trace & Docs Owner (Sprint 4)

**File bạn sở hữu 100%:**
- `eval_trace.py` — toàn bộ
- `docs/system_architecture.md` — điền template
- `docs/routing_decisions.md` — điền template sau khi có trace
- `docs/single_vs_multi_comparison.md` — điền template
- `reports/group_report.md` — viết sau 18:00

**Function bạn implement trong `eval_trace.py`:**
- `run_test_questions(questions_file)` — chạy 15 câu hỏi, save trace
- `run_grading_questions(questions_file)` — chạy grading, xuất JSONL
- `analyze_traces(traces_dir)` — tính routing_distribution, avg_confidence, v.v.
- `compare_single_vs_multi(multi_traces_dir, day08_file)` — so sánh với baseline Day 08
- `save_eval_report(comparison)` — ghi `artifacts/eval_report.json`
- CLI: `--grading`, `--analyze`, `--compare`

**Artifact bạn tạo:**
- `artifacts/traces/*.json` — mỗi câu hỏi một file
- `artifacts/grading_run.jsonl` — log chính thức để giảng viên chấm
- `artifacts/eval_report.json` — so sánh Day 08 vs Day 09

**Không được động vào:**
- Code workers, supervisor, MCP (chỉ gọi qua `run_graph`)

**Commit pattern (gợi ý):**
```
[sprint4] eval: implement run_grading + analyze + compare
[sprint4] docs: fill system_architecture
[sprint4] docs: fill routing_decisions from trace
[sprint4] docs: fill single_vs_multi comparison
[report] group_report: fill sections 1-6
```

---

## Quy tắc tránh xung đột

1. **Không sửa file của role khác** — nếu cần, tạo PR nhỏ và tag owner.
2. **`contracts/worker_contracts.yaml` là file shared** — mỗi role chỉ sửa section của mình, commit riêng để `git blame` khớp.
3. **Mỗi commit phải có prefix role/sprint** (`[sprint1]`, `[sprint2]`, `[sprint3]`, `[sprint4]`, `[report]`).
4. **Individual report**: từng người mô tả đúng phần mình làm, không overlap. Nếu nhóm chỉ có 2 người, 1 người nên khai `Supervisor+Worker Owner` và người kia `MCP+Trace+Docs Owner`.

---

## Checklist đi cùng cho mỗi role trước 18:00

### Supervisor Owner
- [ ] `python graph.py` chạy 3 test queries không lỗi
- [ ] Mỗi query có `route_reason` không rỗng, không là `"unknown"`
- [ ] HITL node trigger được với câu có `err-` + risk keyword
- [ ] Trace có đủ fields: `supervisor_route`, `route_reason`, `workers_called`, `latency_ms`

### Worker Owner
- [ ] `python workers/retrieval.py` → có ít nhất 1 chunk cho mỗi query
- [ ] `python workers/policy_tool.py` → detect được Flash Sale + digital product exceptions
- [ ] `python workers/synthesis.py` → trả về answer có citation `[source]`, không hallucinate
- [ ] `python setup_index.py` → ChromaDB có ≥ 5 documents indexed

### MCP Owner
- [ ] `python mcp_server.py` → 4 tools listed, 3 test calls pass
- [ ] Trace có `mcp_tools_used` non-empty cho ít nhất câu q03, q13, q15
- [ ] (Bonus) `python mcp_http_server.py` → HTTP endpoint trả JSON đúng MCP format

### Trace & Docs Owner
- [ ] `python eval_trace.py` chạy 15 test questions, tạo 15 trace files
- [ ] `python eval_trace.py --grading` (sau 17:00) tạo `grading_run.jsonl` với ≥ 10 records
- [ ] `python eval_trace.py --compare` tạo `eval_report.json`
- [ ] 3 file docs điền đầy đủ, không còn `_________________`

---

*File này do Trace & Docs Owner maintain. Cập nhật khi phân công thay đổi.*
