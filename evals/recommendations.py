from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

PHASE10_VERSION = "phase10_recommendation_engine_v1"

EFFORT_SCORE = {"low": 30, "medium": 18, "high": 8}
IMPACT_SCORE = {"low": 15, "medium": 30, "high": 45, "critical": 60}
SEVERITY_SCORE = {"info": 3, "low": 8, "medium": 16, "high": 28, "critical": 42}
LAYER_ORDER = {
    "safety": 0,
    "schema": 1,
    "instructions": 2,
    "custom_gpt_behavior": 3,
    "backend_engine": 4,
    "backend_route": 5,
    "repo_environment": 6,
    "evaluation": 7,
}


def _events(events: list[dict[str, Any]], event_type: str | None = None) -> list[dict[str, Any]]:
    if event_type is None:
        return events
    return [e for e in events if e.get("event_type") == event_type]


def _failure_codes(failures: list[dict[str, Any]]) -> Counter:
    return Counter(str(f.get("code") or "unknown") for f in failures)


def _failure_layers(failures: list[dict[str, Any]]) -> Counter:
    out: Counter = Counter()
    for failure in failures:
        layer = str(failure.get("layer") or "unknown")
        for part in layer.replace("/", ",").split(","):
            part = part.strip()
            if part:
                out[part] += 1
    return out


def _endpoint_latency(endpoint_stats: dict[str, Any]) -> dict[str, Any]:
    latency = endpoint_stats.get("latency_ms") or {}
    return {"p50": latency.get("p50"), "p95": latency.get("p95"), "max": latency.get("max")}


def _count_exit_127(events: list[dict[str, Any]]) -> int:
    return sum(1 for e in events if e.get("event_type") == "subprocess_completed" and (e.get("exit_code") == 127 or e.get("not_found")))


def _quality_failed(events: list[dict[str, Any]]) -> int:
    return sum(1 for e in events if e.get("event_type") == "quality_run" and e.get("passed") is False)


def _tests_failed(events: list[dict[str, Any]]) -> int:
    return sum(1 for e in events if e.get("event_type") == "tests_run" and e.get("passed") is False)


def _has_event(events: list[dict[str, Any]], event_type: str) -> bool:
    return any(e.get("event_type") == event_type for e in events)


def _rec(
    *,
    title: str,
    layer: str,
    why: str,
    impact: str,
    effort: str,
    evidence: dict[str, Any],
    affected_metrics: list[str],
    action_items: list[str],
    severity: str = "medium",
    confidence: float = 0.85,
) -> dict[str, Any]:
    frequency = int(evidence.get("count") or evidence.get("failure_count") or 1)
    roi = IMPACT_SCORE.get(impact, 20) + SEVERITY_SCORE.get(severity, 10) + EFFORT_SCORE.get(effort, 10) + min(25, frequency * 4)
    if confidence < 0.7:
        roi -= 8
    return {
        "title": title,
        "layer": layer,
        "why": why,
        "impact": impact,
        "effort": effort,
        "severity": severity,
        "confidence": round(confidence, 2),
        "roi_score": max(1, int(roi)),
        "affected_metrics": affected_metrics,
        "evidence": evidence,
        "action_items": action_items,
    }


def generate_recommendations(
    events: list[dict[str, Any]],
    agent: dict[str, Any] | None = None,
    backend: dict[str, Any] | None = None,
    failures: list[dict[str, Any]] | None = None,
    endpoint_stats: dict[str, Any] | None = None,
    engine_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate ranked, evidence-backed improvement recommendations.

    This is Phase 10's central recommendation engine. It turns scorecards,
    classified failures, endpoint stats, and engine metrics into ranked
    improvement opportunities grouped by likely ownership layer.
    """
    agent = agent or {}
    backend = backend or {}
    failures = failures or []
    endpoint_stats = endpoint_stats or {}
    engine_metrics = engine_metrics or {}
    recs: list[dict[str, Any]] = []
    codes = _failure_codes(failures)
    layers = _failure_layers(failures)
    agent_sub = agent.get("subscores") or {}
    backend_sub = backend.get("subscores") or {}
    agent_evidence = agent.get("evidence") or {}
    backend_evidence = backend.get("evidence") or {}

    if codes["missing_payload_fields"] or agent_evidence.get("missing_payload_errors", 0):
        count = max(codes["missing_payload_fields"], int(agent_evidence.get("missing_payload_errors") or 0))
        recs.append(_rec(
            title="Harden dispatcher payload discipline",
            layer="schema/custom_gpt_behavior",
            why="Dispatcher calls omitted required fields inside payload.",
            impact="high",
            effort="low",
            severity="high" if count > 1 else "medium",
            evidence={"count": count, "agent_tool_use_score": agent_sub.get("tool_use"), "failure_code": "missing_payload_fields"},
            affected_metrics=["tool_use", "recovery", "endpoint_reliability"],
            action_items=[
                "Keep payload required in dispatcher schema.",
                "Add examples for the most common repo/workspace/task payloads.",
                "Regression-test missing_payload_fields retry behavior.",
            ],
        ))

    unsupported = int(agent_evidence.get("unsupported_action_or_category") or codes["unsupported_action"] + codes["unsupported_category"])
    if unsupported:
        recs.append(_rec(
            title="Constrain Custom GPT to allowlisted dispatcher categories/actions",
            layer="instructions/knowledge/custom_gpt_behavior",
            why="The agent attempted unsupported actions or categories.",
            impact="high",
            effort="low",
            severity="medium",
            evidence={"count": unsupported, "allowed_categories": ["repo", "workspace", "patch", "test", "quality", "diagnostics", "policy", "tasks", "github", "env"]},
            affected_metrics=["tool_use", "safety"],
            action_items=[
                "Keep the short instruction warning against shell/files/git/package categories.",
                "Ensure dispatcher knowledge docs are attached to the GPT.",
                "Add a regression case for the unsupported category/action.",
            ],
        ))

    exit_127 = _count_exit_127(events)
    dependency_failures = max(codes["dependency_missing"], exit_127)
    if dependency_failures:
        recs.append(_rec(
            title="Improve missing dependency diagnosis and environment guidance",
            layer="backend_engine/repo_environment",
            why="A command failed because an executable or dependency was missing.",
            impact="medium",
            effort="low",
            severity="medium",
            evidence={"count": dependency_failures, "exit_127_count": exit_127, "quality_failures": _quality_failed(events)},
            affected_metrics=["quality_engine", "test_engine", "communication"],
            action_items=[
                "Classify exit code 127 as dependency_missing in test and quality results.",
                "Return a suggested /coding/env/action prepare_dry_run next step.",
                "Require explicit user approval before install/network-writing setup.",
            ],
        ))

    if codes["timeout"] or backend_evidence.get("timeouts", 0):
        count = max(codes["timeout"], int(backend_evidence.get("timeouts") or 0))
        recs.append(_rec(
            title="Reduce timeout risk with focused commands and clearer timeout guidance",
            layer="backend_engine/repo_environment",
            why="One or more subprocesses timed out.",
            impact="medium",
            effort="medium",
            severity="medium",
            evidence={"count": count},
            affected_metrics=["latency", "test_engine", "quality_engine"],
            action_items=[
                "Prefer focused tests before broad suites.",
                "Surface timeout_seconds in repair guidance.",
                "Track slow command names in eval reports.",
            ],
        ))

    endpoint_reliability = backend_sub.get("endpoint_reliability", 100)
    failed_actions = endpoint_stats.get("failed_count", 0)
    if endpoint_reliability < 95 or failed_actions:
        recs.append(_rec(
            title="Review endpoint reliability failures",
            layer="backend_route",
            why="Endpoint reliability is below target or action failures occurred.",
            impact="high",
            effort="medium",
            severity="high" if endpoint_reliability < 80 else "medium",
            evidence={"endpoint_reliability_score": endpoint_reliability, "failed_actions": failed_actions, "by_endpoint": endpoint_stats.get("by_endpoint", {})},
            affected_metrics=["endpoint_reliability", "agent_recovery"],
            action_items=[
                "Inspect action_failed events by endpoint.",
                "Add regression cases for repeated route failures.",
                "Return structured, retryable errors where appropriate.",
            ],
        ))

    latency_score = backend_sub.get("latency", 100)
    latency = _endpoint_latency(endpoint_stats)
    if latency_score < 90:
        recs.append(_rec(
            title="Profile slow endpoints and reduce initial response size",
            layer="backend_engine/backend_route",
            why="Latency score is below target.",
            impact="medium",
            effort="medium",
            severity="medium",
            evidence={"latency_score": latency_score, "latency_ms": latency},
            affected_metrics=["latency", "user_friction"],
            action_items=[
                "Inspect p95 and max endpoint latency.",
                "Keep task initialization compact by default.",
                "Move expensive repo intelligence behind explicit dispatcher calls.",
            ],
        ))

    repo_metrics = engine_metrics.get("repo_intelligence") or {}
    if repo_metrics.get("relevant_context_hit_rate") is not None and repo_metrics.get("relevant_context_hit_rate", 1) < 0.7:
        recs.append(_rec(
            title="Improve relevant context ranking",
            layer="backend_engine",
            why="Relevant context hit rate is below target.",
            impact="high",
            effort="medium",
            severity="medium",
            evidence={"relevant_context_hit_rate": repo_metrics.get("relevant_context_hit_rate"), "repo_metrics": repo_metrics},
            affected_metrics=["repo_intelligence", "coding_quality"],
            action_items=[
                "Use diagnostics, changed files, and test map as ranking signals.",
                "Track whether suggested files are later patched.",
                "Add repo-specific context regression cases.",
            ],
        ))

    policy_score = backend_sub.get("policy", 100)
    unsafe_allowed = [e for e in events if e.get("event_type") == "policy_evaluated" and e.get("risk") in {"high", "critical"} and e.get("allowed") is True]
    if policy_score < 95 or unsafe_allowed:
        recs.append(_rec(
            title="Audit policy decisions for safety and false positives",
            layer="safety/policy",
            why="Policy score is below target or high-risk actions were allowed.",
            impact="critical",
            effort="medium",
            severity="critical" if unsafe_allowed else "medium",
            evidence={"policy_score": policy_score, "unsafe_allowed_count": len(unsafe_allowed), "policy_events": backend_evidence.get("policy_events")},
            affected_metrics=["safety", "policy"],
            action_items=[
                "Review high/critical policy_evaluated events.",
                "Add regression tests for any unsafe allowance.",
                "Document acceptable policy tradeoffs in eval report.",
            ],
        ))

    if agent_sub.get("state_management", 100) < 90:
        recs.append(_rec(
            title="Improve task state persistence guidance",
            layer="instructions/custom_gpt_behavior",
            why="State management score is below target.",
            impact="high",
            effort="low",
            severity="medium",
            evidence={"state_management_score": agent_sub.get("state_management"), "event_counts": agent_evidence.get("event_counts")},
            affected_metrics=["state_management", "tool_use"],
            action_items=[
                "Keep instructions telling the GPT to save repo_path, task_id, and workspace_path.",
                "Add examples showing those values reused in dispatcher payloads.",
                "Add a state-management regression case if repeated.",
            ],
        ))

    if agent_sub.get("communication_readiness", 100) < 90:
        recs.append(_rec(
            title="Strengthen final answer contract checks",
            layer="instructions/custom_gpt_behavior",
            why="Communication readiness is below target.",
            impact="medium",
            effort="low",
            severity="low",
            evidence={"communication_readiness_score": agent_sub.get("communication_readiness")},
            affected_metrics=["communication", "final_answer_quality"],
            action_items=[
                "Require contract-report before final response.",
                "Use a fixed final answer checklist.",
                "Keep final_answer_contract eval in the release gate.",
            ],
        ))

    if not _has_event(events, "release_gate_completed") and len(events) > 0:
        recs.append(_rec(
            title="Run Phase 9 release gate before shipping changes",
            layer="evaluation",
            why="This trace does not include release_gate_completed evidence.",
            impact="medium",
            effort="low",
            severity="low",
            confidence=0.7,
            evidence={"event_count": len(events), "release_gate_completed": False},
            affected_metrics=["release_quality", "regression_prevention"],
            action_items=[
                "Run python evals/run_release_gate.py --repo-path /home/obsidian/Elevate_test before release.",
                "Compare the new report against the baseline.",
            ],
        ))

    if not recs:
        recs.append(_rec(
            title="Maintain current release gate and continue collecting traces",
            layer="evaluation",
            why="No high-priority issues were detected in this trace.",
            impact="medium",
            effort="low",
            severity="info",
            evidence={"agent_score": agent.get("score"), "backend_score": backend.get("score"), "event_count": len(events)},
            affected_metrics=["release_quality", "regression_prevention"],
            action_items=[
                "Keep running the release gate before schema/instruction/backend changes.",
                "Convert any future real Custom GPT failure into a regression case.",
            ],
        ))

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in recs:
        key = (rec["title"], rec["layer"])
        if key not in deduped or rec["roi_score"] > deduped[key]["roi_score"]:
            deduped[key] = rec
    ranked = sorted(deduped.values(), key=lambda r: (-r["roi_score"], LAYER_ORDER.get(str(r.get("layer", "")).split("/")[0], 99), r["title"]))
    for idx, rec in enumerate(ranked, 1):
        rec["priority"] = idx

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in ranked:
        primary_layer = str(rec.get("layer", "evaluation")).split("/")[0]
        grouped[primary_layer].append(rec)

    return {
        "version": PHASE10_VERSION,
        "summary": {
            "recommendation_count": len(ranked),
            "top_priority": ranked[0]["title"] if ranked else None,
            "failure_code_counts": dict(sorted(codes.items())),
            "failure_layer_counts": dict(sorted(layers.items())),
        },
        "ranked": ranked,
        "grouped": {k: v for k, v in sorted(grouped.items(), key=lambda item: LAYER_ORDER.get(item[0], 99))},
    }


def legacy_recommendation_list(engine_output: dict[str, Any]) -> list[dict[str, Any]]:
    """Compatibility helper for callers expecting a list."""
    return engine_output.get("ranked", [])
