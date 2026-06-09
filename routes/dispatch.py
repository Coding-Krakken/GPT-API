"""Route: /dispatch — Boomerang dispatcher for the multi-agent pipeline.

Full lifecycle per call:
  1. Receives dispatch request from Chief of Staff GPT action
  2. Assigns issue number if missing (auto-increment from task-state/)
  3. Fires run_dispatcher.py inside gptapi-playwright-novnc container
  4. Playwright navigates to target agent GPT, sends prompt
  5. Auto-clicks ALL Confirm / Always-allow dialogs in target agent session
  6. Waits for full agent response (up to max_wait_seconds)
  7. Extracts complete agent output text
  8. Persists any YAML/file blocks found in output to disk
  9. Returns agent output PLUS explicit pipeline guidance:
       next_required_dispatch, must_continue, pipeline_stage_number, instruction
  10. CoS reads the JSON, sees must_continue=true, immediately calls
      dispatchToAgent again for the next stage — completing the pipeline loop.

The response JSON is the complete boomerang — the CoS never needs to reason
about "what comes next"; the instruction field tells it exactly what to call.
"""
from __future__ import annotations

import asyncio
import glob
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from utils.auth import verify_key
from utils.audit import log_api_action

# Try to import the structured pipeline logger (lives in ChatGPT/functions/)
import sys as _sys
_here = Path(__file__).resolve().parent.parent / "ChatGPT" / "functions"
if str(_here) not in _sys.path:
    _sys.path.insert(0, str(_here))

try:
    from pipeline_logger import log_file_written, log_event as _log_pipeline_event, log_error as _log_pipeline_error
except ImportError:
    def log_file_written(*a, **k): pass
    def _log_pipeline_event(*a, **k): pass
    def _log_pipeline_error(*a, **k): pass

router = APIRouter()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONTAINER_NAME = os.environ.get("PLAYWRIGHT_CONTAINER", "gptapi-playwright-novnc")
DISPATCHER_SCRIPT = os.environ.get(
    "DISPATCHER_SCRIPT", "/work/ChatGPT/functions/run_dispatcher.py"
)
SESSION_TOKEN_PATH_0 = os.environ.get(
    "CHATGPT_SESSION_TOKEN_PATH_0", "/work/.chatgpt_session_token.0"
)
SESSION_TOKEN_PATH_1 = os.environ.get(
    "CHATGPT_SESSION_TOKEN_PATH_1", "/work/.chatgpt_session_token.1"
)
DEFAULT_TIMEOUT = int(os.environ.get("DISPATCH_TIMEOUT_SECONDS", "420"))

# Canonical pipeline order — used to compute next_required_dispatch
PIPELINE_STAGES = [
    "product-owner",
    "solution-architect",
    "tech-lead",
    "backend-engineer",
    "qa-test-engineer",
    "security-engineer",
    "quality-director",
]

# Flexible downstream routing (non-standard engineer variants map to qa)
_DOWNSTREAM: dict[str, Optional[str]] = {
    "product-owner":              "solution-architect",
    "solution-architect":         "tech-lead",
    "tech-lead":                  "backend-engineer",
    "backend-engineer":           "qa-test-engineer",
    "frontend-engineer":          "qa-test-engineer",
    "platform-engineer":          "qa-test-engineer",
    "data-engineer":              "qa-test-engineer",
    "ml-engineer":                "qa-test-engineer",
    "devops-engineer":            "qa-test-engineer",
    "qa-test-engineer":           "security-engineer",
    "security-engineer":          "quality-director",
    "quality-director":           None,   # terminal — pipeline complete
}

# Where to persist known stage artifacts relative to repo root
_STAGE_OUTPUT_PATHS: dict[str, str] = {
    "solution-architect": ".github/.system-state/model/system_state_model.yaml",
    "product-owner":      ".github/.system-state/model/requirements.md",
    "security-engineer":  ".github/.system-state/security/threat_model.yaml",
    "quality-director":   ".github/.system-state/delivery/quality_gate_report.md",
}

# Repo root on the host (where this file lives two levels up)
_REPO_ROOT = Path(__file__).resolve().parent.parent
_TASK_STATE_DIR = _REPO_ROOT / "ChatGPT" / "task-state"


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class DispatchRequest(BaseModel):
    # Required
    to: str       # Target agent ID, e.g. "tech-lead"
    prompt: str   # Full prompt text to send to the target agent

    # Optional — issue is auto-assigned if missing
    issue: Optional[int] = None
    from_agent: Optional[str] = None   # Sending agent ID ("00-chief-of-staff")
    dry_run: bool = False
    max_wait_seconds: int = DEFAULT_TIMEOUT
    output_file_path: Optional[str] = None  # Override artifact output path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_token(path: str) -> Optional[str]:
    host_path = path.replace("/work/", str(_REPO_ROOT) + "/", 1)
    try:
        text = Path(host_path).read_text(encoding="utf-8").strip()
        return text if text else None
    except FileNotFoundError:
        return None


def _next_issue_number() -> int:
    """Return max existing issue number + 1 by scanning task-state/*.json."""
    try:
        files = glob.glob(str(_TASK_STATE_DIR / "[0-9]*.json"))
        if not files:
            return 1
        nums = [
            int(Path(f).stem)
            for f in files
            if Path(f).stem.isdigit()
        ]
        return max(nums) + 1 if nums else 1
    except Exception:
        return int(time.time()) % 100000  # fallback: timestamp-based


def _pipeline_meta(agent: str, ok: bool, agent_output: str) -> dict:
    """Build the pipeline guidance block that the CoS reads to know next steps."""
    next_stage = _DOWNSTREAM.get(agent)
    is_canonical = agent in PIPELINE_STAGES
    stage_num = (PIPELINE_STAGES.index(agent) + 1) if is_canonical else -1
    total = len(PIPELINE_STAGES)
    remaining = PIPELINE_STAGES[stage_num:] if is_canonical else []

    if not ok:
        return {
            "pipeline_stage_number": stage_num,
            "pipeline_total_stages": total,
            "pipeline_stages_remaining": remaining,
            "next_required_dispatch": agent,   # retry same stage
            "must_continue": True,
            "pipeline_complete": False,
            "instruction": (
                f"Stage {stage_num}/{total} FAILED for {agent}. "
                f"IMMEDIATELY call dispatchToAgent again with to='{agent}' with a REWORK prompt "
                f"identifying the specific gaps. Do NOT output text."
            ),
        }

    if next_stage is None:
        # quality-director approved — pipeline complete
        return {
            "pipeline_stage_number": stage_num,
            "pipeline_total_stages": total,
            "pipeline_stages_remaining": [],
            "next_required_dispatch": None,
            "must_continue": False,
            "pipeline_complete": True,
            "instruction": "ALL STAGES COMPLETE. quality-director approved. Now output the final summary to the user.",
        }

    return {
        "pipeline_stage_number": stage_num,
        "pipeline_total_stages": total,
        "pipeline_stages_remaining": remaining,
        "next_required_dispatch": next_stage,
        "must_continue": True,
        "pipeline_complete": False,
        "instruction": (
            f"Stage {stage_num}/{total} complete ({agent} → done). "
            f"IMMEDIATELY call dispatchToAgent with to='{next_stage}' — "
            f"NO text output, NO analysis, dispatch NOW."
        ),
    }


def _extract_and_persist_files(agent: str, output: str, issue: int) -> list[str]:
    """Parse markdown code blocks from agent output and write them to disk.

    Supports two patterns:
    1. Explicit path comment:  <!-- FILE: path/to/file.yaml -->  before a code block
    2. Stage-canonical path:   Known path for this pipeline stage (see _STAGE_OUTPUT_PATHS)
    """
    written: list[str] = []

    # Pattern 1 — explicit file path marker
    explicit_re = re.compile(
        r'<!--\s*FILE:\s*([^\s>]+)\s*-->\s*```[\w]*\n([\s\S]*?)```',
        re.MULTILINE,
    )
    for m in explicit_re.finditer(output):
        rel_path, content = m.group(1).strip(), m.group(2)
        _write_file(_REPO_ROOT / rel_path, content)
        written.append(rel_path)

    # Pattern 2 — stage-canonical path: write the largest code block
    if not written and agent in _STAGE_OUTPUT_PATHS:
        canon_path = _STAGE_OUTPUT_PATHS[agent]
        blocks = re.findall(r'```[\w\-]*\n([\s\S]*?)```', output)
        if blocks:
            # Pick the longest block (most likely the main artifact)
            content = max(blocks, key=len)
            _write_file(_REPO_ROOT / canon_path, content)
            written.append(canon_path)

    return written


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    try:
        rel = str(path.relative_to(_REPO_ROOT))
    except ValueError:
        rel = str(path)
    log_file_written(None, None, rel, len(content.encode("utf-8")))


def _build_docker_cmd(data: DispatchRequest, issue: int) -> list[str]:
    """Build the docker exec + run_dispatcher command.

    Each dispatch gets its own /tmp/dispatch-<uuid> profile to avoid
    Chromium SingletonLock conflicts between concurrent runs.
    """
    job_profile = f"/tmp/dispatch-{uuid.uuid4().hex}"
    token0 = _read_token(SESSION_TOKEN_PATH_0)
    token1 = _read_token(SESSION_TOKEN_PATH_1)

    py_args = [
        "python3", DISPATCHER_SCRIPT,
        "--to", data.to,
        "--prompt", data.prompt,
        "--issue", str(issue),
        # Always start a fresh conversation for every outbound dispatch so we
        # never pollute a previous task's conversation thread.
        "--force-new-conversation",
        "--user-data-dir", job_profile,
    ]
    if data.from_agent:
        py_args += ["--from", data.from_agent]
    if data.dry_run:
        py_args.append("--dry-run")
    if data.max_wait_seconds != DEFAULT_TIMEOUT:
        py_args += ["--max-wait-seconds", str(data.max_wait_seconds)]
    if token0:
        py_args += ["--session-token", token0]
    if token1:
        py_args += ["--session-token-1", token1]
    py_args.append("--headful")

    return [
        "docker", "exec",
        "-e", "DISPLAY=:99",
        "-e", "DEPLOY_HEADLESS=0",
        CONTAINER_NAME,
    ] + py_args


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/", dependencies=[Depends(verify_key)])
async def dispatch_to_agent(data: DispatchRequest, request: Request):
    start = time.time()

    if not data.to or not data.prompt:
        resp = {
            "ok": False,
            "error": {"code": "missing_fields", "message": "Both 'to' and 'prompt' are required."},
        }
        log_api_action(request, "/dispatch", "dispatch_to_agent", 400, str(resp))
        return resp

    # Auto-assign issue number if not provided
    issue = data.issue if data.issue is not None else _next_issue_number()

    _log_pipeline_event("api_dispatch_received", issue=issue, agent=data.to,
                        from_agent=data.from_agent, prompt_len=len(data.prompt),
                        dry_run=data.dry_run)

    cmd = _build_docker_cmd(data, issue)

    if data.dry_run:
        resp = {
            "ok": True,
            "dry_run": True,
            "issue": issue,
            "command": " ".join(cmd),
            "latency_ms": round((time.time() - start) * 1000, 2),
        }
        log_api_action(request, "/dispatch", "dispatch_to_agent", 200, str(resp))
        return resp

    try:
        # Use asyncio subprocess so the event loop stays free for concurrent requests
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            raw_out, raw_err = await asyncio.wait_for(
                proc.communicate(),
                timeout=data.max_wait_seconds + 30,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            _waited = data.max_wait_seconds + 30
            _log_pipeline_error(issue, data.to, "DispatchTimeout",
                                f"Dispatcher timed out after {_waited}s",
                                stage="asyncio_wait")
            resp = {
                "ok": False,
                "error": {"code": "timeout", "message": f"Dispatcher timed out after {data.max_wait_seconds}s"},
                "issue": issue,
                "dispatched_to": data.to,
                **_pipeline_meta(data.to, False, ""),
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
            log_api_action(request, "/dispatch", "dispatch_to_agent", 504, str(resp))
            return resp

        stdout = raw_out.decode("utf-8", errors="replace").strip()
        stderr = raw_err.decode("utf-8", errors="replace").strip()

        # run_dispatcher.py prints one JSON block on the last stdout line
        parsed: dict = {}
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    parsed = json.loads(line)
                    break
                except json.JSONDecodeError:
                    pass

        if not parsed:
            parsed = {
                "ok": proc.returncode == 0,
                "raw_stdout": stdout[-4000:] if len(stdout) > 4000 else stdout,
            }
        if stderr:
            parsed["stderr"] = stderr[-1000:] if len(stderr) > 1000 else stderr

        # --------------------------------------------------------------
        # Enrich the response with pipeline metadata so the CoS always
        # knows exactly which agent to dispatch to next.
        # --------------------------------------------------------------
        agent_ok = parsed.get("ok", proc.returncode == 0)
        raw_output = parsed.get("agent_output") or parsed.get("output") or ""

        # Persist files found in the agent output
        files_written: list[str] = []
        if agent_ok and raw_output:
            try:
                files_written = _extract_and_persist_files(data.to, raw_output, issue)
            except Exception as exc:
                parsed["file_write_warning"] = str(exc)

        latency = round((time.time() - start) * 1000, 2)
        parsed.update({
            "ok": agent_ok,
            "issue": issue,
            "dispatched_to": data.to,
            "latency_ms": latency,
            "files_written": files_written,
            # Full agent output — not truncated
            "agent_output": raw_output,
            **_pipeline_meta(data.to, agent_ok, raw_output),
        })

        status_code = 200 if agent_ok else 500
        _log_pipeline_event("api_dispatch_complete", issue=issue, agent=data.to,
                            ok=agent_ok, latency_ms=latency,
                            files_written=len(files_written),
                            output_len=len(raw_output))
        log_api_action(request, "/dispatch", "dispatch_to_agent", status_code, str(parsed)[:2000])
        return parsed

    except Exception as exc:
        _log_pipeline_error(issue, data.to, type(exc).__name__, str(exc),
                            stage="dispatch_to_agent")
        resp = {
            "ok": False,
            "error": {"code": "internal_error", "message": str(exc)},
            "issue": issue,
            "dispatched_to": data.to,
            **_pipeline_meta(data.to, False, ""),
            "latency_ms": round((time.time() - start) * 1000, 2),
        }
        log_api_action(request, "/dispatch", "dispatch_to_agent", 500, str(resp))
        return resp
