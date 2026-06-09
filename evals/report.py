from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

from utils import eval_telemetry
from evals.engine_metrics import engine_metrics, engine_scores
from evals.scoring import classify_failures, endpoint_stats, score_agent, score_backend
from evals.recommendations import generate_recommendations


def load_events(path: str | Path | None = None, *, task_id: str | None = None, run_id: str | None = None) -> list[dict[str, Any]]:
    event_path = Path(path) if path else eval_telemetry.events_path()
    if not event_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_no, line in enumerate(event_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            events.append({"event_type": "telemetry_parse_error", "line_no": line_no, "raw_preview": line[:200]})
            continue
        if task_id and event.get("task_id") != task_id:
            continue
        if run_id and event.get("run_id") != run_id:
            continue
        events.append(event)
    return events


def _unique(events: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({str(e.get(key)) for e in events if e.get(key) not in (None, "")})


def _time_bounds(events: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps = [e.get("timestamp") for e in events if isinstance(e.get("timestamp"), int)]
    if not timestamps:
        return {"started_at": None, "ended_at": None, "duration_ms": None}
    return {"started_at": min(timestamps), "ended_at": max(timestamps), "duration_ms": max(timestamps) - min(timestamps)}


def build_report(events: list[dict[str, Any]], *, report_id: str | None = None, source_path: str | None = None) -> dict[str, Any]:
    report_id = report_id or f"eval_{time.strftime('%Y%m%d_%H%M%S')}"
    agent = score_agent(events)
    backend = score_backend(events)
    failures = classify_failures(events)
    counts = Counter(str(e.get("event_type")) for e in events)
    endpoints = endpoint_stats(events)
    summary = {
        "report_id": report_id,
        "source_path": source_path,
        "event_count": len(events),
        "backend_commits": _unique(events, "backend_commit"),
        "schema_versions": _unique(events, "schema_version"),
        "task_ids": _unique(events, "task_id"),
        "repo_paths": _unique(events, "repo_path"),
        "workspace_paths": _unique(events, "workspace_path"),
        **_time_bounds(events),
    }
    engines = engine_metrics(events)
    recommendation_engine = generate_recommendations(events, agent=agent, backend=backend, failures=failures, endpoint_stats=endpoints, engine_metrics=engines)
    report = {
        "summary": summary,
        "scores": {"agent": agent, "backend": backend, "engines": engine_scores(engines)},
        "engine_metrics": engines,
        "event_type_counts": dict(sorted(counts.items())),
        "endpoint_stats": endpoints,
        "failures": failures,
        "recommendation_engine": recommendation_engine,
        "recommendations": recommendation_engine.get("ranked", []),
        "recommendations_grouped": recommendation_engine.get("grouped", {}),
        "events_sample": events[:20],
    }
    return report


def write_json_report(report: dict[str, Any], output_path: str | Path | None = None) -> Path:
    root = eval_telemetry.eval_root() / "reports"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(output_path) if output_path else root / f"{report['summary']['report_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _table(rows: list[list[Any]], headers: list[str]) -> str:
    all_rows = [headers] + [["" if c is None else str(c) for c in row] for row in rows]
    widths = [max(len(row[i]) for row in all_rows) for i in range(len(headers))]
    def fmt(row: list[Any]) -> str:
        vals = ["" if c is None else str(c) for c in row]
        return "| " + " | ".join(vals[i].ljust(widths[i]) for i in range(len(headers))) + " |"
    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    return "\n".join([fmt(headers), sep] + [fmt(row) for row in rows])


def markdown_report(report: dict[str, Any]) -> str:
    s = report["summary"]
    agent = report["scores"]["agent"]
    backend = report["scores"]["backend"]
    lines: list[str] = []
    lines.append(f"# Coding GPT Evaluation Report: {s['report_id']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(_table([
        ["Events", s.get("event_count")],
        ["Agent score", agent.get("score")],
        ["Backend score", backend.get("score")],
        ["Duration ms", s.get("duration_ms")],
        ["Task ids", ", ".join(s.get("task_ids") or [])],
        ["Repos", ", ".join(s.get("repo_paths") or [])],
        ["Backend commits", ", ".join(s.get("backend_commits") or [])],
        ["Schema versions", ", ".join(s.get("schema_versions") or [])],
    ], ["Metric", "Value"]))
    lines.append("")
    lines.append("## Scores")
    lines.append("")
    lines.append("### Agent")
    lines.append("")
    lines.append(_table([[k, v] for k, v in agent.get("subscores", {}).items()], ["Subscore", "Score"]))
    lines.append("")
    lines.append("### Backend")
    lines.append("")
    lines.append(_table([[k, v] for k, v in backend.get("subscores", {}).items()], ["Subscore", "Score"]))
    lines.append("")
    lines.append("## Endpoint reliability")
    lines.append("")
    ep = report.get("endpoint_stats", {})
    lines.append(_table([
        ["Endpoint event count", ep.get("endpoint_event_count")],
        ["Completed actions", ep.get("completed_count")],
        ["Failed actions", ep.get("failed_count")],
        ["Success rate", round(float(ep.get("success_rate", 0)) * 100, 2)],
        ["Latency p50 ms", (ep.get("latency_ms") or {}).get("p50")],
        ["Latency p95 ms", (ep.get("latency_ms") or {}).get("p95")],
        ["Latency max ms", (ep.get("latency_ms") or {}).get("max")],
    ], ["Metric", "Value"]))
    lines.append("")
    by_endpoint = ep.get("by_endpoint", {})
    if by_endpoint:
        rows = []
        for endpoint, counts in by_endpoint.items():
            rows.append([endpoint, counts.get("action_called", 0), counts.get("action_completed", 0), counts.get("action_failed", 0), counts.get("dispatcher_called", 0)])
        lines.append(_table(rows, ["Endpoint", "Called", "Completed", "Failed", "Dispatcher called"]))
        lines.append("")
    lines.append("## Backend engine metrics")
    lines.append("")
    eng_scores = report.get("scores", {}).get("engines", {})
    lines.append(_table([["overall", eng_scores.get("overall")]] + [[k, v] for k, v in (eng_scores.get("subscores") or {}).items()], ["Engine", "Score"]))
    lines.append("")
    for engine_name, data in (report.get("engine_metrics") or {}).items():
        lines.append(f"### {engine_name}")
        rows = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)[:500]
            rows.append([key, value])
        lines.append(_table(rows, ["Metric", "Value"]))
        lines.append("")

    lines.append("## Failures")
    lines.append("")
    failures = report.get("failures", [])
    if failures:
        lines.append(_table([[f.get("severity"), f.get("layer"), f.get("code"), f.get("recommendation")] for f in failures], ["Severity", "Layer", "Code", "Recommendation"]))
    else:
        lines.append("No failures classified from telemetry.")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    rec_engine = report.get("recommendation_engine", {})
    if rec_engine.get("summary"):
        lines.append(_table([[k, v] for k, v in rec_engine.get("summary", {}).items()], ["Metric", "Value"]))
        lines.append("")
    recs = report.get("recommendations", [])
    lines.append(_table([[r.get("priority"), r.get("roi_score"), r.get("layer"), r.get("title"), r.get("impact"), r.get("effort"), r.get("why")] for r in recs], ["Priority", "ROI", "Layer", "Title", "Impact", "Effort", "Why"]))
    lines.append("")
    grouped = report.get("recommendations_grouped", {})
    if grouped:
        lines.append("### Recommendations by owner layer")
        lines.append("")
        for layer, layer_recs in grouped.items():
            lines.append(f"#### {layer}")
            lines.append("")
            lines.append(_table([[r.get("priority"), r.get("title"), "; ".join(r.get("affected_metrics", [])), "; ".join(r.get("action_items", [])[:2])] for r in layer_recs], ["Priority", "Title", "Metrics", "First actions"]))
            lines.append("")
    lines.append("## Event type counts")
    lines.append("")
    lines.append(_table([[k, v] for k, v in report.get("event_type_counts", {}).items()], ["Event type", "Count"]))
    lines.append("")
    return "\n".join(lines)


def write_markdown_report(report: dict[str, Any], output_path: str | Path | None = None) -> Path:
    root = eval_telemetry.eval_root() / "reports"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(output_path) if output_path else root / f"{report['summary']['report_id']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_report(report), encoding="utf-8")
    return path


def generate_report(events_path: str | Path | None = None, *, task_id: str | None = None, run_id: str | None = None, report_id: str | None = None) -> dict[str, Any]:
    events = load_events(events_path, task_id=task_id, run_id=run_id)
    source = str(events_path or eval_telemetry.events_path())
    report = build_report(events, report_id=report_id, source_path=source)
    json_path = write_json_report(report)
    md_path = write_markdown_report(report)
    report["summary"]["report_json"] = str(json_path)
    report["summary"]["report_md"] = str(md_path)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Coding GPT eval report from telemetry events.jsonl")
    parser.add_argument("--events", default=None, help="Path to events.jsonl. Defaults to EVAL_TELEMETRY_EVENTS or /tmp/gpt-api-evals/events.jsonl")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--report-id", default=None)
    args = parser.parse_args(argv)
    report = generate_report(args.events, task_id=args.task_id, run_id=args.run_id, report_id=args.report_id)
    print(json.dumps({
        "report_id": report["summary"]["report_id"],
        "event_count": report["summary"]["event_count"],
        "agent_score": report["scores"]["agent"]["score"],
        "backend_score": report["scores"]["backend"]["score"],
        "report_json": report["summary"].get("report_json"),
        "report_md": report["summary"].get("report_md"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
