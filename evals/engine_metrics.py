from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any


def _events(events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [e for e in events if e.get("event_type") == event_type]


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _latencies(events: list[dict[str, Any]]) -> dict[str, Any]:
    vals = [float(e["latency_ms"]) for e in events if isinstance(e.get("latency_ms"), (int, float))]
    if not vals:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    return {
        "count": len(vals),
        "p50_ms": round(statistics.median(vals), 2),
        "p95_ms": round(statistics.quantiles(vals, n=20)[18] if len(vals) >= 20 else max(vals), 2),
        "max_ms": round(max(vals), 2),
    }


def repo_intelligence_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    overview = _events(events, "repo_overview_completed")
    relevant = _events(events, "repo_relevant_context_completed")
    instructions = _events(events, "repo_instructions_completed")
    tests_discovered = _events(events, "tests_discovered")
    route_maps = _events(events, "repo_route_map_completed")
    patched = {f for e in _events(events, "patch_applied") for f in (e.get("files_touched") or [])}
    suggested = {f for e in relevant for f in (e.get("suggested_files") or [])}
    hit = len(patched & suggested)
    return {
        "overview_count": len(overview),
        "instructions_count": len(instructions),
        "relevant_context_count": len(relevant),
        "route_map_count": len(route_maps),
        "test_discovery_count": len(tests_discovered),
        "latency": _latencies(overview + relevant + instructions + route_maps),
        "languages_detected": sorted({lang for e in overview for lang in (e.get("languages") or [])}),
        "frameworks_detected": sorted({fw for e in overview for fw in (e.get("frameworks") or [])}),
        "test_command_count": sum(int(e.get("command_count") or 0) for e in tests_discovered),
        "focused_test_count": sum(int(e.get("focused_count") or 0) for e in tests_discovered),
        "relevant_context_suggested_files": len(suggested),
        "patched_files": len(patched),
        "relevant_context_hit_rate": _rate(hit, len(patched)) if patched else None,
    }


def workspace_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    created = _events(events, "workspace_created")
    status = _events(events, "workspace_status_checked")
    diff = _events(events, "workspace_diff_checked") + _events(events, "workspace_diff_summary")
    destroyed = _events(events, "workspace_destroyed")
    committed = _events(events, "workspace_committed")
    return {
        "created_count": len(created),
        "status_count": len(status),
        "diff_count": len(diff),
        "destroyed_count": len(destroyed),
        "commit_count": len(committed),
        "dirty_status_count": sum(1 for e in status if e.get("dirty")),
        "changed_file_observations": sum(int(e.get("changed_count") or 0) for e in status + diff),
        "latency": _latencies(created + status + diff + destroyed + committed),
    }


def patch_engine_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    previews = _events(events, "patch_previewed")
    applies = _events(events, "patch_applied")
    reverts = _events(events, "patch_reverted")
    risks = _events(events, "patch_risk_validated")
    preview_ok = sum(1 for e in previews if e.get("applies") is True)
    apply_ok = sum(1 for e in applies if e.get("applied") is True)
    revert_ok = sum(1 for e in reverts if e.get("reverted") is True)
    files = {f for e in applies + previews + risks for f in (e.get("files_touched") or [])}
    return {
        "preview_count": len(previews),
        "preview_success_rate": _rate(preview_ok, len(previews)),
        "apply_count": len(applies),
        "apply_success_rate": _rate(apply_ok, len(applies)),
        "revert_count": len(reverts),
        "revert_success_rate": _rate(revert_ok, len(reverts)),
        "risk_validation_count": len(risks),
        "risk_block_count": sum(1 for e in risks if e.get("allowed") is False),
        "risk_item_count": sum(int(e.get("risk_count") or 0) for e in risks),
        "changed_files_observed": sorted(files),
        "max_patch_lines": max([int(e.get("line_count") or 0) for e in risks] or [0]),
        "latency": _latencies(previews + applies + reverts + risks),
    }


def test_quality_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    discovered = _events(events, "tests_discovered")
    tests = _events(events, "tests_run")
    quality = _events(events, "quality_run")
    subprocesses = _events(events, "subprocess_completed")
    missing = [e for e in subprocesses if e.get("not_found") or e.get("exit_code") == 127]
    timeouts = [e for e in subprocesses if e.get("timeout")]
    return {
        "test_discovery_count": len(discovered),
        "test_command_count": sum(int(e.get("command_count") or 0) for e in discovered),
        "test_run_count": len(tests),
        "test_pass_rate": _rate(sum(1 for e in tests if e.get("passed") is True), len(tests)),
        "quality_run_count": len(quality),
        "quality_pass_rate": _rate(sum(1 for e in quality if e.get("passed") is True), len(quality)),
        "subprocess_count": len(subprocesses),
        "missing_dependency_count": len(missing),
        "timeout_count": len(timeouts),
        "exit_code_counts": dict(sorted(Counter(str(e.get("exit_code")) for e in subprocesses if e.get("exit_code") is not None).items())),
        "missing_executables": sorted({str(e.get("executable")) for e in missing if e.get("executable")}),
        "latency": _latencies(tests + quality + subprocesses),
    }


def policy_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    policies = _events(events, "policy_evaluated")
    path_checks = _events(events, "policy_path_checked")
    blocks = [e for e in policies if e.get("allowed") is False]
    high_allowed = [e for e in policies if e.get("risk") in {"high", "critical"} and e.get("allowed") is True]
    by_action: dict[str, Counter] = defaultdict(Counter)
    for e in policies:
        action = str(e.get("action") or "unknown")
        by_action[action]["total"] += 1
        by_action[action]["allowed" if e.get("allowed") else "blocked"] += 1
    return {
        "policy_event_count": len(policies),
        "path_check_count": len(path_checks),
        "block_count": len(blocks),
        "allow_rate": _rate(sum(1 for e in policies if e.get("allowed") is True), len(policies)),
        "high_risk_allowed_count": len(high_allowed),
        "network_write_checks": sum(1 for e in policies if e.get("action") in {"create_pr", "push_branch", "comment_pr", "network_write"}),
        "by_action": {k: dict(v) for k, v in sorted(by_action.items())},
        "latency": _latencies(policies + path_checks),
    }


def engine_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "repo_intelligence": repo_intelligence_metrics(events),
        "workspace": workspace_metrics(events),
        "patch_engine": patch_engine_metrics(events),
        "test_quality_engine": test_quality_metrics(events),
        "policy_engine": policy_metrics(events),
    }


def engine_scores(metrics: dict[str, Any]) -> dict[str, Any]:
    repo = metrics.get("repo_intelligence", {})
    workspace = metrics.get("workspace", {})
    patch = metrics.get("patch_engine", {})
    tq = metrics.get("test_quality_engine", {})
    policy = metrics.get("policy_engine", {})
    scores = {
        "repo_intelligence": 100,
        "workspace": 100,
        "patch_engine": 100,
        "test_quality_engine": 100,
        "policy_engine": 100,
    }
    if repo.get("overview_count", 0) == 0:
        scores["repo_intelligence"] -= 35
    if repo.get("test_command_count", 0) == 0:
        scores["repo_intelligence"] -= 20
    if workspace.get("created_count", 0) == 0:
        scores["workspace"] -= 40
    if patch.get("apply_count", 0) and patch.get("preview_count", 0) == 0:
        scores["patch_engine"] -= 40
    if patch.get("risk_block_count", 0):
        scores["patch_engine"] -= min(25, 5 * int(patch.get("risk_block_count") or 0))
    if tq.get("missing_dependency_count", 0):
        scores["test_quality_engine"] -= min(25, 5 * int(tq.get("missing_dependency_count") or 0))
    if tq.get("timeout_count", 0):
        scores["test_quality_engine"] -= min(25, 10 * int(tq.get("timeout_count") or 0))
    if policy.get("policy_event_count", 0) == 0:
        scores["policy_engine"] -= 20
    if policy.get("high_risk_allowed_count", 0):
        scores["policy_engine"] -= 80
    scores = {k: max(0, min(100, int(v))) for k, v in scores.items()}
    overall = round(sum(scores.values()) / max(1, len(scores)))
    return {"overall": overall, "subscores": scores}
