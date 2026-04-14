"""
eval_trace.py — Trace Evaluation & Comparison (Sprint 4)

Owner: Trace & Docs Owner (xem note.md)

Chạy:
    python eval_trace.py                  # chạy 15 test_questions + analyze + compare
    python eval_trace.py --grading        # chạy grading_questions (17:00 public)
    python eval_trace.py --analyze        # chỉ analyze trace đã có
    python eval_trace.py --compare        # chỉ so sánh single vs multi

Outputs:
    artifacts/traces/*.json       — một file per question
    artifacts/grading_run.jsonl   — log grading (nộp cho giảng viên)
    artifacts/eval_report.json    — so sánh Day 08 vs Day 09
    artifacts/test_summary.json   — summary chi tiết 15 test questions
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

from graph import run_graph, save_trace  # noqa: E402

ARTIFACTS_DIR = _PROJECT_ROOT / "artifacts"
TRACES_DIR = ARTIFACTS_DIR / "traces"


# ─────────────────────────────────────────────
# 1. Run test questions (15 câu)
# ─────────────────────────────────────────────

ABSTAIN_SIGNALS = [
    "không đủ thông tin",
    "không có trong tài liệu",
    "insufficient",
    "cần xác nhận",
    "local fallback",
]


def _is_abstain(answer: str) -> bool:
    low = (answer or "").lower()
    return any(sig in low for sig in ABSTAIN_SIGNALS)


def _sources_match(actual: list, expected: list) -> bool:
    if not expected:
        return True  # abstain question — sources có/không đều OK
    actual_set = {s.lower() for s in actual or []}
    expected_set = {s.lower() for s in expected}
    return len(actual_set & expected_set) > 0


def run_test_questions(questions_file: str = "data/test_questions.json") -> list:
    """Chạy pipeline với test questions, lưu trace từng câu."""
    q_path = _PROJECT_ROOT / questions_file
    with open(q_path, encoding="utf-8") as f:
        questions = json.load(f)

    print(f"\n📋 Running {len(questions)} test questions from {q_path}")
    print("=" * 60)

    results = []
    for i, q in enumerate(questions, 1):
        q_id = q.get("id", f"q{i:02d}")
        question_text = q["question"]
        print(f"[{i:02d}/{len(questions)}] {q_id}: {question_text[:60]}...")

        try:
            result = run_graph(question_text)
            result["question_id"] = q_id
            trace_file = save_trace(result, str(TRACES_DIR))

            actual_sources = result.get("retrieved_sources", [])
            expected_sources = q.get("expected_sources", [])
            expected_route = q.get("expected_route", "")
            actual_route = result.get("supervisor_route", "")
            answer = result.get("final_answer", "")
            abstain = _is_abstain(answer)

            route_ok = (expected_route == actual_route) if expected_route else True
            sources_ok = _sources_match(actual_sources, expected_sources)
            abstain_expected = q.get("test_type") == "abstain"
            abstain_ok = abstain == abstain_expected if abstain_expected else True

            print(
                f"  ✓ route={actual_route} (expected={expected_route}) "
                f"conf={result.get('confidence', 0):.2f} "
                f"{result.get('latency_ms', 0)}ms "
                f"[route_ok={route_ok} src_ok={sources_ok}]"
            )

            results.append({
                "id": q_id,
                "question": question_text,
                "expected_answer": q.get("expected_answer", ""),
                "expected_sources": expected_sources,
                "expected_route": expected_route,
                "difficulty": q.get("difficulty", "unknown"),
                "category": q.get("category", "unknown"),
                "test_type": q.get("test_type", ""),
                "actual_route": actual_route,
                "actual_sources": actual_sources,
                "actual_answer": answer,
                "confidence": result.get("confidence", 0),
                "latency_ms": result.get("latency_ms", 0),
                "workers_called": result.get("workers_called", []),
                "mcp_tools_used": [t.get("tool") for t in result.get("mcp_tools_used", [])],
                "hitl_triggered": result.get("hitl_triggered", False),
                "abstain": abstain,
                "route_ok": route_ok,
                "sources_ok": sources_ok,
                "abstain_ok": abstain_ok,
                "trace_file": trace_file,
            })

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append({
                "id": q_id,
                "question": question_text,
                "error": str(e),
            })

    ok_count = sum(1 for r in results if r.get("actual_route"))
    print(f"\n✅ Done. {ok_count}/{len(results)} succeeded.")

    # Save summary
    summary_file = ARTIFACTS_DIR / "test_summary.json"
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total": len(results),
            "succeeded": ok_count,
            "route_accuracy": sum(1 for r in results if r.get("route_ok")) / max(1, len(results)),
            "source_hit_rate": sum(1 for r in results if r.get("sources_ok")) / max(1, len(results)),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"📄 Test summary → {summary_file}")

    return results


# ─────────────────────────────────────────────
# 2. Run grading questions
# ─────────────────────────────────────────────

def run_grading_questions(questions_file: str = "data/grading_questions.json") -> str:
    """Chạy pipeline với grading questions và lưu JSONL log."""
    q_path = _PROJECT_ROOT / questions_file
    if not q_path.exists():
        print(f"❌ {q_path} chưa được public (sau 17:00 mới có).")
        return ""

    with open(q_path, encoding="utf-8") as f:
        questions = json.load(f)

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    output_file = ARTIFACTS_DIR / "grading_run.jsonl"

    print(f"\n🎯 Running GRADING questions — {len(questions)} câu")
    print(f"   Output → {output_file}")
    print("=" * 60)

    with open(output_file, "w", encoding="utf-8") as out:
        for i, q in enumerate(questions, 1):
            q_id = q.get("id", f"gq{i:02d}")
            question_text = q["question"]
            print(f"[{i:02d}/{len(questions)}] {q_id}: {question_text[:60]}...")

            try:
                result = run_graph(question_text)
                record = {
                    "id": q_id,
                    "question": question_text,
                    "answer": result.get("final_answer", "PIPELINE_ERROR: no answer"),
                    "sources": result.get("retrieved_sources", []),
                    "supervisor_route": result.get("supervisor_route", ""),
                    "route_reason": result.get("route_reason", ""),
                    "workers_called": result.get("workers_called", []),
                    "mcp_tools_used": [t.get("tool") for t in result.get("mcp_tools_used", [])],
                    "confidence": result.get("confidence", 0.0),
                    "hitl_triggered": result.get("hitl_triggered", False),
                    "latency_ms": result.get("latency_ms"),
                    "timestamp": datetime.now().isoformat(),
                }
                print(f"  ✓ route={record['supervisor_route']}, conf={record['confidence']:.2f}")
                # Save full trace cho grading câu này
                save_trace(result, str(TRACES_DIR / "grading"))

            except Exception as e:
                record = {
                    "id": q_id,
                    "question": question_text,
                    "answer": f"PIPELINE_ERROR: {e}",
                    "sources": [],
                    "supervisor_route": "error",
                    "route_reason": str(e),
                    "workers_called": [],
                    "mcp_tools_used": [],
                    "confidence": 0.0,
                    "hitl_triggered": False,
                    "latency_ms": None,
                    "timestamp": datetime.now().isoformat(),
                }
                print(f"  ✗ ERROR: {e}")

            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n✅ Grading log saved → {output_file}")
    print(f"   ⚠️  Nộp file này trước 18:00!")
    return str(output_file)


# ─────────────────────────────────────────────
# 3. Analyze traces
# ─────────────────────────────────────────────

def analyze_traces(traces_dir: Path = TRACES_DIR) -> dict:
    traces_dir = Path(traces_dir)
    if not traces_dir.exists():
        print(f"⚠️  {traces_dir} không tồn tại. Chạy run_test_questions() trước.")
        return {}

    trace_files = list(traces_dir.glob("*.json"))
    if not trace_files:
        print(f"⚠️  Không có trace files trong {traces_dir}.")
        return {}

    traces = []
    for f in trace_files:
        try:
            with open(f, encoding="utf-8") as fh:
                traces.append(json.load(fh))
        except Exception as e:
            print(f"⚠️  Skip {f.name}: {e}")

    routing_counts: dict = {}
    confidences = []
    latencies = []
    mcp_calls = 0
    hitl_triggers = 0
    source_counts: dict = {}
    worker_co_call = {"retrieval_only": 0, "policy_only": 0, "both": 0, "none": 0}
    abstain_count = 0

    for t in traces:
        route = t.get("supervisor_route", "unknown")
        routing_counts[route] = routing_counts.get(route, 0) + 1

        conf = t.get("confidence", 0)
        if conf:
            confidences.append(conf)

        lat = t.get("latency_ms")
        if lat:
            latencies.append(lat)

        workers = t.get("workers_called", [])
        has_retrieval = "retrieval_worker" in workers
        has_policy = "policy_tool_worker" in workers
        if has_retrieval and has_policy:
            worker_co_call["both"] += 1
        elif has_retrieval:
            worker_co_call["retrieval_only"] += 1
        elif has_policy:
            worker_co_call["policy_only"] += 1
        else:
            worker_co_call["none"] += 1

        if t.get("mcp_tools_used"):
            mcp_calls += 1

        if t.get("hitl_triggered"):
            hitl_triggers += 1

        if _is_abstain(t.get("final_answer", "")):
            abstain_count += 1

        for src in t.get("retrieved_sources", []):
            source_counts[src] = source_counts.get(src, 0) + 1

    total = len(traces)
    pct = lambda x: f"{x}/{total} ({round(100 * x / total, 1)}%)" if total else "0"

    return {
        "total_traces": total,
        "routing_distribution": {k: pct(v) for k, v in routing_counts.items()},
        "worker_co_call": {k: pct(v) for k, v in worker_co_call.items()},
        "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
        "min_confidence": round(min(confidences), 3) if confidences else 0,
        "max_confidence": round(max(confidences), 3) if confidences else 0,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "p95_latency_ms": (
            sorted(latencies)[int(0.95 * len(latencies))] if len(latencies) >= 20 else
            (max(latencies) if latencies else 0)
        ),
        "mcp_usage_rate": pct(mcp_calls),
        "hitl_rate": pct(hitl_triggers),
        "abstain_rate": pct(abstain_count),
        "top_sources": sorted(source_counts.items(), key=lambda x: -x[1])[:5],
    }


# ─────────────────────────────────────────────
# 4. Compare single vs multi
# ─────────────────────────────────────────────

def compare_single_vs_multi(
    multi_traces_dir: Path = TRACES_DIR,
    day08_results_file: Optional[str] = None,
) -> dict:
    multi_metrics = analyze_traces(multi_traces_dir)

    # Day 08 baseline — điền thủ công hoặc load từ file
    day08_baseline = {
        "total_questions": 15,
        "avg_confidence": None,
        "avg_latency_ms": None,
        "abstain_rate": None,
        "routing_visibility": "N/A — single agent không có concept routing",
        "debuggability": "Low — khó isolate bug vì monolithic prompt",
        "note": "Để cập nhật thực tế, chạy day08 eval và điền vào file day08_results.json.",
    }

    if day08_results_file:
        p = Path(day08_results_file)
        if p.exists():
            with open(p) as f:
                day08_baseline.update(json.load(f))

    # Delta analysis
    analysis = {
        "routing_visibility": "Day 09 có route_reason cho từng câu → dễ debug hơn Day 08.",
        "debuggability": (
            "Multi-agent có thể test từng worker độc lập (python workers/retrieval.py, "
            "policy_tool.py, synthesis.py). Single-agent phải chạy toàn pipeline để debug."
        ),
        "mcp_benefit": (
            "Day 09 extend capability qua MCP (thêm tool mới không sửa core). "
            "Day 08 phải hard-code API calls vào prompt/pipeline."
        ),
        "trace_richness": (
            f"Day 09 trace có {len(multi_metrics.get('routing_distribution', {}))} routes, "
            f"{multi_metrics.get('mcp_usage_rate', 'N/A')} MCP usage, "
            f"{multi_metrics.get('hitl_rate', 'N/A')} HITL. "
            "Day 08 chỉ có final answer + retrieved_docs."
        ),
        "latency_cost": (
            f"Day 09 avg latency {multi_metrics.get('avg_latency_ms', 'N/A')}ms — "
            "cao hơn single-agent vì extra supervisor + policy node, "
            "nhưng bù lại có thể cache retrieval riêng."
        ),
    }

    return {
        "generated_at": datetime.now().isoformat(),
        "day08_single_agent": day08_baseline,
        "day09_multi_agent": multi_metrics,
        "analysis": analysis,
    }


def save_eval_report(comparison: dict) -> str:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    output_file = ARTIFACTS_DIR / "eval_report.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    return str(output_file)


# ─────────────────────────────────────────────
# 5. CLI
# ─────────────────────────────────────────────

def print_metrics(metrics: dict):
    if not metrics:
        return
    print("\n📊 Trace Analysis:")
    for k, v in metrics.items():
        if isinstance(v, list):
            print(f"  {k}:")
            for item in v:
                print(f"    • {item}")
        elif isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 09 Lab — Trace Evaluation")
    parser.add_argument("--grading", action="store_true", help="Run grading questions")
    parser.add_argument("--analyze", action="store_true", help="Analyze existing traces")
    parser.add_argument("--compare", action="store_true", help="Compare single vs multi")
    parser.add_argument("--test-file", default="data/test_questions.json", help="Test questions file")
    parser.add_argument("--day08", default=None, help="Path to day08_results.json for comparison")
    args = parser.parse_args()

    if args.grading:
        log_file = run_grading_questions()
        if log_file:
            print(f"\n✅ Grading log: {log_file}")

    elif args.analyze:
        metrics = analyze_traces()
        print_metrics(metrics)

    elif args.compare:
        comparison = compare_single_vs_multi(day08_results_file=args.day08)
        report_file = save_eval_report(comparison)
        print(f"\n📊 Comparison report saved → {report_file}")
        print("\n=== Day 08 vs Day 09 — Analysis ===")
        for k, v in comparison.get("analysis", {}).items():
            print(f"  [{k}] {v}")

    else:
        # Default: end-to-end
        run_test_questions(args.test_file)
        metrics = analyze_traces()
        print_metrics(metrics)
        comparison = compare_single_vs_multi(day08_results_file=args.day08)
        report_file = save_eval_report(comparison)
        print(f"\n📄 Eval report → {report_file}")
        print("\n✅ Sprint 4 complete!")
        print("   Next steps:")
        print("     1. Điền docs/system_architecture.md, routing_decisions.md, single_vs_multi_comparison.md")
        print("     2. Sau 17:00: python eval_trace.py --grading")
        print("     3. Sau 18:00: viết reports/group_report.md + reports/individual/[ten].md")
