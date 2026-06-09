from __future__ import annotations

import html
import json
import time
from pathlib import Path
from typing import Any

from utils import eval_telemetry

DASHBOARD_VERSION = "phase11_dashboard_v1"


def reports_root() -> Path:
    root = eval_telemetry.eval_root() / "reports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _report_files() -> list[Path]:
    return sorted(reports_root().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def load_report(report_id: str) -> dict[str, Any]:
    path = reports_root() / f"{report_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {report_id}")
    data = _load_json(path)
    if data is None:
        raise ValueError(f"Report is not valid JSON: {report_id}")
    return data


def _score(report: dict[str, Any], section: str) -> int | None:
    value = report.get("scores", {}).get(section, {}).get("score")
    return int(value) if isinstance(value, (int, float)) else None


def _summary(report: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    summary = report.get("summary", {})
    recs = report.get("recommendations") or []
    failures = report.get("failures") or []
    endpoint_stats = report.get("endpoint_stats") or {}
    return {
        "report_id": summary.get("report_id") or (path.stem if path else None),
        "path": str(path) if path else None,
        "modified_at": int(path.stat().st_mtime * 1000) if path and path.exists() else None,
        "event_count": summary.get("event_count", 0),
        "duration_ms": summary.get("duration_ms"),
        "task_ids": summary.get("task_ids") or [],
        "repo_paths": summary.get("repo_paths") or [],
        "workspace_paths": summary.get("workspace_paths") or [],
        "backend_commits": summary.get("backend_commits") or [],
        "schema_versions": summary.get("schema_versions") or [],
        "agent_score": _score(report, "agent"),
        "backend_score": _score(report, "backend"),
        "engine_score": report.get("scores", {}).get("engines", {}).get("overall"),
        "failure_count": len(failures),
        "recommendation_count": len(recs),
        "top_recommendation": recs[0].get("title") if recs else None,
        "endpoint_success_rate": endpoint_stats.get("success_rate"),
        "endpoint_failed_count": endpoint_stats.get("failed_count"),
        "report_json": summary.get("report_json") or (str(path) if path else None),
        "report_md": summary.get("report_md"),
    }


def list_reports(
    *,
    limit: int = 25,
    repo_path: str | None = None,
    task_id: str | None = None,
    min_agent_score: int | None = None,
    min_backend_score: int | None = None,
    failure_layer: str | None = None,
    endpoint: str | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    skipped_invalid = 0
    for path in _report_files():
        report = _load_json(path)
        if report is None:
            skipped_invalid += 1
            continue
        summary = _summary(report, path)
        if repo_path and repo_path not in summary.get("repo_paths", []):
            continue
        if task_id and task_id not in summary.get("task_ids", []):
            continue
        if min_agent_score is not None and (summary.get("agent_score") is None or summary.get("agent_score") < min_agent_score):
            continue
        if min_backend_score is not None and (summary.get("backend_score") is None or summary.get("backend_score") < min_backend_score):
            continue
        if failure_layer:
            layers = {str(f.get("layer") or "") for f in report.get("failures", [])}
            if not any(failure_layer in layer for layer in layers):
                continue
        if endpoint:
            endpoints = set((report.get("endpoint_stats") or {}).get("by_endpoint", {}).keys())
            if endpoint not in endpoints:
                continue
        items.append(summary)
        if len(items) >= max(1, min(limit, 200)):
            break
    return {
        "status": 200,
        "version": DASHBOARD_VERSION,
        "reports_root": str(reports_root()),
        "count": len(items),
        "skipped_invalid": skipped_invalid,
        "reports": items,
    }


def latest_report() -> dict[str, Any]:
    listing = list_reports(limit=1)
    if not listing["reports"]:
        return {"status": 404, "error": {"code": "no_reports", "message": "No eval reports found."}}
    report_id = listing["reports"][0]["report_id"]
    return {"status": 200, "report": load_report(report_id), "summary": listing["reports"][0]}


def trend(limit: int = 20) -> dict[str, Any]:
    listing = list_reports(limit=limit)
    series = list(reversed(listing["reports"]))
    points = []
    for item in series:
        points.append({
            "report_id": item.get("report_id"),
            "modified_at": item.get("modified_at"),
            "agent_score": item.get("agent_score"),
            "backend_score": item.get("backend_score"),
            "engine_score": item.get("engine_score"),
            "failure_count": item.get("failure_count"),
            "endpoint_success_rate": item.get("endpoint_success_rate"),
            "top_recommendation": item.get("top_recommendation"),
        })
    return {"status": 200, "version": DASHBOARD_VERSION, "points": points, "count": len(points)}


def compare(current_report_id: str, baseline_report_id: str) -> dict[str, Any]:
    current = load_report(current_report_id)
    baseline = load_report(baseline_report_id)
    cur = _summary(current)
    base = _summary(baseline)
    current_failures = {str(f.get("code") or "unknown") for f in current.get("failures", [])}
    baseline_failures = {str(f.get("code") or "unknown") for f in baseline.get("failures", [])}
    return {
        "status": 200,
        "version": DASHBOARD_VERSION,
        "current": cur,
        "baseline": base,
        "deltas": {
            "agent_score": (cur.get("agent_score") or 0) - (base.get("agent_score") or 0),
            "backend_score": (cur.get("backend_score") or 0) - (base.get("backend_score") or 0),
            "engine_score": (cur.get("engine_score") or 0) - (base.get("engine_score") or 0),
            "failure_count": (cur.get("failure_count") or 0) - (base.get("failure_count") or 0),
            "recommendation_count": (cur.get("recommendation_count") or 0) - (base.get("recommendation_count") or 0),
        },
        "new_failure_codes": sorted(current_failures - baseline_failures),
        "fixed_failure_codes": sorted(baseline_failures - current_failures),
    }


def _fmt_ts(ms: int | None) -> str:
    if not ms:
        return ""
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ms / 1000))
    except Exception:
        return str(ms)


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["<table>", "<thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr></thead>", "<tbody>"]
    for row in rows:
        out.append("<tr>" + "".join(f"<td>{html.escape('' if c is None else str(c))}</td>" for c in row) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def render_html(limit: int = 25) -> str:
    listing = list_reports(limit=limit)
    latest = listing["reports"][0] if listing["reports"] else None
    tr = trend(limit=min(limit, 50))["points"]
    rows = []
    for r in listing["reports"]:
        rows.append([
            r.get("report_id"),
            _fmt_ts(r.get("modified_at")),
            r.get("agent_score"),
            r.get("backend_score"),
            r.get("engine_score"),
            r.get("failure_count"),
            round(float(r.get("endpoint_success_rate") or 0) * 100, 2),
            r.get("top_recommendation"),
        ])
    trend_rows = [[p.get("report_id"), p.get("agent_score"), p.get("backend_score"), p.get("engine_score"), p.get("failure_count")] for p in tr]
    latest_cards = ""
    if latest:
        latest_cards = f"""
        <div class='cards'>
          <div class='card'><b>Latest report</b><span>{html.escape(str(latest.get('report_id')))}</span></div>
          <div class='card'><b>Agent</b><span>{html.escape(str(latest.get('agent_score')))}</span></div>
          <div class='card'><b>Backend</b><span>{html.escape(str(latest.get('backend_score')))}</span></div>
          <div class='card'><b>Failures</b><span>{html.escape(str(latest.get('failure_count')))}</span></div>
        </div>
        """
    return f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <title>Coding GPT Eval Dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f8fafc; color: #0f172a; }}
    h1, h2 {{ margin-bottom: .4rem; }}
    code {{ background: #e2e8f0; padding: .15rem .3rem; border-radius: .25rem; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 1rem 0 2rem; }}
    th, td {{ border: 1px solid #cbd5e1; padding: .5rem; text-align: left; vertical-align: top; }}
    th {{ background: #e2e8f0; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; margin: 1rem 0 2rem; }}
    .card {{ background: white; border: 1px solid #cbd5e1; border-radius: .7rem; padding: 1rem; }}
    .card b {{ display: block; color: #475569; font-size: .9rem; }}
    .card span {{ display: block; font-size: 1.35rem; margin-top: .4rem; }}
    .muted {{ color: #64748b; }}
  </style>
</head>
<body>
  <h1>Coding GPT Eval Dashboard</h1>
  <p class='muted'>Version <code>{html.escape(DASHBOARD_VERSION)}</code>. Reports root: <code>{html.escape(str(reports_root()))}</code>.</p>
  {latest_cards}
  <h2>Recent reports</h2>
  {_table(['Report', 'Modified', 'Agent', 'Backend', 'Engine', 'Failures', 'Endpoint success %', 'Top recommendation'], rows)}
  <h2>Trend</h2>
  {_table(['Report', 'Agent', 'Backend', 'Engine', 'Failures'], trend_rows)}
</body>
</html>"""


def render_markdown(limit: int = 25) -> str:
    listing = list_reports(limit=limit)
    lines = ["# Coding GPT Eval Dashboard", "", f"Version: `{DASHBOARD_VERSION}`", f"Reports root: `{reports_root()}`", ""]
    if not listing["reports"]:
        lines.append("No reports found.")
        return "\n".join(lines)
    latest = listing["reports"][0]
    lines += [
        "## Latest",
        "",
        f"- Report: `{latest.get('report_id')}`",
        f"- Agent score: `{latest.get('agent_score')}`",
        f"- Backend score: `{latest.get('backend_score')}`",
        f"- Engine score: `{latest.get('engine_score')}`",
        f"- Failures: `{latest.get('failure_count')}`",
        f"- Top recommendation: {latest.get('top_recommendation') or 'None'}",
        "",
        "## Recent reports",
        "",
        "| Report | Agent | Backend | Engine | Failures | Endpoint success | Top recommendation |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in listing["reports"]:
        lines.append(f"| `{r.get('report_id')}` | {r.get('agent_score')} | {r.get('backend_score')} | {r.get('engine_score')} | {r.get('failure_count')} | {round(float(r.get('endpoint_success_rate') or 0)*100,2)}% | {str(r.get('top_recommendation') or '').replace('|','/')} |")
    return "\n".join(lines) + "\n"
