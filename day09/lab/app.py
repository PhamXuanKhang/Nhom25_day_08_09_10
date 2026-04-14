"""
app.py — Streamlit Demo: Multi-Agent Orchestration (Day 09 Lab)

Chạy:
    streamlit run app.py

Yêu cầu:
    pip install streamlit
    OPENAI_API_KEY đã set trong .env
    python setup_index.py đã chạy (ChromaDB index phải có)
"""

import sys
import os
import json
import time
from pathlib import Path

# ── Thêm project root vào sys.path ──
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Load .env ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import streamlit as st

# ─────────────────────────────────────────────
# Page config — phải gọi đầu tiên
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Multi-Agent Helpdesk — Day 09",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CSS — light theme clean
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
html, body, [data-testid="stAppViewContainer"] {
    background: #f8f9fb;
    color: #1a1a2e;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e5e7eb;
}

/* ── Header strip ── */
.hero-banner {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    padding: 28px 32px;
    border-radius: 12px;
    margin-bottom: 24px;
    color: white;
}
.hero-banner h1 { margin: 0; font-size: 1.7rem; font-weight: 700; }
.hero-banner p  { margin: 6px 0 0; opacity: 0.85; font-size: 0.95rem; }

/* ── Agent pipeline diagram ── */
.pipeline-row {
    display: flex;
    align-items: center;
    gap: 0;
    margin: 10px 0;
    flex-wrap: wrap;
}
.pipeline-node {
    background: #eff6ff;
    border: 2px solid #bfdbfe;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 0.82rem;
    font-weight: 600;
    color: #1e40af;
    white-space: nowrap;
}
.pipeline-node.active {
    background: #dbeafe;
    border-color: #3b82f6;
    color: #1d4ed8;
    box-shadow: 0 0 0 3px #bfdbfe;
}
.pipeline-node.policy  { background:#f0fdf4; border-color:#86efac; color:#166534; }
.pipeline-node.policy.active { box-shadow: 0 0 0 3px #bbf7d0; }
.pipeline-node.synthesis { background:#fdf4ff; border-color:#d8b4fe; color:#6b21a8; }
.pipeline-node.synthesis.active { box-shadow: 0 0 0 3px #e9d5ff; }
.pipeline-node.hitl    { background:#fff7ed; border-color:#fed7aa; color:#c2410c; }
.pipeline-node.hitl.active { box-shadow: 0 0 0 3px #fdba74; }
.pipeline-arrow { color: #94a3b8; font-size: 1.1rem; padding: 0 4px; }

/* ── Metric card ── */
.metric-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 16px 20px;
    text-align: center;
}
.metric-card .val { font-size: 1.5rem; font-weight: 700; color: #2563eb; }
.metric-card .lbl { font-size: 0.78rem; color: #6b7280; margin-top: 2px; }

/* ── Trace panel ── */
.trace-block {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 18px 20px;
    margin-top: 10px;
}
.trace-block h4 { margin: 0 0 10px; font-size: 0.9rem; color: #374151; }
.trace-row { display:flex; gap:10px; margin:4px 0; align-items:flex-start; }
.trace-key {
    min-width: 120px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: .03em;
    padding-top: 2px;
}
.trace-val { font-size: 0.85rem; color: #111827; flex: 1; word-break: break-word; }

/* ── Route badge ── */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
}
.badge-blue   { background:#dbeafe; color:#1d4ed8; }
.badge-green  { background:#dcfce7; color:#166534; }
.badge-orange { background:#fff7ed; color:#c2410c; }
.badge-purple { background:#f3e8ff; color:#7e22ce; }
.badge-gray   { background:#f3f4f6; color:#374151; }

/* ── Chat messages ── */
.chat-user {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 12px 12px 4px 12px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.92rem;
    color: #1e40af;
}
.chat-agent {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px 12px 12px 4px;
    padding: 14px 18px;
    margin: 8px 0;
    font-size: 0.92rem;
    color: #111827;
    line-height: 1.6;
}
.chat-meta {
    font-size: 0.75rem;
    color: #9ca3af;
    margin-top: 6px;
}

/* ── Example question chips ── */
.chip-wrap { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }

/* ── Confidence bar ── */
.conf-bar-wrap { background:#f3f4f6; border-radius:99px; height:8px; overflow:hidden; margin-top:4px; }
.conf-bar { height:8px; border-radius:99px; }

/* ── Section header ── */
.section-header {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #9ca3af;
    margin: 18px 0 8px;
}

/* ── Hide Streamlit branding ── */
#MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

ROUTE_BADGE = {
    "retrieval_worker":    ("badge-blue",   "Retrieval Worker"),
    "policy_tool_worker":  ("badge-green",  "Policy Tool Worker"),
    "human_review":        ("badge-orange", "Human Review (HITL)"),
}

DIFFICULTY_BADGE = {
    "easy":   ("badge-green",  "Easy"),
    "medium": ("badge-blue",   "Medium"),
    "hard":   ("badge-orange", "Hard"),
}

CATEGORY_COLOR = {
    "SLA":                  "#dbeafe",
    "Refund":               "#fce7f3",
    "Access Control":       "#d1fae5",
    "IT Helpdesk":          "#e0e7ff",
    "HR Policy":            "#fef3c7",
    "Multi-hop":            "#ede9fe",
    "Insufficient Context": "#f3f4f6",
}

def conf_color(c: float) -> str:
    if c >= 0.75: return "#22c55e"
    if c >= 0.5:  return "#f59e0b"
    return "#ef4444"

def badge(cls: str, label: str) -> str:
    return f'<span class="badge {cls}">{label}</span>'

def worker_node(label: str, kind: str, active: bool) -> str:
    cls = kind + (" active" if active else "")
    return f'<div class="pipeline-node {cls}">{label}</div>'

def arrow() -> str:
    return '<span class="pipeline-arrow">→</span>'


@st.cache_resource(show_spinner="Đang tải pipeline...")
def load_graph():
    """Import graph một lần, cache singleton."""
    from graph import run_graph
    return run_graph


@st.cache_data(show_spinner=False)
def load_test_questions():
    path = PROJECT_ROOT / "data" / "test_questions.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def run_query(question: str) -> dict:
    """Gọi pipeline và trả về state dict."""
    run_graph = load_graph()
    return run_graph(question)


# ─────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []   # [{role, content, state}]
if "last_state" not in st.session_state:
    st.session_state.last_state = None
if "running" not in st.session_state:
    st.session_state.running = False


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🤖 Multi-Agent Helpdesk")
    st.caption("Lab Day 09 — AI in Action · VinUni")

    st.divider()

    # ── Architecture overview ──
    st.markdown('<div class="section-header">Kiến trúc hệ thống</div>', unsafe_allow_html=True)
    st.markdown("""
**Supervisor → Workers → Synthesis**

Supervisor phân tích câu hỏi và route đến đúng worker, thay vì một agent monolith phải làm tất cả.
""")

    arch_html = """
<div style="font-size:0.78rem; line-height:1.8; color:#374151;">
  <div>📥 <b>User Query</b></div>
  <div style="margin-left:16px; color:#6b7280;">↓</div>
  <div>🧠 <b>Supervisor</b> — keyword routing, risk detection</div>
  <div style="margin-left:16px; color:#6b7280;">↓ route_decision()</div>
  <div style="margin-left:16px;">
    🔍 <b>Retrieval</b> — ChromaDB dense search<br>
    ⚖️ <b>Policy Tool</b> — rule check + MCP<br>
    👤 <b>Human Review</b> — HITL (unknown errors)
  </div>
  <div style="margin-left:16px; color:#6b7280;">↓</div>
  <div>✍️ <b>Synthesis</b> — grounded LLM + citation</div>
  <div style="margin-left:16px; color:#6b7280;">↓</div>
  <div>📤 <b>Answer</b> + trace</div>
</div>
"""
    st.markdown(arch_html, unsafe_allow_html=True)

    st.divider()

    # ── Knowledge base ──
    st.markdown('<div class="section-header">Knowledge Base (5 tài liệu)</div>', unsafe_allow_html=True)
    docs = {
        "📋 policy_refund_v4.txt": "Chính sách hoàn tiền v4",
        "⏱ sla_p1_2026.txt": "SLA xử lý ticket P1",
        "🔐 access_control_sop.txt": "SOP kiểm soát quyền truy cập",
        "🖥 it_helpdesk_faq.txt": "FAQ IT Helpdesk",
        "🏖 hr_leave_policy.txt": "Chính sách nghỉ phép & remote",
    }
    for name, desc in docs.items():
        st.markdown(f"<div style='font-size:0.8rem; margin:4px 0;'>{name}<br><span style='color:#6b7280;font-size:0.73rem;'>{desc}</span></div>", unsafe_allow_html=True)

    st.divider()

    # ── MCP Tools ──
    st.markdown('<div class="section-header">MCP Tools</div>', unsafe_allow_html=True)
    mcp_tools = [
        ("🔍", "search_kb", "Tìm kiếm KB"),
        ("🎫", "get_ticket_info", "Tra cứu ticket"),
        ("🔐", "check_access_permission", "Kiểm tra quyền"),
        ("📝", "create_ticket", "Tạo ticket"),
    ]
    for icon, name, desc in mcp_tools:
        st.markdown(
            f"<div style='font-size:0.79rem;margin:3px 0;'>{icon} <b>{name}</b><br>"
            f"<span style='color:#6b7280;font-size:0.73rem;'>{desc}</span></div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.caption("Powered by OpenAI · ChromaDB · Python orchestrator")


# ─────────────────────────────────────────────
# Main layout: two columns
# ─────────────────────────────────────────────
left_col, right_col = st.columns([3, 2], gap="large")


# ══════════════════════════════════════════════
# LEFT COLUMN — Hero + Chat
# ══════════════════════════════════════════════
with left_col:
    # Hero banner
    st.markdown("""
<div class="hero-banner">
  <h1>Multi-Agent IT Helpdesk</h1>
  <p>Supervisor-Worker pattern · MCP integration · Trace & Observability · Lab Day 09</p>
</div>
""", unsafe_allow_html=True)

    # ── Why multi-agent? (collapsible) ──
    with st.expander("Tại sao Multi-Agent tốt hơn Single Agent?", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
**Single Agent (Day 08)**
- 1 LLM call xử lý tất cả
- Không có trace routing
- Lỗi khó isolate
- Dễ hallucinate khi context thiếu
""")
        with c2:
            st.markdown("""
**Multi-Agent (Day 09)**
- Supervisor route đúng worker
- Trace `route_reason` mỗi câu
- Test từng worker độc lập
- 3 lớp chống hallucination
""")
        st.info(
            "**Key insight:** Multi-agent tỏa sáng ở câu phức tạp (multi-hop, policy exception) "
            "và abstain cases. Câu đơn giản overhead nhỏ (~200ms) nhưng vẫn có routing visibility."
        )

    st.divider()

    # ── Example questions ──
    st.markdown('<div class="section-header">Câu hỏi mẫu — click để thử nhanh</div>', unsafe_allow_html=True)

    test_qs = load_test_questions()
    # Group by category, show 2 per row
    example_questions = [
        ("🔍 Retrieval đơn giản", "SLA xử lý ticket P1 là bao lâu?"),
        ("⚖️ Policy exception", "Khách hàng Flash Sale yêu cầu hoàn tiền — được không?"),
        ("🔐 Access + MCP", "Contractor cần Level 3 để fix P1 khẩn. Quy trình?"),
        ("⏳ Temporal scoping", "Đơn ngày 31/01/2026, yêu cầu hoàn tiền 07/02/2026. Áp dụng policy nào?"),
        ("👤 HITL trigger", "ERR-403-AUTH là lỗi gì và cách xử lý?"),
        ("🌙 Multi-hop", "Ticket P1 lúc 2am — escalation xảy ra thế nào và ai nhận thông báo?"),
    ]

    q_cols = st.columns(3)
    for i, (label, q) in enumerate(example_questions):
        col = q_cols[i % 3]
        with col:
            if st.button(
                label,
                key=f"ex_{i}",
                help=q,
                use_container_width=True,
            ):
                st.session_state["pending_question"] = q

    st.divider()

    # ── Chat history ──
    st.markdown('<div class="section-header">Chat</div>', unsafe_allow_html=True)

    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.markdown(
                "<div style='text-align:center; color:#9ca3af; padding:30px 0; font-size:0.88rem;'>"
                "Chưa có câu hỏi nào. Thử nhấn một câu mẫu phía trên hoặc gõ câu hỏi bên dưới."
                "</div>",
                unsafe_allow_html=True,
            )

        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="chat-user">💬 {msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                state = msg.get("state", {})
                conf = state.get("confidence", 0)
                workers = state.get("workers_called", [])
                latency = state.get("latency_ms", 0)

                route_key = state.get("supervisor_route", "retrieval_worker")
                badge_cls, badge_lbl = ROUTE_BADGE.get(route_key, ("badge-gray", route_key))

                st.markdown(
                    f'<div class="chat-agent">'
                    f'{msg["content"]}'
                    f'<div class="chat-meta">'
                    f'{badge(badge_cls, badge_lbl)} &nbsp;'
                    f'Workers: {" → ".join(workers)} &nbsp;|&nbsp; '
                    f'Confidence: {conf:.0%} &nbsp;|&nbsp; '
                    f'{latency}ms'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Input box ──
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Câu hỏi của bạn",
            placeholder="VD: SLA ticket P1 là bao lâu? hoặc Contractor cần Level 3 access...",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Gửi", use_container_width=True, type="primary")

    # Xử lý pending question từ example buttons
    if "pending_question" in st.session_state and st.session_state["pending_question"]:
        user_input = st.session_state.pop("pending_question")
        submitted = True

    if submitted and user_input and user_input.strip():
        question = user_input.strip()
        st.session_state.messages.append({"role": "user", "content": question})

        with st.spinner("Đang xử lý qua pipeline multi-agent..."):
            try:
                t0 = time.time()
                state = run_query(question)
                elapsed = time.time() - t0

                answer = state.get("final_answer", "")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "state": state,
                })
                st.session_state.last_state = state

            except Exception as e:
                err_msg = f"Lỗi khi chạy pipeline: {e}"
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": err_msg,
                    "state": {},
                })
                st.session_state.last_state = None
                st.error(err_msg)

        st.rerun()

    # Clear chat button
    if st.session_state.messages:
        if st.button("Xóa lịch sử chat", use_container_width=False):
            st.session_state.messages = []
            st.session_state.last_state = None
            st.rerun()


# ══════════════════════════════════════════════
# RIGHT COLUMN — Live Trace + System Info
# ══════════════════════════════════════════════
with right_col:
    st.markdown('<div class="section-header">Pipeline Trace</div>', unsafe_allow_html=True)

    state = st.session_state.last_state

    if state is None:
        # Placeholder khi chưa có câu hỏi
        st.markdown("""
<div class="trace-block" style="text-align:center; padding:40px 20px; color:#9ca3af;">
  <div style="font-size:2rem; margin-bottom:10px;">🔍</div>
  <div style="font-size:0.88rem;">
    Trace sẽ hiển thị ở đây sau khi bạn gửi câu hỏi đầu tiên.
  </div>
</div>
""", unsafe_allow_html=True)
    else:
        # ── Pipeline visualization ──
        route_key = state.get("supervisor_route", "retrieval_worker")
        workers_called = state.get("workers_called", [])
        hitl = state.get("hitl_triggered", False)
        has_policy = "policy_tool_worker" in workers_called

        def is_active(name: str) -> bool:
            return name in workers_called or (name == "supervisor" and bool(workers_called))

        pipeline_html = f"""
<div style="margin-bottom:14px;">
  <div style="font-size:0.78rem; font-weight:600; color:#6b7280; margin-bottom:8px;">PIPELINE EXECUTION</div>
  <div class="pipeline-row">
    {worker_node("📥 User", "", False)}
    {arrow()}
    {worker_node("🧠 Supervisor", "", is_active("supervisor"))}
    {arrow()}
"""
        if hitl:
            pipeline_html += f"""
    {worker_node("👤 HITL", "hitl", True)}
    {arrow()}
"""
        if has_policy:
            pipeline_html += f"""
    {worker_node("🔍 Retrieval", "", is_active("retrieval_worker"))}
    {arrow()}
    {worker_node("⚖️ Policy Tool", "policy", is_active("policy_tool_worker"))}
    {arrow()}
"""
        else:
            pipeline_html += f"""
    {worker_node("🔍 Retrieval", "", is_active("retrieval_worker"))}
    {arrow()}
"""

        pipeline_html += f"""
    {worker_node("✍️ Synthesis", "synthesis", is_active("synthesis_worker"))}
    {arrow()}
    {worker_node("📤 Answer", "", False)}
  </div>
</div>
"""
        st.markdown(pipeline_html, unsafe_allow_html=True)

        # ── Key metrics row ──
        conf = state.get("confidence", 0)
        latency = state.get("latency_ms", 0)
        mcp_calls = len(state.get("mcp_tools_used", []))
        chunks = state.get("retrieved_chunks", [])

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Confidence", f"{conf:.0%}", delta=None)
        with m2:
            st.metric("Latency", f"{latency}ms")
        with m3:
            st.metric("MCP calls", mcp_calls)
        with m4:
            st.metric("Chunks", len(chunks))

        # ── Routing detail ──
        route_cls, route_lbl = ROUTE_BADGE.get(route_key, ("badge-gray", route_key))
        st.markdown(f"""
<div class="trace-block">
  <h4>Supervisor Decision</h4>
  <div class="trace-row">
    <div class="trace-key">Route</div>
    <div class="trace-val">{badge(route_cls, route_lbl)}</div>
  </div>
  <div class="trace-row">
    <div class="trace-key">Reason</div>
    <div class="trace-val">{state.get("route_reason", "—")}</div>
  </div>
  <div class="trace-row">
    <div class="trace-key">Risk High</div>
    <div class="trace-val">{badge("badge-orange", "YES") if state.get("risk_high") else badge("badge-gray", "no")}</div>
  </div>
  <div class="trace-row">
    <div class="trace-key">Needs Tool</div>
    <div class="trace-val">{badge("badge-purple", "YES") if state.get("needs_tool") else badge("badge-gray", "no")}</div>
  </div>
  <div class="trace-row">
    <div class="trace-key">HITL</div>
    <div class="trace-val">{badge("badge-orange", "TRIGGERED") if hitl else badge("badge-gray", "no")}</div>
  </div>
  <div class="trace-row">
    <div class="trace-key">Workers</div>
    <div class="trace-val">{" → ".join(workers_called) or "—"}</div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── Confidence bar ──
        ccolor = conf_color(conf)
        st.markdown(f"""
<div style="margin-top:10px;">
  <div style="font-size:0.78rem; color:#6b7280; font-weight:600; margin-bottom:4px;">CONFIDENCE</div>
  <div class="conf-bar-wrap">
    <div class="conf-bar" style="width:{conf*100:.0f}%; background:{ccolor};"></div>
  </div>
  <div style="font-size:0.75rem; color:{ccolor}; margin-top:3px; text-align:right;">{conf:.0%}</div>
</div>
""", unsafe_allow_html=True)

        # ── Retrieved chunks ──
        if chunks:
            with st.expander(f"Retrieved Chunks ({len(chunks)})", expanded=False):
                for i, c in enumerate(chunks, 1):
                    score = c.get("score", 0)
                    sc = conf_color(score)
                    st.markdown(
                        f"**[{i}] {c.get('source', '?')}** "
                        f"<span style='color:{sc};font-size:0.8rem;'>[score {score:.3f}]</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(c.get("text", "")[:300] + ("..." if len(c.get("text","")) > 300 else ""))
        else:
            st.markdown(
                '<div style="font-size:0.82rem;color:#9ca3af;margin-top:6px;">No chunks retrieved.</div>',
                unsafe_allow_html=True,
            )

        # ── MCP tools used ──
        mcp_used = state.get("mcp_tools_used", [])
        if mcp_used:
            with st.expander(f"MCP Tool Calls ({len(mcp_used)})", expanded=True):
                for call in mcp_used:
                    tool = call.get("tool", "?")
                    err = call.get("error")
                    out = call.get("output") or {}
                    status_html = '<span style="color:#ef4444;">ERROR</span>' if err else '<span style="color:#22c55e;">OK</span>'
                    st.markdown(
                        f"**{tool}** {status_html}",
                        unsafe_allow_html=True,
                    )
                    with st.container():
                        if err:
                            st.error(err.get("reason", str(err)))
                        else:
                            # Show compact summary of output
                            if tool == "check_access_permission":
                                ac = out
                                st.markdown(
                                    f"Level {ac.get('access_level')} · "
                                    f"can_grant=**{ac.get('can_grant')}** · "
                                    f"emergency_override=**{ac.get('emergency_override')}**  \n"
                                    f"Approvers: {', '.join(ac.get('required_approvers', []))}"
                                )
                                for note in ac.get("notes", []):
                                    st.caption(f"• {note}")
                            elif tool == "get_ticket_info":
                                ti = out
                                st.markdown(
                                    f"Ticket **{ti.get('ticket_id')}** · "
                                    f"Priority **{ti.get('priority')}** · "
                                    f"Status {ti.get('status')}"
                                )
                            elif tool == "search_kb":
                                st.markdown(f"Found {out.get('total_found', 0)} chunks")
                            else:
                                st.json(out, expanded=False)
                    st.divider()

        # ── Policy result ──
        policy_result = state.get("policy_result", {})
        if policy_result:
            with st.expander("Policy Analysis", expanded=False):
                st.markdown(f"**Policy applies:** {'✅' if policy_result.get('policy_applies') else '❌'}")
                if policy_result.get("policy_version_note"):
                    st.warning(policy_result["policy_version_note"])
                exceptions = policy_result.get("exceptions_found", [])
                if exceptions:
                    for ex in exceptions:
                        st.error(f"**{ex.get('type')}**: {ex.get('rule', '')}")
                if policy_result.get("access_check"):
                    st.markdown("**Access check included** (see MCP calls above)")

        # ── Raw sources cited ──
        sources = state.get("sources", [])
        if sources:
            st.markdown(
                '<div style="font-size:0.78rem; color:#6b7280; font-weight:600; margin-top:14px;">SOURCES CITED</div>',
                unsafe_allow_html=True,
            )
            for s in sources:
                st.markdown(
                    f'<span style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:4px;'
                    f'padding:2px 8px;font-size:0.8rem;margin-right:4px;color:#0369a1;">{s}</span>',
                    unsafe_allow_html=True,
                )

        # ── Full trace JSON (collapsed) ──
        with st.expander("Full Trace JSON", expanded=False):
            # Filter out large binary fields for display
            display_state = {
                k: v for k, v in state.items()
                if k not in ("worker_io_logs",)
            }
            st.json(display_state)

    st.divider()

    # ── System info ── (always visible)
    st.markdown('<div class="section-header">Thông tin hệ thống</div>', unsafe_allow_html=True)
    api_ok = bool(os.getenv("OPENAI_API_KEY")) and not os.getenv("OPENAI_API_KEY", "").startswith("sk-...your")
    chroma_ok = (PROJECT_ROOT / "chroma_db").exists()
    embed_model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    llm_model   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    status_rows = [
        ("OpenAI API Key", "✅ Set" if api_ok else "❌ Chưa set — cần thêm vào .env"),
        ("ChromaDB index", "✅ Sẵn sàng" if chroma_ok else "❌ Chưa có — chạy setup_index.py"),
        ("Embedding model", embed_model),
        ("LLM model", llm_model),
        ("MCP mode", os.getenv("MCP_SERVER_MODE", "mock")),
    ]
    rows_html = "".join(
        f'<div class="trace-row"><div class="trace-key">{k}</div><div class="trace-val">{v}</div></div>'
        for k, v in status_rows
    )
    st.markdown(f'<div class="trace-block">{rows_html}</div>', unsafe_allow_html=True)

    if not api_ok:
        st.warning("Cần OPENAI_API_KEY trong .env để chạy pipeline đầy đủ.")
    if not chroma_ok:
        st.warning("Chưa có ChromaDB index. Chạy `python setup_index.py` trước.")


# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding:20px 0 8px; font-size:0.75rem; color:#9ca3af;">
  Lab Day 09 · AI in Action (AICB-P1) · VinUni · 2026-04-14
  &nbsp;·&nbsp; Supervisor-Worker · MCP · Trace Observability
</div>
""", unsafe_allow_html=True)
