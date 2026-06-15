from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from utils import eval_telemetry


PYTEST_FAILED_RE = re.compile(r"FAILED\s+([^\s:]+)(?:::([^\s]+))?")
TRACE_RE = re.compile(r'File "([^"]+)", line (\d+)')
MYPY_RE = re.compile(r"^([^:\n]+):(\d+):(?:(\d+):)?\s*(error|note):\s*(.*)$", re.MULTILINE)
RUFF_RE = re.compile(r"^([^:\n]+):(\d+):(\d+):\s*([A-Z]+\d+)\s+(.*)$", re.MULTILINE)
ESLINT_RE = re.compile(r"^\s*(\d+):(\d+)\s+(error|warning)\s+(.*?)\s+([\w@/-]+)\s*$", re.MULTILINE)
TSC_RE = re.compile(r"([^\s()]+)\((\d+),(\d+)\):\s*error\s+(TS\d+):\s*(.*)")
GO_RE = re.compile(r"^--- FAIL: ([^\s]+).*|^\s*([^:\n]+\.go):(\d+):\s*(.*)$", re.MULTILINE)
CARGO_RE = re.compile(r"-->\s+([^:\n]+):(\d+):(\d+)|error(?:\[[^\]]+\])?:\s*(.*)")


def parse(tool: str, stdout: str = "", stderr: str = "") -> dict[str, Any]:
    text = (stdout or "") + "\n" + (stderr or "")
    tool = (tool or "unknown").lower()
    diagnostics: list[dict[str, Any]] = []

    if tool in {"pytest", "python", "test"}:
        for m in PYTEST_FAILED_RE.finditer(text):
            diagnostics.append({"tool": "pytest", "file": m.group(1), "test": m.group(2), "severity": "error", "message": "pytest failure"})
        for m in TRACE_RE.finditer(text):
            diagnostics.append({"tool": "python", "file": m.group(1), "line": int(m.group(2)), "severity": "error", "message": "traceback location"})
    if tool in {"mypy", "python", "quality"}:
        for m in MYPY_RE.finditer(text):
            diagnostics.append({"tool": "mypy", "file": m.group(1), "line": int(m.group(2)), "column": int(m.group(3) or 0), "severity": m.group(4), "message": m.group(5)})
    if tool in {"ruff", "flake8", "python", "quality"}:
        for m in RUFF_RE.finditer(text):
            diagnostics.append({"tool": "ruff", "file": m.group(1), "line": int(m.group(2)), "column": int(m.group(3)), "code": m.group(4), "severity": "error", "message": m.group(5)})
    if tool in {"eslint", "javascript", "typescript", "quality"}:
        current_file = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped[0].isdigit() and (stripped.endswith((".js", ".ts", ".tsx", ".jsx")) or "/" in stripped):
                current_file = stripped
            m = ESLINT_RE.match(line)
            if m and current_file:
                diagnostics.append({"tool": "eslint", "file": current_file, "line": int(m.group(1)), "column": int(m.group(2)), "severity": m.group(3), "message": m.group(4), "code": m.group(5)})
    if tool in {"tsc", "typescript", "quality"}:
        for m in TSC_RE.finditer(text):
            diagnostics.append({"tool": "tsc", "file": m.group(1), "line": int(m.group(2)), "column": int(m.group(3)), "code": m.group(4), "severity": "error", "message": m.group(5)})
    if tool in {"go", "go test", "quality"}:
        for m in GO_RE.finditer(text):
            if m.group(1):
                diagnostics.append({"tool": "go test", "test": m.group(1), "severity": "error", "message": "go test failure"})
            elif m.group(2):
                diagnostics.append({"tool": "go", "file": m.group(2), "line": int(m.group(3)), "severity": "error", "message": m.group(4)})
    if tool in {"cargo", "rust", "quality"}:
        last_error = None
        for m in CARGO_RE.finditer(text):
            if m.group(4):
                last_error = m.group(4)
            elif m.group(1):
                diagnostics.append({"tool": "cargo", "file": m.group(1), "line": int(m.group(2)), "column": int(m.group(3)), "severity": "error", "message": last_error or "rust compiler error"})

    out = {"tool": tool, "diagnostics": diagnostics[:200], "count": len(diagnostics)}
    eval_telemetry.log_event("diagnostics_parsed", tool=tool, diagnostic_count=len(diagnostics))
    return out


def suggest_context(diagnostics: list[dict[str, Any]], max_files: int = 20) -> dict[str, Any]:
    files: Counter[str] = Counter()
    tests: list[str] = []
    for item in diagnostics:
        file = item.get("file")
        if file:
            files[str(file)] += 3 if str(file).startswith("tests/") or "/tests/" in str(file) else 2
            p = Path(str(file))
            if p.name.startswith("test_"):
                stem = p.name.replace("test_", "").replace(".py", ".py")
                files[stem] += 1
        if item.get("test"):
            tests.append(str(item["test"]))
    ranked = [f for f, _ in files.most_common(max_files)]
    return {"files": ranked, "tests": tests[:50], "reason": "Ranked from diagnostics, tracebacks, and test/source file naming heuristics."}


def triage(diagnostics: list[dict[str, Any]], task: str | None = None, max_files: int = 20) -> dict[str, Any]:
    files = Counter()
    tests = []
    symbols = Counter()
    categories = Counter()
    messages = []
    for d in diagnostics or []:
        tool = str(d.get("tool", "")).lower()
        msg = str(d.get("message", ""))
        messages.append(msg)
        f = d.get("file")
        if f:
            fs = str(f)
            files[fs] += 5
            if fs.startswith("tests/") or "/tests/" in fs or Path(fs).name.startswith("test_"):
                tests.append(fs)
                source_guess = Path(fs).name.replace("test_", "").replace(".py", ".py")
                files[source_guess] += 2
        if d.get("test"): tests.append(str(d["test"]))
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", msg)[:20]:
            if token.lower() not in {"assert", "error", "failed", "none", "true", "false"}:
                symbols[token] += 1
        if tool in {"pytest", "unittest"} or "assert" in msg.lower(): categories["test_assertion_failure"] += 1
        if "import" in msg.lower() or "module" in msg.lower(): categories["import_or_dependency_failure"] += 1
        if "type" in msg.lower() or tool in {"mypy", "pyright", "tsc"}: categories["type_error"] += 1
        if tool in {"ruff", "flake8", "eslint"}: categories["lint_failure"] += 1
        if "permission" in msg.lower() or "auth" in msg.lower() or "token" in msg.lower(): categories["auth_or_permission_failure"] += 1
    if task:
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", task)[:30]:
            symbols[token] += 1
    category = categories.most_common(1)[0][0] if categories else "unknown_failure"
    ranked_files = [f for f, _ in files.most_common(max_files)]
    ranked_symbols = [s for s, _ in symbols.most_common(20)]
    out = {
        "failure_category": category,
        "source_files": [f for f in ranked_files if not (f.startswith("tests/") or "/tests/" in f)][:max_files],
        "test_files": list(dict.fromkeys(tests))[:max_files],
        "symbols": ranked_symbols,
        "next_context": ranked_files[:max_files],
        "repair_strategy": _repair_strategy(category),
        "diagnostic_count": len(diagnostics or []),
    }
    eval_telemetry.log_event("diagnostics_triaged", failure_category=category, diagnostic_count=len(diagnostics or []), next_context=ranked_files[:max_files])
    return out


def _repair_strategy(category: str) -> str:
    return {
        "test_assertion_failure": "Read failing test and source implementation, patch behavior minimally, rerun focused test.",
        "import_or_dependency_failure": "Inspect imports/manifests and avoid installing dependencies unless explicitly approved.",
        "type_error": "Read typed function signatures and call sites, patch type mismatch minimally.",
        "lint_failure": "Apply formatting or lint-specific minimal correction, then rerun quality command.",
        "auth_or_permission_failure": "Inspect auth policy and route boundaries; avoid weakening safety rules.",
    }.get(category, "Gather focused context from diagnostic files, patch minimally, rerun checks.")
