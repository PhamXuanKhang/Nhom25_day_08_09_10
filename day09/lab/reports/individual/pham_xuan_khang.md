# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Phạm Xuân Khang  
**Vai trò trong nhóm:** Supervisor Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi chịu trách nhiệm toàn bộ Sprint 1 — thiết kế và implement Supervisor Orchestrator trong `graph.py`. Đây là file điều phối trung tâm của hệ thống: nhận query từ user, quyết định worker nào được gọi, và orchestrate toàn bộ luồng xử lý.

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py` — toàn bộ
- File phụ: `setup_index.py` (viết lại hoàn toàn để dùng OpenAI batch embedding), `app.py` (Streamlit demo UI)

**Functions tôi implement:**
- `AgentState` TypedDict (18 fields — schema state dùng chung toàn hệ thống)
- `supervisor_node(state)` — keyword matching + 2 override rules
- `route_decision(state)` — conditional edge trả tên worker
- `human_review_node(state)` — HITL checkpoint (auto-approve lab mode)
- `build_graph()` / `run_graph(task)` / `save_trace(state)`
- `embed_batch()` trong `setup_index.py` — OpenAI batch API, sort by `.index`

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`supervisor_node` set `needs_tool=True` để báo cho policy_tool_worker (Duy) gọi MCP tools (Thức). `route_reason` trong trace được Thư dùng để phân tích routing accuracy trong `eval_trace.py`.

**Bằng chứng:** Commit `305044b PhamXuanKhang — Update .gitignore, enhance README, and add setup_index script`, commit `50e3bbc PhamXuanKhang — Refactor code structure for improved readability and maintainability`, commit `b80026e PhamXuanKhang — Enhance eval_trace.py`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Thiết kế keyword routing với 2-tier override rules thay vì gọi LLM để classify

Khi implement `supervisor_node`, tôi đứng trước lựa chọn: (1) gọi gpt-4o-mini để phân tích intent, hoặc (2) dùng 3 bảng keyword + 2 override rules cứng.

**Các lựa chọn thay thế:**
- LLM classifier: semantic understanding tốt hơn, nhưng thêm 800-1200ms và 1 API call trước khi pipeline thậm chí bắt đầu
- Pure keyword: ~5ms, deterministic, dễ audit

Tôi chọn keyword routing vì scope 5 domain docs có vocabulary ổn định, và quan trọng hơn là **predictability**: với LLM classifier, nhóm không thể đảm bảo trace luôn có `route_reason` explainable — nếu LLM trả lời sai, debug rất khó.

Override rule quan trọng nhất là `err-` pattern → force `human_review`. Tôi quyết định dùng string check `UNKNOWN_ERROR_PATTERN = "err-"` thay vì regex phức tạp vì trong 5 docs hiện tại, không có section nào dùng "err-" làm keyword hợp lệ — false positive rate = 0%.

**Trade-off đã chấp nhận:** Miss rate khi câu diễn đạt khác (VD: "mã lỗi 403" thay vì "ERR-403"). Chấp nhận được vì scope cố định.

**Bằng chứng từ trace/code:**

```python
# graph.py:108
UNKNOWN_ERROR_PATTERN = "err-"

# graph.py:144-146
if UNKNOWN_ERROR_PATTERN in task:
    route = "human_review"
    reasons.append("unknown error code detected → human_review")
    risk_high = True

# Kết quả trace q09 (ERR-403-AUTH):
# route_reason: "no specific keyword → default retrieval_worker | 
#                risk signals: ['err-'] | unknown error code detected → human_review"
# hitl_triggered: true
# abstain: true
# confidence: 0.44 (thấp — đúng, vì không có evidence)
```

Route accuracy toàn bộ 15 câu = 93.3% (14/15). Câu sai duy nhất (q02) vẫn cho answer đúng.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Python 3.9 f-string backslash syntax error trong `app.py`

**Symptom:**

Khi chạy `streamlit run app.py`, gặp ngay:
```
SyntaxError: f-string expression part cannot include a backslash (app.py, line 661)
```
Pipeline không start được.

**Root cause:**

Python 3.9 không cho phép backslash bên trong expression của f-string. Code bị lỗi:
```python
f"{'<span style=\"color:#ef4444;\">ERROR</span>' if err else '<span style=\"color:#22c55e;\">OK</span>'}"
```
Trong Python 3.12 điều này được fix, nhưng environment đang dùng Python 3.9.

**Cách sửa:**

Extract conditional expression ra biến trước, sau đó embed biến vào f-string:

```python
# Trước (lỗi):
st.markdown(
    f"**{tool}** {'<span style=\"color:#ef4444;\">ERROR</span>' if err else '<span>OK</span>'}",
    unsafe_allow_html=True
)

# Sau (đúng):
status_html = '<span style="color:#ef4444;">ERROR</span>' if err else '<span style="color:#22c55e;">OK</span>'
st.markdown(f"**{tool}** {status_html}", unsafe_allow_html=True)
```

**Bằng chứng trước/sau:**

Trước: `SyntaxError` ngay khi import, app không load được.  
Sau: `python -c "import ast; ast.parse(open('app.py').read()); print('OK')"` → `syntax OK, lines: 765`.

Lỗi này minh họa rõ tầm quan trọng của việc test syntax trên đúng Python version — code viết trên 3.12 nhưng deploy trên 3.9 sẽ fail silent cho đến runtime.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Thiết kế `AgentState` TypedDict và `route_reason` format. Việc định nghĩa rõ 18 fields với type annotation từ đầu giúp các member khác (Duy, Thức, Thư) implement worker của mình mà không cần hỏi "output cần format thế nào". `route_reason` dạng `signal1 | signal2 | override` giúp Thư analyze traces trong `eval_trace.py` chỉ bằng string split.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Quyết định embedding model quá muộn — ban đầu `setup_index.py` dùng SentenceTransformer local, sau đó mới migrate sang OpenAI. Điều này bắt Duy phải update `retrieval.py` lần 2 để sync embedding model. Nếu tôi confirm stack sớm hơn (trước Sprint 2 bắt đầu), nhóm tiết kiệm được ~1 giờ refactor.

**Nhóm phụ thuộc vào tôi ở đâu?**

`AgentState` schema và `run_graph()` entry point — không có 2 thứ này, Thư không thể implement `eval_trace.py` và test end-to-end.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần `workers/retrieval.run()`, `policy_tool.run()`, `synthesis.run()` từ Duy để `build_graph()` có gì để gọi. Và cần `mcp_server.dispatch_tool()` từ Thức để policy_tool_worker gọi MCP tools.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ thêm **supervisor confidence score** vào routing. Trace câu q02 cho thấy câu "hoàn tiền trong bao nhiêu ngày" bị route sang `policy_tool_worker` (sai — đây là câu retrieval đơn giản), vì keyword "hoàn tiền" match `POLICY_KEYWORDS`. Nếu supervisor có `supervisor_confidence` field (VD: 0.6 khi có 1 keyword hit vs 0.95 khi có 3+ keyword hits), nhóm có thể thêm LLM fallback cho uncertain cases (confidence < 0.7) mà không tăng latency cho majority cases.

---

*Lưu file này với tên: `reports/individual/pham_xuan_khang.md`*
