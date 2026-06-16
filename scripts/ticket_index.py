#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TICKET_DIR = ROOT / "maintenance" / "tickets"
INDEX = ROOT / "maintenance" / "TICKET_INDEX.md"
TMP_PATTERNS = ("gpt-api*.md", "coding-agent*.md", "openapi*.md")
FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

VALID_STATUSES = {"open", "in_progress", "needs_verification", "resolved", "obsolete", "duplicate", "wontfix"}
ACTIVE_STATUSES = {"open", "in_progress", "needs_verification"}
CLOSED_STATUSES = {"resolved", "obsolete", "duplicate", "wontfix"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
REQUIRED_FIELDS = {
    "id",
    "status",
    "severity",
    "area",
    "created",
    "resolved_at",
    "resolved_by_commit",
    "verification_command",
    "verification_result",
    "resolution_summary",
}


def parse_front_matter(text: str) -> dict[str, str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def infer_area(name: str, text: str) -> str:
    haystack = f"{name} {text[:1000]}".lower()
    if "codeops" in haystack or "/code" in haystack:
        return "codeops"
    if "ngrok" in haystack or "production" in haystack or "port 8000" in haystack or "live" in haystack:
        return "deployment"
    if "patch" in haystack or ".env" in haystack:
        return "patch-safety"
    if "requests" in haystack or "requirements" in haystack or "dependency" in haystack:
        return "environment"
    if "openapi" in haystack or "schema" in haystack:
        return "schema"
    if "endpoint" in haystack or "404" in haystack or "route" in haystack:
        return "endpoint"
    if "timeout" in haystack or "hang" in haystack:
        return "runtime"
    if "git" in haystack or "push" in haystack or "remote" in haystack:
        return "release"
    if "command_too_long" in haystack or "command too long" in haystack or "kwargs" in haystack:
        return "tooling"
    return "maintenance"


def infer_severity(name: str, text: str) -> str:
    haystack = f"{name} {text[:1000]}".lower()
    if any(word in haystack for word in ["production", "hang", "timeout", "403", "404", "blocked", "blocker"]):
        return "high"
    if any(word in haystack for word in ["validator", "schema", "command_too_long", "dirty"]):
        return "medium"
    return "low"


def infer_status(name: str, text: str) -> str:
    haystack = f"{name} {text[:1200]}".lower()
    if "workaround" in haystack and "one-off" in haystack:
        return "obsolete"
    return "open"


def import_tmp_tickets() -> list[Path]:
    if os.environ.get("IMPORT_TMP_TICKETS", "").lower() not in {"1", "true", "yes"}:
        return []
    TICKET_DIR.mkdir(parents=True, exist_ok=True)
    imported: list[Path] = []
    for pattern in TMP_PATTERNS:
        for src in sorted(Path("/tmp").glob(pattern)):
            dest = TICKET_DIR / src.name
            if dest.exists():
                imported.append(dest)
                continue
            text = src.read_text(encoding="utf-8", errors="replace")
            ticket_id = src.stem
            area = infer_area(src.name, text)
            severity = infer_severity(src.name, text)
            front_matter = (
                "---\n"
                f"id: \"{ticket_id}\"\n"
                "status: \"open\"\n"
                f"severity: \"{severity}\"\n"
                f"area: \"{area}\"\n"
                f"created: \"{datetime.now(timezone.utc).date().isoformat()}\"\n"
                "resolved_at: \"\"\n"
                "resolved_by_commit: \"\"\n"
                "verification_command: \"Review imported ticket and assign lifecycle status.\"\n"
                "verification_result: \"not_run\"\n"
                "resolution_summary: \"Imported from /tmp; awaiting triage.\"\n"
                "---\n\n"
            )
            dest.write_text(text if FRONT_MATTER_RE.match(text) else front_matter + text, encoding="utf-8")
            imported.append(dest)
    return imported


def normalize_meta(path: Path, text: str) -> dict[str, str]:
    meta = parse_front_matter(text)
    ticket_id = meta.get("id", path.stem)
    status = meta.get("status") or infer_status(path.name, text)
    severity = meta.get("severity") or infer_severity(path.name, text)
    area = meta.get("area") or infer_area(path.name, text)
    out = {
        "id": ticket_id,
        "status": status,
        "severity": severity,
        "area": area,
        "created": meta.get("created", ""),
        "resolved_at": meta.get("resolved_at") or meta.get("resolved", ""),
        "resolved_by_commit": meta.get("resolved_by_commit", ""),
        "verification_command": meta.get("verification_command", ""),
        "verification_result": meta.get("verification_result", ""),
        "resolution_summary": meta.get("resolution_summary", ""),
    }
    return out


def validate_ticket(path: Path, meta: dict[str, str]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_FIELDS - set(meta)
    if missing:
        errors.append("missing_fields=" + ",".join(sorted(missing)))
    if meta.get("id") != path.stem:
        errors.append("id_mismatch")
    if meta.get("status") not in VALID_STATUSES:
        errors.append("invalid_status")
    if meta.get("severity") not in VALID_SEVERITIES:
        errors.append("invalid_severity")
    if not meta.get("area"):
        errors.append("missing_area")
    if not meta.get("created"):
        errors.append("missing_created")
    if meta.get("status") in CLOSED_STATUSES:
        if not meta.get("resolved_at"):
            errors.append("closed_missing_resolved_at")
        if not meta.get("resolution_summary"):
            errors.append("closed_missing_resolution_summary")
    if meta.get("status") in ACTIVE_STATUSES and not meta.get("verification_command"):
        errors.append("active_missing_next_verification")
    return errors


def ticket_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(TICKET_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = normalize_meta(path, text)
        title = first_heading(text, path.stem)
        errors = validate_ticket(path, meta)
        rows.append({**meta, "title": title, "file": path.name, "validation_errors": ";".join(errors)})
    return rows


def build_index() -> str:
    rows = ticket_rows()
    status_counts = Counter(row["status"] for row in rows)
    area_counts = Counter(row["area"] for row in rows if row["status"] in ACTIVE_STATUSES)
    severity_counts = Counter(row["severity"] for row in rows if row["status"] in ACTIVE_STATUSES)
    invalid = [row for row in rows if row["validation_errors"]]
    by_status: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_status[row["status"]].append(row)

    lines = [
        "# Maintainer Ticket Index",
        "",
        "Generated by: `scripts/ticket_index.py`",
        "",
        f"Ticket count: {len(rows)}",
        f"Active count: {sum(status_counts[s] for s in ACTIVE_STATUSES)}",
        f"Closed count: {sum(status_counts[s] for s in CLOSED_STATUSES)}",
        f"Invalid metadata count: {len(invalid)}",
        "",
        "## Status summary",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status in sorted(VALID_STATUSES):
        if status_counts[status]:
            lines.append(f"| {status} | {status_counts[status]} |")
    lines.extend(["", "## Active tickets by area", "", "| Area | Count |", "|---|---:|"])
    for area, count in sorted(area_counts.items()):
        lines.append(f"| {area} | {count} |")
    lines.extend(["", "## Active tickets by severity", "", "| Severity | Count |", "|---|---:|"])
    for severity, count in sorted(severity_counts.items()):
        lines.append(f"| {severity} | {count} |")
    lines.extend([
        "",
        "## Active ticket detail",
        "",
        "| Area | Severity | Status | ID | Title | Verification / Next Action | File |",
        "|---|---|---|---|---|---|---|",
    ])
    for row in sorted((r for r in rows if r["status"] in ACTIVE_STATUSES), key=lambda r: (r["area"], r["severity"], r["id"])):
        title = row["title"].replace("|", "/")
        verify = row["verification_command"].replace("|", "/")[:160]
        lines.append(f"| {row['area']} | {row['severity']} | {row['status']} | `{row['id']}` | {title} | {verify} | `maintenance/tickets/{row['file']}` |")
    lines.extend([
        "",
        "## Closed / historical ticket detail",
        "",
        "| Area | Severity | Status | ID | Title | Resolution | File |",
        "|---|---|---|---|---|---|---|",
    ])
    for row in sorted((r for r in rows if r["status"] in CLOSED_STATUSES), key=lambda r: (r["status"], r["area"], r["id"])):
        title = row["title"].replace("|", "/")
        resolution = row["resolution_summary"].replace("|", "/")[:160]
        lines.append(f"| {row['area']} | {row['severity']} | {row['status']} | `{row['id']}` | {title} | {resolution} | `maintenance/tickets/{row['file']}` |")
    if invalid:
        lines.extend(["", "## Metadata validation errors", "", "| ID | Errors |", "|---|---|"])
        for row in invalid:
            lines.append(f"| `{row['id']}` | {row['validation_errors']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    imported = import_tmp_tickets()
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(build_index(), encoding="utf-8")
    rows = ticket_rows()
    invalid = [row for row in rows if row["validation_errors"]]
    print(f"tickets_imported={len(imported)}")
    print(f"ticket_count={len(rows)}")
    print(f"invalid_metadata={len(invalid)}")
    print(f"index={INDEX}")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
