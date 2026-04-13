"""
app.py — Streamlit Demo: RAG Chatbot (Day 08 Lab)
==================================================
Giao diện hỏi-đáp dựa trên pipeline RAG đã xây dựng.
Chạy: streamlit run app.py
"""

import sys
import os
from pathlib import Path

# Đảm bảo import được index.py và rag_answer.py từ cùng thư mục
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="RAG Chatbot — CS/IT Helpdesk",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# CSS
# =============================================================================

st.markdown("""
<style>
/* Main background — white */
.stApp { background-color: #ffffff; }

/* Sidebar background */
section[data-testid="stSidebar"] { background-color: #f8fafc; }

/* Chat message bubbles */
.user-bubble {
    background: #eff6ff;
    border-left: 3px solid #2563eb;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #1e3a5f;
}
.assistant-bubble {
    background: #f0fdf4;
    border-left: 3px solid #16a34a;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #14532d;
}

/* Source badge */
.source-badge {
    display: inline-block;
    background: #dbeafe;
    color: #1d4ed8;
    border: 1px solid #93c5fd;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 12px;
    margin: 2px 3px;
}

/* Chunk card */
.chunk-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 13px;
    color: #374151;
}
.chunk-header {
    color: #1d4ed8;
    font-weight: 600;
    margin-bottom: 4px;
    font-size: 12px;
}
.score-badge {
    float: right;
    background: #dcfce7;
    color: #15803d;
    border: 1px solid #86efac;
    border-radius: 4px;
    padding: 1px 7px;
    font-size: 11px;
}

/* Input area */
.stTextArea textarea {
    background: #ffffff !important;
    color: #111827 !important;
    border: 1px solid #d1d5db !important;
}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.markdown("## ⚙️ Cấu hình Pipeline")

    retrieval_mode = st.selectbox(
        "Retrieval Strategy",
        options=["dense", "hybrid", "sparse"],
        index=0,
        help="dense: embedding similarity | hybrid: dense + BM25 RRF | sparse: BM25 only",
    )

    top_k_search = st.slider("Top-K Search (vector store)", 3, 20, 10,
                              help="Số chunk lấy từ vector store trước khi select")
    top_k_select = st.slider("Top-K Select (vào prompt)", 1, 6, 3,
                              help="Số chunk thực sự đưa vào LLM prompt")

    st.markdown("---")
    st.markdown("### 📊 Scorecard (từ kết quả lab)")

    scores = {
        "dense":  {"Faithfulness": 4.70, "Relevance": 4.60, "Recall": 5.00, "Completeness": 3.80},
        "hybrid": {"Faithfulness": 4.10, "Relevance": 4.20, "Recall": 5.00, "Completeness": 3.40},
        "sparse": {"Faithfulness": "N/A", "Relevance": "N/A", "Recall": "N/A", "Completeness": "N/A"},
    }
    sc = scores[retrieval_mode]
    cols = st.columns(2)
    for i, (metric, val) in enumerate(sc.items()):
        with cols[i % 2]:
            if isinstance(val, float):
                color = "#15803d" if val >= 4.5 else "#b45309" if val >= 4.0 else "#dc2626"
                st.markdown(
                    f'<div style="text-align:center; padding:8px; background:#f1f5f9; '
                    f'border:1px solid #e2e8f0; border-radius:6px; margin:4px 0;">'
                    f'<div style="font-size:11px; color:#64748b;">{metric}</div>'
                    f'<div style="font-size:20px; font-weight:700; color:{color};">{val}</div>'
                    f'<div style="font-size:10px; color:#94a3b8;">/5.00</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="text-align:center; padding:8px; background:#f1f5f9; '
                    f'border:1px solid #e2e8f0; border-radius:6px; margin:4px 0;">'
                    f'<div style="font-size:11px; color:#64748b;">{metric}</div>'
                    f'<div style="font-size:18px; font-weight:700; color:#94a3b8;">{val}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")
    st.markdown("### 📚 Knowledge Base")
    st.markdown("""
<small style="color:#475569;">
• policy_refund_v4 (6 chunks)<br>
• sla_p1_2026 (5 chunks)<br>
• access_control_sop (7 chunks)<br>
• it_helpdesk_faq (6 chunks)<br>
• hr_leave_policy (5 chunks)<br>
<br>
<b style="color:#1d4ed8;">Tổng: 29 chunks</b>
</small>
""", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# =============================================================================
# HEADER
# =============================================================================

st.markdown("""
<div style="padding: 20px 0 10px 0;">
    <h1 style="margin:0; color:#111827;">🔍 RAG Chatbot</h1>
    <p style="color:#6b7280; margin:4px 0 0 0; font-size:15px;">
        CS + IT Helpdesk · Trả lời từ tài liệu nội bộ · Có citation · Abstain khi không đủ dữ liệu
    </p>
</div>
<hr style="border-color:#e5e7eb; margin:12px 0;">
""", unsafe_allow_html=True)

# =============================================================================
# QUICK QUESTIONS
# =============================================================================

st.markdown("**💡 Câu hỏi mẫu:**")
sample_qs = [
    "SLA xử lý ticket P1 là bao lâu?",
    "Khách hàng hoàn tiền trong bao nhiêu ngày?",
    "Ai phê duyệt cấp quyền Level 3?",
    "Tài khoản bị khóa sau bao nhiêu lần đăng nhập sai?",
    "Nhân viên được làm remote mấy ngày?",
    "ERR-403-AUTH là lỗi gì?",
]

q_cols = st.columns(3)
clicked_q = None
for i, q in enumerate(sample_qs):
    with q_cols[i % 3]:
        if st.button(q, key=f"sq_{i}", use_container_width=True):
            clicked_q = q

# =============================================================================
# SESSION STATE
# =============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

# =============================================================================
# CHAT DISPLAY
# =============================================================================

chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="user-bubble">👤 <b>Bạn</b><br>{msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            answer_html = msg["content"].replace("\n", "<br>")
            st.markdown(
                f'<div class="assistant-bubble">🤖 <b>RAG Bot</b><br>{answer_html}</div>',
                unsafe_allow_html=True,
            )
            # Show sources
            if msg.get("sources"):
                badges = "".join(
                    f'<span class="source-badge">📄 {s}</span>'
                    for s in msg["sources"]
                )
                st.markdown(
                    f'<div style="margin:-4px 0 8px 0;">{badges}</div>',
                    unsafe_allow_html=True,
                )
            # Show retrieved chunks in expander
            if msg.get("chunks"):
                with st.expander(f"🔎 {len(msg['chunks'])} chunk đã retrieve ({msg.get('mode', 'dense')})"):
                    for j, chunk in enumerate(msg["chunks"], 1):
                        meta = chunk.get("metadata", {})
                        score = chunk.get("score", 0)
                        source = meta.get("source", "?")
                        # Show only basename for readability
                        source_short = Path(source).stem if source != "?" else source
                        section = meta.get("section", "")
                        dept = meta.get("department", "")
                        text = chunk.get("text", "")[:400]
                        if len(chunk.get("text", "")) > 400:
                            text += "…"

                        header_parts = [f"[{j}] {source_short}"]
                        if section:
                            header_parts.append(section)
                        if dept:
                            header_parts.append(dept)

                        st.markdown(
                            f'<div class="chunk-card">'
                            f'<div class="chunk-header">'
                            f'{"  ·  ".join(header_parts)}'
                            f'<span class="score-badge">score {score:.3f}</span>'
                            f'</div>'
                            f'{text}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

# =============================================================================
# INPUT
# =============================================================================

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

with st.form("chat_form", clear_on_submit=True):
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_input = st.text_input(
            "Câu hỏi của bạn",
            placeholder="Nhập câu hỏi về chính sách hoàn tiền, SLA, quyền truy cập, nghỉ phép...",
            label_visibility="collapsed",
        )
    with col_btn:
        submitted = st.form_submit_button("Gửi ↩", use_container_width=True)

# Handle quick question click
if clicked_q:
    user_input = clicked_q
    submitted = True

# =============================================================================
# PIPELINE CALL
# =============================================================================

if submitted and user_input and user_input.strip():
    query = user_input.strip()

    # Add user message
    st.session_state.messages.append({"role": "user", "content": query})

    with st.spinner("Đang tìm kiếm và tổng hợp câu trả lời..."):
        try:
            from rag_answer import rag_answer

            result = rag_answer(
                query=query,
                retrieval_mode=retrieval_mode,
                top_k_search=top_k_search,
                top_k_select=top_k_select,
                use_rerank=False,
                verbose=False,
            )

            answer = result["answer"]
            sources = result.get("sources", [])
            chunks = result.get("chunks_used", [])

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "sources": sources,
                "chunks": chunks,
                "mode": retrieval_mode,
            })

        except Exception as e:
            err_msg = str(e)
            if "OPENAI_API_KEY" in err_msg or "api_key" in err_msg.lower():
                err_display = "❌ Thiếu OPENAI_API_KEY. Hãy thêm vào file `.env`."
            elif "rag_lab" in err_msg or "does not exist" in err_msg.lower():
                err_display = "❌ Chưa có index. Hãy chạy `python index.py` trước."
            else:
                err_display = f"❌ Lỗi: {err_msg}"

            st.session_state.messages.append({
                "role": "assistant",
                "content": err_display,
                "sources": [],
                "chunks": [],
                "mode": retrieval_mode,
            })

    st.rerun()

# =============================================================================
# FOOTER
# =============================================================================

if not st.session_state.messages:
    st.markdown("""
<div style="text-align:center; padding:40px 0;">
    <div style="font-size:48px;">🔍</div>
    <div style="margin-top:12px; font-size:16px; color:#374151;">
        Đặt câu hỏi về chính sách nội bộ<br>
        <small style="color:#6b7280;">hoàn tiền · SLA · access control · IT FAQ · nghỉ phép</small>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<hr style="border-color:#e5e7eb; margin-top:24px;">
<div style="text-align:center; font-size:11px; color:#9ca3af; padding:4px 0;">
    Day 08 Lab · RAG Pipeline · text-embedding-3-small · gpt-4o-mini · ChromaDB
</div>
""", unsafe_allow_html=True)
