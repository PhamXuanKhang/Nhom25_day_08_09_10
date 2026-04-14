"""
graph.py — Supervisor Orchestrator (Sprint 1)

Owner: Supervisor Owner

Kiến trúc:
    Input → Supervisor → [retrieval | policy_tool | human_review] → synthesis → Output

Luồng chi tiết:
    1. supervisor_node(): phân tích task, quyết định `supervisor_route`, ghi
       `route_reason`, `risk_high`, `needs_tool`.
    2. route_decision(): conditional edge dựa trên `supervisor_route`.
    3. Nếu policy_tool_worker → chạy retrieval_worker trước để có context chunks.
    4. Nếu human_review → pause (auto-approve trong lab mode) rồi chạy retrieval.
    5. synthesis_worker() chạy cuối cùng để tổng hợp câu trả lời + citation.

Chạy thử:
    python graph.py
"""

import json
import os
import time
from datetime import datetime
from typing import TypedDict, Literal, Optional

# Load .env nếu có (cho OPENAI_API_KEY, v.v.)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────
# 1. Shared State — dữ liệu đi xuyên toàn graph
# ─────────────────────────────────────────────

class AgentState(TypedDict, total=False):
    task: str
    route_reason: str
    risk_high: bool
    needs_tool: bool
    hitl_triggered: bool
    retrieved_chunks: list
    retrieved_sources: list
    policy_result: dict
    mcp_tools_used: list
    final_answer: str
    sources: list
    confidence: float
    history: list
    workers_called: list
    worker_io_logs: list
    supervisor_route: str
    latency_ms: Optional[int]
    run_id: str
    timestamp: str


def make_initial_state(task: str) -> AgentState:
    """Khởi tạo state cho một run mới."""
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "worker_io_logs": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "timestamp": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────
# 2. Supervisor Node — quyết định route
# ─────────────────────────────────────────────

# Keyword tables — tách ra module-level để dễ audit & test.
POLICY_KEYWORDS = [
    "hoàn tiền", "refund", "flash sale", "license", "subscription",
    "kỹ thuật số", "đã kích hoạt", "cấp quyền", "access level",
    "level 1", "level 2", "level 3", "level 4", "admin access",
    "elevated access", "contractor", "phê duyệt",
]

RETRIEVAL_HINT_KEYWORDS = [
    "sla", "ticket", "p1", "p2", "escalation", "sự cố", "on-call",
    "helpdesk", "vpn", "password", "mật khẩu", "remote", "probation",
    "nghỉ phép", "leave", "faq",
]

RISK_KEYWORDS = [
    "emergency", "khẩn cấp", "2am", "2 giờ sáng", "ngoài giờ",
    "err-", "không rõ", "bất thường",
]

UNKNOWN_ERROR_PATTERN = "err-"


def supervisor_node(state: AgentState) -> AgentState:
    """Phân tích task → quyết định route, needs_tool, risk_high.

    Quyết định được ghi đầy đủ vào `route_reason` để trace debug được.
    """
    task_raw = state["task"]
    task = task_raw.lower()
    state["history"].append(f"[supervisor] received task: {task_raw[:80]}")

    reasons: list[str] = []

    policy_hits = [kw for kw in POLICY_KEYWORDS if kw in task]
    retrieval_hits = [kw for kw in RETRIEVAL_HINT_KEYWORDS if kw in task]
    risk_hits = [kw for kw in RISK_KEYWORDS if kw in task]

    if policy_hits:
        route = "policy_tool_worker"
        needs_tool = True
        reasons.append(f"matches policy/access keywords: {policy_hits[:3]}")
    elif retrieval_hits:
        route = "retrieval_worker"
        needs_tool = False
        reasons.append(f"matches knowledge keywords: {retrieval_hits[:3]}")
    else:
        route = "retrieval_worker"
        needs_tool = False
        reasons.append("no specific keyword → default retrieval_worker")

    risk_high = bool(risk_hits)
    if risk_hits:
        reasons.append(f"risk signals: {risk_hits[:3]}")

    # Override: mã lỗi không rõ (ERR-xxx) + không đủ context → HITL
    if UNKNOWN_ERROR_PATTERN in task:
        route = "human_review"
        reasons.append("unknown error code detected → human_review")
        risk_high = True

    # Policy questions liên quan access level → cần MCP tool
    if any(kw in task for kw in ["access level", "level 1", "level 2", "level 3", "level 4", "admin access"]):
        needs_tool = True
        reasons.append("access question → will call MCP check_access_permission")

    # Multi-hop signals (SLA + access) → vẫn policy_tool route, nhưng flag để worker gọi MCP
    if ("p1" in task or "sla" in task) and any(kw in task for kw in ["access", "cấp quyền", "contractor"]):
        route = "policy_tool_worker"
        needs_tool = True
        reasons.append("multi-hop SLA+access → policy_tool_worker with MCP")

    state["supervisor_route"] = route
    state["route_reason"] = " | ".join(reasons)
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["history"].append(
        f"[supervisor] route={route} needs_tool={needs_tool} risk_high={risk_high}"
    )
    return state


# ─────────────────────────────────────────────
# 3. Route Decision — conditional edge
# ─────────────────────────────────────────────

def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    """Trả về tên node tiếp theo dựa vào `supervisor_route`."""
    route = state.get("supervisor_route", "retrieval_worker")
    if route not in {"retrieval_worker", "policy_tool_worker", "human_review"}:
        route = "retrieval_worker"
    return route  # type: ignore[return-value]


# ─────────────────────────────────────────────
# 4. Human Review Node — HITL placeholder
# ─────────────────────────────────────────────

def human_review_node(state: AgentState) -> AgentState:
    """HITL: pause để human duyệt.

    Trong lab mode, auto-approve và chuyển sang retrieval để lấy evidence.
    Production: gắn với interrupt_before (LangGraph) hoặc queue external.
    """
    state["hitl_triggered"] = True
    state["workers_called"].append("human_review")
    state["history"].append("[human_review] HITL triggered — auto-approved in lab mode")
    print(f"\n⚠️  HITL TRIGGERED")
    print(f"   Task   : {state['task']}")
    print(f"   Reason : {state['route_reason']}")
    print(f"   Action : Auto-approve (lab mode) → fallback to retrieval_worker\n")

    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += " | human_review auto-approved → retrieval"
    return state


# ─────────────────────────────────────────────
# 5. Import Workers (Sprint 2)
# ─────────────────────────────────────────────

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workers.retrieval import run as retrieval_run
from workers.policy_tool import run as policy_tool_run
from workers.synthesis import run as synthesis_run


def retrieval_worker_node(state: AgentState) -> AgentState:
    return retrieval_run(state)


def policy_tool_worker_node(state: AgentState) -> AgentState:
    return policy_tool_run(state)


def synthesis_worker_node(state: AgentState) -> AgentState:
    return synthesis_run(state)


# ─────────────────────────────────────────────
# 6. Build Graph
# ─────────────────────────────────────────────

def build_graph():
    """Orchestrator — Python thuần (Option A).

    Flow:
        supervisor → route_decision
                    ├─ retrieval_worker        ──┐
                    ├─ policy_tool_worker → retrieval (nếu chưa có chunks) ──┐
                    └─ human_review → retrieval_worker  ──┘
                                                          │
                                                          ▼
                                                    synthesis_worker
    """
    def run(state: AgentState) -> AgentState:
        start = time.time()

        # Step 1: Supervisor
        state = supervisor_node(state)

        # Step 2: Route to node
        route = route_decision(state)

        if route == "human_review":
            state = human_review_node(state)
            state = retrieval_worker_node(state)

        elif route == "policy_tool_worker":
            # Policy worker cần context trước → chạy retrieval trước
            if not state.get("retrieved_chunks"):
                state = retrieval_worker_node(state)
            state = policy_tool_worker_node(state)

        else:
            state = retrieval_worker_node(state)

        # Step 3: Luôn chạy synthesis cuối cùng
        state = synthesis_worker_node(state)

        state["latency_ms"] = int((time.time() - start) * 1000)
        state["history"].append(f"[graph] completed in {state['latency_ms']}ms")
        return state

    return run


# ─────────────────────────────────────────────
# 7. Public API
# ─────────────────────────────────────────────

_graph = build_graph()


def run_graph(task: str) -> AgentState:
    """Entry point: nhận câu hỏi, trả về AgentState với full trace."""
    state = make_initial_state(task)
    return _graph(state)


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{state['run_id']}.json")
    # Chỉ ghi các fields có thể serialize
    serializable = {}
    for k, v in state.items():
        try:
            json.dumps(v, ensure_ascii=False)
            serializable[k] = v
        except (TypeError, ValueError):
            serializable[k] = str(v)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    return filename


# ─────────────────────────────────────────────
# 8. Manual Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab — Supervisor-Worker Graph")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?",
        "ERR-403-AUTH là lỗi gì và cách xử lý?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run_graph(query)
        print(f"  Route      : {result['supervisor_route']}")
        print(f"  Reason     : {result['route_reason']}")
        print(f"  Workers    : {result['workers_called']}")
        print(f"  Answer     : {result['final_answer'][:120]}...")
        print(f"  Sources    : {result['sources']}")
        print(f"  Confidence : {result['confidence']}")
        print(f"  HITL       : {result['hitl_triggered']}")
        print(f"  Latency    : {result['latency_ms']}ms")
        trace_file = save_trace(result)
        print(f"  Trace      : {trace_file}")

    print("\n✅ graph.py smoke test complete.")
