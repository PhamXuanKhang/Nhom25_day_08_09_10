"""
mcp_server.py — Mock MCP Server
Sprint 3: Implement ít nhất 2 MCP tools.

Mô phỏng MCP (Model Context Protocol) interface trong Python.
Agent (MCP client) gọi dispatch_tool() thay vì hard-code từng API.

Tools available:
    1. search_kb(query, top_k)           → tìm kiếm Knowledge Base
    2. get_ticket_info(ticket_id)        → tra cứu thông tin ticket (mock data)
    3. check_access_permission(level, requester_role)  → kiểm tra quyền truy cập
    4. create_ticket(priority, title, description)     → tạo ticket mới (mock)

Sử dụng:
    from mcp_server import dispatch_tool, list_tools

    # Discover available tools
    tools = list_tools()

    # Call a tool
    result = dispatch_tool("search_kb", {"query": "SLA P1", "top_k": 3})

Sprint 3 TODO:
    - Option Standard: Sử dụng file này as-is (mock class)
    - Option Advanced: Implement HTTP server với FastAPI hoặc dùng `mcp` library

Chạy thử:
    python mcp_server.py
"""

from _future_ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict


# ─────────────────────────────────────────────
# Tool schemas (MCP discovery)
# ─────────────────────────────────────────────

TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "search_kb": {
        "name": "search_kb",
        "description": "Tìm kiếm Knowledge Base nội bộ bằng semantic search (dense vector retrieval). Trả về top-k chunks liên quan.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Câu hỏi hoặc keyword."},
                "top_k": {"type": "integer", "description": "Số chunks cần trả về.", "default": 3},
            },
            "required": ["query"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "chunks": {"type": "array"},
                "sources": {"type": "array"},
                "total_found": {"type": "integer"},
            },
        },
    },
    "get_ticket_info": {
        "name": "get_ticket_info",
        "description": "Tra cứu thông tin ticket từ hệ thống Jira nội bộ (mock dataset).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "ID ticket (VD: IT-1234, P1-LATEST)."},
            },
            "required": ["ticket_id"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "priority": {"type": "string"},
                "status": {"type": "string"},
                "assignee": {"type": "string"},
                "created_at": {"type": "string"},
                "sla_deadline": {"type": "string"},
                "notifications_sent": {"type": "array"},
            },
        },
    },
    "check_access_permission": {
        "name": "check_access_permission",
        "description": "Kiểm tra điều kiện cấp quyền theo Access Control SOP (Level 1-4 + emergency bypass rules).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "access_level": {"type": "integer", "description": "Level cần cấp (1, 2, 3, hoặc 4)."},
                "requester_role": {"type": "string", "description": "Vai trò của người yêu cầu."},
                "is_emergency": {"type": "boolean", "description": "Có phải khẩn cấp không.", "default": False},
            },
            "required": ["access_level", "requester_role"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "access_level": {"type": "integer"},
                "can_grant": {"type": "boolean"},
                "required_approvers": {"type": "array"},
                "approver_count": {"type": "integer"},
                "emergency_override": {"type": "boolean"},
                "notes": {"type": "array"},
                "source": {"type": "string"},
            },
        },
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Tạo ticket mới trong Jira (MOCK — chỉ in log, không persist).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["priority", "title"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "url": {"type": "string"},
                "created_at": {"type": "string"},
                "note": {"type": "string"},
            },
        },
    },
}


# ─────────────────────────────────────────────
# Tool: search_kb
# ─────────────────────────────────────────────

def tool_search_kb(query: str, top_k: int = 3) -> dict:
    """Search KB — delegate sang retrieval worker (cùng ChromaDB)."""
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(_file_)))
        from workers.retrieval import retrieve_dense

        chunks = retrieve_dense(query, top_k=top_k)
        sources = list({c["source"] for c in chunks})
        return {
            "chunks": chunks,
            "sources": sources,
            "total_found": len(chunks),
        }
    except Exception as e:
        return {
            "chunks": [],
            "sources": [],
            "total_found": 0,
            "error": f"search_kb failed: {e}",
        }


# ─────────────────────────────────────────────
# Tool: get_ticket_info
# ─────────────────────────────────────────────

MOCK_TICKETS: Dict[str, Dict[str, Any]] = {
    "P1-LATEST": {
        "ticket_id": "IT-9847",
        "priority": "P1",
        "title": "API Gateway down — toàn bộ người dùng không đăng nhập được",
        "status": "in_progress",
        "assignee": "nguyen.van.a@company.internal",
        "created_at": "2026-04-13T22:47:00",
        "sla_deadline": "2026-04-14T02:47:00",
        "escalated": True,
        "escalated_to": "senior_engineer_team",
        "notifications_sent": [
            "slack:#incident-p1",
            "email:incident@company.internal",
            "pagerduty:oncall",
        ],
    },
    "IT-9847": None,  # alias resolved below
    "IT-1234": {
        "ticket_id": "IT-1234",
        "priority": "P2",
        "title": "Feature login chậm cho một số user",
        "status": "open",
        "assignee": None,
        "created_at": "2026-04-13T09:15:00",
        "sla_deadline": "2026-04-14T09:15:00",
        "escalated": False,
        "notifications_sent": ["slack:#incident-p2"],
    },
}
# Alias resolve
MOCK_TICKETS["IT-9847"] = MOCK_TICKETS["P1-LATEST"]


def tool_get_ticket_info(ticket_id: str) -> dict:
    key = ticket_id.upper().strip()
    ticket = MOCK_TICKETS.get(key)
    if ticket:
        return ticket
    return {
        "error": f"Ticket '{ticket_id}' không tìm thấy.",
        "available_mock_ids": [k for k in MOCK_TICKETS.keys() if MOCK_TICKETS[k]],
    }


# ─────────────────────────────────────────────
# Tool: check_access_permission
# ─────────────────────────────────────────────

# Rules đồng bộ với data/docs/access_control_sop.txt (Section 2 + Section 4).
ACCESS_RULES: Dict[int, Dict[str, Any]] = {
    1: {
        "name": "Read Only",
        "required_approvers": ["Line Manager"],
        "emergency_can_bypass": False,
        "notes": ["Standard user access, no special handling."],
    },
    2: {
        "name": "Standard Access",
        "required_approvers": ["Line Manager", "IT Admin"],
        "emergency_can_bypass": True,
        "emergency_bypass_note": (
            "Level 2 có emergency bypass — On-call IT Admin có thể cấp tạm thời (max 24h) "
            "sau khi được Tech Lead phê duyệt. Phải log vào Security Audit."
        ),
        "notes": ["Elevated access for regular employees."],
    },
    3: {
        "name": "Elevated Access",
        "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
        "emergency_can_bypass": False,
        "notes": [
            "Level 3 KHÔNG có emergency bypass — phải follow quy trình chuẩn đủ 3 approvers.",
            "Dù đang có P1, vẫn cần IT Security approve.",
        ],
    },
    4: {
        "name": "Admin Access",
        "required_approvers": ["IT Manager", "CISO"],
        "emergency_can_bypass": False,
        "notes": [
            "Admin access — yêu cầu training bắt buộc về security policy.",
            "Không có emergency bypass.",
        ],
    },
}


def tool_check_access_permission(
    access_level: int,
    requester_role: str,
    is_emergency: bool = False,
) -> dict:
    rule = ACCESS_RULES.get(access_level)
    if not rule:
        return {
            "error": f"Access level {access_level} không hợp lệ. Valid: 1, 2, 3, 4.",
            "valid_levels": list(ACCESS_RULES.keys()),
        }

    notes = list(rule.get("notes", []))
    emergency_override = False

    if is_emergency:
        if rule.get("emergency_can_bypass"):
            emergency_override = True
            notes.append(rule.get("emergency_bypass_note", "Emergency bypass applicable."))
        else:
            notes.append(
                f"Level {access_level} KHÔNG có emergency bypass theo SOP. "
                f"Phải follow quy trình chuẩn với đủ {len(rule['required_approvers'])} approvers."
            )

    return {
        "access_level": access_level,
        "level_name": rule["name"],
        "requester_role": requester_role,
        "can_grant": True,  # Technically có thể grant, chỉ phụ thuộc approvers
        "required_approvers": rule["required_approvers"],
        "approver_count": len(rule["required_approvers"]),
        "emergency_override": emergency_override,
        "notes": notes,
        "source": "access_control_sop.txt",
    }


# ─────────────────────────────────────────────
# Tool: create_ticket
# ─────────────────────────────────────────────

def tool_create_ticket(priority: str, title: str, description: str = "") -> dict:
    priority = priority.upper()
    if priority not in {"P1", "P2", "P3", "P4"}:
        return {"error": f"Priority '{priority}' không hợp lệ. Valid: P1, P2, P3, P4."}

    mock_id = f"IT-{9900 + (abs(hash(title)) % 99)}"
    now = datetime.now()
    # SLA deadline mock
    sla_hours = {"P1": 4, "P2": 24, "P3": 120, "P4": 336}[priority]
    ticket = {
        "ticket_id": mock_id,
        "priority": priority,
        "title": title,
        "description": description[:200],
        "status": "open",
        "created_at": now.isoformat(),
        "sla_deadline": (now + timedelta(hours=sla_hours)).isoformat(),
        "url": f"https://jira.company.internal/browse/{mock_id}",
        "note": "MOCK ticket — không persist.",
    }
    print(f"  [MCP create_ticket] MOCK: {mock_id} | {priority} | {title[:50]}")
    return ticket


# ─────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────

TOOL_REGISTRY = {
    "search_kb": tool_search_kb,
    "get_ticket_info": tool_get_ticket_info,
    "check_access_permission": tool_check_access_permission,
    "create_ticket": tool_create_ticket,
}


def list_tools() -> list:
    """MCP discovery (tools/list)."""
    return list(TOOL_SCHEMAS.values())


def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    """MCP execution (tools/call).

    Luôn trả dict (không raise). Nếu lỗi, trả {"error": ...}.
    """
    if tool_name not in TOOL_REGISTRY:
        return {
            "error": f"Tool '{tool_name}' không tồn tại.",
            "available_tools": list(TOOL_REGISTRY.keys()),
        }

    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        return tool_fn(**(tool_input or {}))
    except TypeError as e:
        return {
            "error": f"Invalid input for '{tool_name}': {e}",
            "schema": TOOL_SCHEMAS[tool_name]["inputSchema"],
        }
    except Exception as e:
        return {"error": f"Tool '{tool_name}' execution failed: {e}"}


# ─────────────────────────────────────────────
# CLI smoke test
# ─────────────────────────────────────────────

if _name_ == "_main_":
    print("=" * 60)
    print("MCP Server — Tool Discovery & Smoke Test")
    print("=" * 60)

    print("\n📋 Available Tools:")
    for tool in list_tools():
        print(f"  • {tool['name']}: {tool['description'][:70]}...")

    print("\n🔍 Test: search_kb")
    r = dispatch_tool("search_kb", {"query": "SLA P1 resolution time", "top_k": 2})
    for c in r.get("chunks", [])[:2]:
        print(f"  [{c.get('score', 0):.3f}] {c.get('source')}: {c.get('text', '')[:70]}...")
    if not r.get("chunks"):
        print(f"  (no chunks) {r.get('error', '')}")

    print("\n🎫 Test: get_ticket_info('P1-LATEST')")
    t = dispatch_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
    print(f"  id={t.get('ticket_id')} priority={t.get('priority')} status={t.get('status')}")
    print(f"  notifications={t.get('notifications_sent')}")

    print("\n🔐 Test: check_access_permission(Level=3, emergency=True)")
    p = dispatch_tool("check_access_permission", {
        "access_level": 3, "requester_role": "contractor", "is_emergency": True,
    })
    print(f"  can_grant={p.get('can_grant')} emergency_override={p.get('emergency_override')}")
    print(f"  approvers={p.get('required_approvers')}")
    print(f"  notes={p.get('notes')}")

    print("\n🔐 Test: check_access_permission(Level=2, emergency=True)")
    p2 = dispatch_tool("check_access_permission", {
        "access_level": 2, "requester_role": "contractor", "is_emergency": True,
    })
    print(f"  can_grant={p2.get('can_grant')} emergency_override={p2.get('emergency_override')}")
    print(f"  approvers={p2.get('required_approvers')}")

    print("\n📝 Test: create_ticket")
    ct = dispatch_tool("create_ticket", {
        "priority": "P2", "title": "Test MCP ticket", "description": "smoke test",
    })
    print(f"  created: {ct.get('ticket_id')} at {ct.get('created_at')}")

    print("\n❌ Test: invalid tool")
    err = dispatch_tool("nonexistent_tool", {})
    print(f"  error: {err.get('error')}")

    print("\n✅ MCP server smoke test done.")