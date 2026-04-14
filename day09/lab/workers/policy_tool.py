"""
workers/policy_tool.py — Policy & Tool Worker (Sprint 2 + 3)

Owner: Worker Owner (phần analyze + run) + MCP Owner (phần _call_mcp_tool).

Contract (xem contracts/worker_contracts.yaml):
    Input:  {"task": str, "retrieved_chunks": list, "needs_tool": bool}
    Output: {
        "policy_result": {
            "policy_applies": bool,
            "policy_name": str,
            "exceptions_found": [...],
            "source": [str, ...],
            "policy_version_note": str,
            "access_check": dict | null,
            "ticket_info": dict | null
        },
        "mcp_tools_used": [...],
        "worker_io_logs": [...]
    }

Test độc lập:
    python workers/policy_tool.py
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

WORKER_NAME = "policy_tool_worker"


# ─────────────────────────────────────────────
# MCP Client (Sprint 3)
# In-process mock — gọi trực tiếp dispatch_tool từ mcp_server.py.
# Nếu MCP_SERVER_MODE=http, sẽ gọi HTTP endpoint (xem mcp_http_server.py).
# ─────────────────────────────────────────────

def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """Gọi MCP tool. Trả về dict chuẩn MCP {tool, input, output, error, timestamp}."""
    ts = datetime.now().isoformat()
    mode = os.getenv("MCP_SERVER_MODE", "mock").lower()

    try:
        if mode == "http":
            import httpx  # type: ignore
            url = os.getenv("MCP_SERVER_URL", "http://localhost:8080") + "/tools/call"
            resp = httpx.post(url, json={"name": tool_name, "input": tool_input}, timeout=10.0)
            resp.raise_for_status()
            output = resp.json()
        else:
            from mcp_server import dispatch_tool
            output = dispatch_tool(tool_name, tool_input)

        return {
            "tool": tool_name,
            "input": tool_input,
            "output": output,
            "error": None,
            "timestamp": ts,
        }

    except Exception as e:
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
            "timestamp": ts,
        }


# ─────────────────────────────────────────────
# Rule-based policy analysis
# ─────────────────────────────────────────────

DATE_PATTERN = re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})")
V4_EFFECTIVE_DATE = (2026, 2, 1)


def _parse_order_date(task: str) -> tuple[int, int, int] | None:
    """Tìm ngày đặt đơn trong task (dạng dd/mm/yyyy hoặc dd-mm-yyyy)."""
    for match in DATE_PATTERN.finditer(task):
        d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if 2024 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
            return (y, m, d)
    return None


def _is_before_v4(order_date: tuple[int, int, int]) -> bool:
    return order_date < V4_EFFECTIVE_DATE


def analyze_policy(task: str, chunks: list) -> dict:
    """Rule-based policy analysis.

    Xử lý:
    - flash_sale_exception
    - digital_product_exception (license, subscription)
    - activated_exception
    - temporal_scoping (đơn trước 01/02/2026 → v3)
    """
    task_lower = task.lower()
    context_text = " ".join(c.get("text", "") for c in chunks).lower()
    sources = list({c.get("source", "unknown") for c in chunks if c})

    exceptions_found: list[dict] = []

    # Exception 1: Flash Sale
    if "flash sale" in task_lower or "flash sale" in context_text:
        exceptions_found.append({
            "type": "flash_sale_exception",
            "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 2: Digital product
    if any(kw in task_lower or kw in context_text for kw in ["license key", "license", "subscription", "kỹ thuật số", "digital"]):
        exceptions_found.append({
            "type": "digital_product_exception",
            "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 3: Activated product
    if any(kw in task_lower or kw in context_text for kw in ["đã kích hoạt", "đã đăng ký", "đã sử dụng", "activated"]):
        exceptions_found.append({
            "type": "activated_exception",
            "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Temporal scoping: đơn trước 01/02/2026 → v3 applies
    policy_version_note = ""
    policy_name = "refund_policy_v4"
    order_date = _parse_order_date(task)
    if order_date and _is_before_v4(order_date):
        policy_name = "refund_policy_v3 (implied)"
        policy_version_note = (
            f"Đơn hàng đặt {order_date[2]:02d}/{order_date[1]:02d}/{order_date[0]} "
            f"trước ngày hiệu lực của chính sách v4 (01/02/2026). "
            f"Áp dụng chính sách v3 — tài liệu nội bộ hiện tại không có nội dung v3, "
            f"cần xác nhận với CS Team."
        )

    policy_applies = len(exceptions_found) == 0 and not policy_version_note

    return {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": sources or ["policy_refund_v4.txt"],
        "policy_version_note": policy_version_note,
        "explanation": "Rule-based policy check (flash_sale, digital_product, activated, temporal_scoping).",
    }


# ─────────────────────────────────────────────
# Task signal detection
# ─────────────────────────────────────────────

def _detect_access_question(task: str) -> dict | None:
    """Phát hiện câu hỏi về access level → chuẩn bị MCP input."""
    task_lower = task.lower()
    level_match = re.search(r"level\s*([1-4])", task_lower)
    level = int(level_match.group(1)) if level_match else None

    if not level and "admin access" in task_lower:
        level = 3

    if not level:
        return None

    is_emergency = any(
        kw in task_lower for kw in ["emergency", "khẩn cấp", "2am", "2 giờ", "tạm thời", "urgent"]
    )
    role = "contractor" if "contractor" in task_lower else "employee"

    return {"access_level": level, "requester_role": role, "is_emergency": is_emergency}


def _detect_ticket_question(task: str) -> str | None:
    """Phát hiện câu hỏi về ticket cụ thể → trả ticket_id."""
    match = re.search(r"(IT-\d+|P1-LATEST)", task, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    task_lower = task.lower()
    if ("p1" in task_lower and ("ticket" in task_lower or "sự cố" in task_lower or "incident" in task_lower)):
        return "P1-LATEST"
    return None


# ─────────────────────────────────────────────
# Worker entry point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    """Worker entry point — gọi từ graph.py."""
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])
    state.setdefault("worker_io_logs", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "chunks_count": len(chunks), "needs_tool": needs_tool},
        "output": None,
        "error": None,
    }

    try:
        # Step 1: Nếu chưa có chunks, dùng MCP search_kb (tool worker agnostic với data source)
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")
            output = mcp_result.get("output") or {}
            if output.get("chunks"):
                chunks = output["chunks"]
                state["retrieved_chunks"] = chunks
                state["retrieved_sources"] = output.get("sources", [])

        # Step 2: Rule-based policy analysis
        policy_result = analyze_policy(task, chunks)

        # Step 3: MCP check_access_permission nếu phát hiện access question
        access_params = _detect_access_question(task)
        if access_params and needs_tool:
            mcp_result = _call_mcp_tool("check_access_permission", access_params)
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(
                f"[{WORKER_NAME}] called MCP check_access_permission "
                f"(level={access_params['access_level']}, "
                f"emergency={access_params['is_emergency']})"
            )
            policy_result["access_check"] = mcp_result.get("output")

        # Step 4: MCP get_ticket_info nếu có ticket id
        ticket_id = _detect_ticket_question(task)
        if ticket_id and needs_tool:
            mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": ticket_id})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP get_ticket_info({ticket_id})")
            policy_result["ticket_info"] = mcp_result.get("output")

        state["policy_result"] = policy_result

        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls": len(state["mcp_tools_used"]),
            "has_access_check": bool(policy_result.get("access_check")),
            "has_ticket_info": bool(policy_result.get("ticket_info")),
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}, "
            f"mcp_calls={len(state['mcp_tools_used'])}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state["worker_io_logs"].append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Policy Tool Worker — Standalone Test")
    print("=" * 50)

    test_cases = [
        {
            "name": "Flash Sale exception",
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "retrieved_chunks": [
                {"text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.9}
            ],
            "needs_tool": True,
        },
        {
            "name": "Digital product exception",
            "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
            "retrieved_chunks": [
                {"text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.88}
            ],
            "needs_tool": True,
        },
        {
            "name": "Temporal scoping v3",
            "task": "Khách hàng đặt đơn 31/01/2026 và yêu cầu hoàn tiền 07/02/2026. Sản phẩm lỗi, chưa kích hoạt.",
            "retrieved_chunks": [
                {"text": "Chính sách hoàn tiền v4 hiệu lực 01/02/2026. Đơn trước đó áp dụng v3.", "source": "policy_refund_v4.txt", "score": 0.86}
            ],
            "needs_tool": True,
        },
        {
            "name": "Access Level 3 emergency (multi-hop)",
            "task": "Contractor cần Admin Access (Level 3) để fix P1 khẩn cấp. Quy trình tạm thời?",
            "retrieved_chunks": [],
            "needs_tool": True,
        },
        {
            "name": "Level 2 emergency",
            "task": "Ticket P1 lúc 2am, cấp Level 2 tạm thời cho contractor emergency fix.",
            "retrieved_chunks": [],
            "needs_tool": True,
        },
    ]

    for tc in test_cases:
        print(f"\n▶ [{tc['name']}] {tc['task'][:65]}...")
        state = {k: v for k, v in tc.items() if k != "name"}
        result = run(state)
        pr = result.get("policy_result", {})
        print(f"  policy_applies: {pr.get('policy_applies')}")
        if pr.get("exceptions_found"):
            for ex in pr["exceptions_found"]:
                print(f"  ✗ exception: {ex['type']}")
        if pr.get("policy_version_note"):
            print(f"  ⏳ version_note: {pr['policy_version_note'][:70]}...")
        if pr.get("access_check"):
            ac = pr["access_check"]
            print(f"  🔐 access_check: can_grant={ac.get('can_grant')}, approvers={ac.get('required_approvers')}")
        print(f"  MCP calls: {len(result.get('mcp_tools_used', []))}")

    print("\n✅ policy_tool_worker test done.")
