"""
workers/synthesis.py — Synthesis Worker (Sprint 2)

Owner: Worker Owner (xem note.md)

Contract (xem contracts/worker_contracts.yaml):
    Input:  {"task": str, "retrieved_chunks": list, "policy_result": dict}
    Output: {
        "final_answer": str (có citation),
        "sources": list,
        "confidence": float (0-1),
        "worker_io_logs": [...]
    }

Đặc điểm:
- Grounded prompt: chỉ trả lời từ context trong state, cấm dùng kiến thức ngoài.
- LLM chain: OpenAI → Gemini → local fallback (abstain rõ ràng, không hallucinate).
- Confidence: weighted avg score − exception penalty.
- Nếu retrieved_chunks=[] → abstain, confidence=0.2.

Test độc lập:
    python workers/synthesis.py
"""

from __future__ import annotations

import os
import sys

WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk + CS nội bộ.

QUY TẮC BẮT BUỘC:
1. CHỈ trả lời dựa trên phần 'TÀI LIỆU THAM KHẢO' bên dưới. Không dùng kiến thức ngoài.
2. Nếu tài liệu không đủ để trả lời → bắt đầu câu trả lời bằng: "Không đủ thông tin trong tài liệu nội bộ."
3. Sau mỗi ý quan trọng, trích dẫn nguồn: [tên_file.txt]. Nếu đã có số thứ tự, dùng [1], [2], ...
4. Nếu có phần 'POLICY EXCEPTIONS' → nêu rõ exceptions trước khi đưa kết luận.
5. Nếu có phần 'ACCESS CHECK' → dùng số liệu trong đó (can_grant, required_approvers, emergency_override) để trả lời.
6. Nếu có phần 'TICKET INFO' → tham chiếu ticket_id, assignee, notifications_sent khi thích hợp.
7. Trả lời ngắn gọn, có cấu trúc (bullet nếu > 2 ý), không dài dòng.
8. Không dùng emoji. Không xin lỗi. Không hỏi ngược lại.
"""


# ─────────────────────────────────────────────
# LLM call (OpenAI → Gemini → local fallback)
# ─────────────────────────────────────────────

def _call_openai(messages: list) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-...your"):
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            temperature=0.1,
            max_tokens=600,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"⚠️  OpenAI call failed: {e}", file=sys.stderr)
        return None


def _call_gemini(messages: list) -> str | None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key.startswith("AI...your"):
        return None
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        combined = "\n\n".join(m.get("content", "") for m in messages)
        response = model.generate_content(combined, generation_config={"temperature": 0.1})
        return response.text
    except Exception as e:
        print(f"⚠️  Gemini call failed: {e}", file=sys.stderr)
        return None


def _local_fallback(task: str, chunks: list, policy_result: dict) -> str:
    """Không có LLM key → build answer template từ context (không hallucinate)."""
    if not chunks:
        return (
            "Không đủ thông tin trong tài liệu nội bộ để trả lời câu hỏi này. "
            "Hãy liên hệ IT Helpdesk hoặc CS Team để được hỗ trợ trực tiếp."
        )

    lines = ["[LOCAL FALLBACK — không có LLM API key]"]
    lines.append(f"Câu hỏi: {task}")
    lines.append("")
    lines.append("Trích dẫn từ tài liệu:")
    for i, c in enumerate(chunks[:3], 1):
        lines.append(f"  [{i}] {c.get('source', 'unknown')}: {c.get('text', '')[:220]}...")

    if policy_result.get("exceptions_found"):
        lines.append("")
        lines.append("Policy exceptions phát hiện:")
        for ex in policy_result["exceptions_found"]:
            lines.append(f"  - {ex.get('rule', '')}")

    if policy_result.get("policy_version_note"):
        lines.append("")
        lines.append(f"Lưu ý phiên bản: {policy_result['policy_version_note']}")

    if policy_result.get("access_check"):
        ac = policy_result["access_check"]
        lines.append("")
        lines.append(
            f"Access check: can_grant={ac.get('can_grant')}, "
            f"approvers={ac.get('required_approvers')}, "
            f"emergency_override={ac.get('emergency_override')}"
        )

    return "\n".join(lines)


def _call_llm(messages: list, task: str, chunks: list, policy_result: dict) -> str:
    """Gọi LLM theo chain. Luôn trả về string."""
    answer = _call_openai(messages)
    if answer:
        return answer
    answer = _call_gemini(messages)
    if answer:
        return answer
    return _local_fallback(task, chunks, policy_result)


# ─────────────────────────────────────────────
# Context builder
# ─────────────────────────────────────────────

def _build_context(chunks: list, policy_result: dict) -> str:
    parts = []

    if chunks:
        parts.append("=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            parts.append(f"[{i}] Nguồn: {source} (relevance: {score:.2f})\n{text}")
    else:
        parts.append("=== TÀI LIỆU THAM KHẢO ===\n(Không có tài liệu nào được retrieve cho câu hỏi này)")

    if policy_result:
        if policy_result.get("exceptions_found"):
            parts.append("\n=== POLICY EXCEPTIONS ===")
            for ex in policy_result["exceptions_found"]:
                parts.append(f"- [{ex.get('type')}] {ex.get('rule', '')} — Nguồn: {ex.get('source', '')}")

        if policy_result.get("policy_version_note"):
            parts.append(f"\n=== LƯU Ý PHIÊN BẢN ===\n{policy_result['policy_version_note']}")

        if policy_result.get("access_check"):
            ac = policy_result["access_check"]
            parts.append("\n=== ACCESS CHECK (từ MCP) ===")
            parts.append(f"- access_level: {ac.get('access_level')}")
            parts.append(f"- can_grant: {ac.get('can_grant')}")
            parts.append(f"- required_approvers: {ac.get('required_approvers')}")
            parts.append(f"- emergency_override: {ac.get('emergency_override')}")
            if ac.get("notes"):
                parts.append(f"- notes: {ac['notes']}")
            parts.append(f"- source: {ac.get('source')}")

        if policy_result.get("ticket_info"):
            ti = policy_result["ticket_info"]
            parts.append("\n=== TICKET INFO (từ MCP) ===")
            for k in ("ticket_id", "priority", "status", "assignee", "created_at", "sla_deadline", "notifications_sent"):
                if ti.get(k) is not None:
                    parts.append(f"- {k}: {ti[k]}")

    return "\n\n".join(parts) if parts else "(Không có context)"


# ─────────────────────────────────────────────
# Confidence estimation
# ─────────────────────────────────────────────

def _estimate_confidence(chunks: list, answer: str, policy_result: dict) -> float:
    """Confidence = weighted_avg(chunk scores) - exception_penalty - abstain_penalty."""
    if not chunks:
        return 0.2  # No evidence

    answer_lower = answer.lower()
    abstain_signals = [
        "không đủ thông tin",
        "không có trong tài liệu",
        "insufficient",
        "cần xác nhận",
        "local fallback",
    ]
    is_abstain = any(sig in answer_lower for sig in abstain_signals)

    # Weighted average of chunk scores
    top_scores = sorted((c.get("score", 0) for c in chunks), reverse=True)[:3]
    avg_score = sum(top_scores) / len(top_scores) if top_scores else 0.0

    exception_penalty = 0.05 * len(policy_result.get("exceptions_found", []))
    version_penalty = 0.15 if policy_result.get("policy_version_note") else 0.0
    abstain_penalty = 0.25 if is_abstain else 0.0

    confidence = avg_score - exception_penalty - version_penalty - abstain_penalty
    return round(max(0.1, min(0.95, confidence)), 2)


# ─────────────────────────────────────────────
# Synthesize
# ─────────────────────────────────────────────

def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    context = _build_context(chunks, policy_result)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Câu hỏi: {task}

{context}

Trả lời câu hỏi dựa **hoàn toàn** vào context bên trên. Nếu không đủ, abstain rõ ràng."""
        },
    ]

    answer = _call_llm(messages, task, chunks, policy_result)
    sources = list({c.get("source", "unknown") for c in chunks if c})
    confidence = _estimate_confidence(chunks, answer, policy_result)

    return {"answer": answer, "sources": sources, "confidence": confidence}


# ─────────────────────────────────────────────
# Worker entry point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {}) or {}

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"]
        state["confidence"] = result["confidence"]

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources": result["sources"],
            "confidence": result["confidence"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated (len={len(result['answer'])}, "
            f"conf={result['confidence']}, sources={result['sources']})"
        )

    except Exception as e:
        worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
        state["confidence"] = 0.0
        state["sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state["worker_io_logs"].append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker — Standalone Test")
    print("=" * 50)

    tests = [
        {
            "name": "SLA retrieval",
            "state": {
                "task": "SLA ticket P1 là bao lâu?",
                "retrieved_chunks": [{
                    "text": "Ticket P1: Phản hồi ban đầu 15 phút. Xử lý và khắc phục 4 giờ. Escalation tự động sau 10 phút.",
                    "source": "sla_p1_2026.txt",
                    "score": 0.92,
                }],
                "policy_result": {},
            },
        },
        {
            "name": "Flash Sale exception",
            "state": {
                "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
                "retrieved_chunks": [{
                    "text": "Ngoại lệ: Flash Sale không được hoàn tiền (Điều 3 v4).",
                    "source": "policy_refund_v4.txt",
                    "score": 0.88,
                }],
                "policy_result": {
                    "policy_applies": False,
                    "exceptions_found": [{
                        "type": "flash_sale_exception",
                        "rule": "Flash Sale không được hoàn tiền.",
                        "source": "policy_refund_v4.txt",
                    }],
                },
            },
        },
        {
            "name": "Abstain",
            "state": {
                "task": "ERR-403-AUTH là lỗi gì?",
                "retrieved_chunks": [],
                "policy_result": {},
            },
        },
    ]

    for tc in tests:
        print(f"\n--- {tc['name']} ---")
        result = run(dict(tc["state"]))
        print(f"Answer:\n{result['final_answer']}")
        print(f"Sources   : {result['sources']}")
        print(f"Confidence: {result['confidence']}")

    print("\n✅ synthesis_worker test done.")
