from __future__ import annotations

import json
import re
from pathlib import Path

from utils.policy import PolicyError, ensure_under_allowed_root
from utils.safe_subprocess import run_checked


_ALLOWED_REF = re.compile(r"^[A-Za-z0-9._/@:-]+$")


def _safe_ref(value: str, field: str) -> str:
    value = (value or "").strip()
    if not value or len(value) > 200 or not _ALLOWED_REF.fullmatch(value):
        raise PolicyError("invalid_github_ref", f"Invalid {field}.")
    return value


def _json_or_text(result: dict) -> dict:
    text = result.get("stdout", "").strip()
    if text:
        try:
            return {"data": json.loads(text), "raw": text}
        except Exception:
            return {"raw": text}
    return {"raw": ""}


def issue_read(workspace_path: str, issue: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    issue_ref = _safe_ref(issue, "issue")
    result = run_checked([
        "gh", "issue", "view", issue_ref,
        "--json", "number,title,body,state,labels,assignees,comments,url",
    ], workspace, timeout=60)
    if result["exit_code"] != 0:
        raise PolicyError("github_issue_read_failed", result["stderr"] or result["stdout"])
    return {"ok": True, **_json_or_text(result), "stderr": result["stderr"]}


def pr_read(workspace_path: str, pr: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    pr_ref = _safe_ref(pr, "pull request")
    result = run_checked([
        "gh", "pr", "view", pr_ref,
        "--json", "number,title,body,state,headRefName,baseRefName,reviewDecision,comments,files,mergeable,url",
    ], workspace, timeout=60)
    if result["exit_code"] != 0:
        raise PolicyError("github_pr_read_failed", result["stderr"] or result["stdout"])
    return {"ok": True, **_json_or_text(result), "stderr": result["stderr"]}


def checks_read(workspace_path: str, ref: str | None = None) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    argv = ["gh", "pr", "checks", "--json", "name,state,link,bucket,startedAt,completedAt"]
    if ref:
        argv.insert(3, _safe_ref(ref, "pull request or branch"))
    result = run_checked(argv, workspace, timeout=120)
    if result["exit_code"] != 0:
        raise PolicyError("github_checks_read_failed", result["stderr"] or result["stdout"])
    return {"ok": True, **_json_or_text(result), "stderr": result["stderr"]}


def pr_comment(workspace_path: str, pr: str, body: str, dry_run: bool = True) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    pr_ref = _safe_ref(pr, "pull request")
    if not body or len(body) > 20000:
        raise PolicyError("invalid_comment_body", "Comment body is required and must be under 20,000 characters.")
    argv = ["gh", "pr", "comment", pr_ref, "--body", body]
    if dry_run:
        return {"dry_run": True, "argv": argv, "workspace_path": str(workspace)}
    result = run_checked(argv, workspace, timeout=60)
    if result["exit_code"] != 0:
        raise PolicyError("github_pr_comment_failed", result["stderr"] or result["stdout"])
    return {"ok": True, "stdout": result["stdout"], "stderr": result["stderr"]}


def _task_pr_body(task_record: dict) -> str:
    artifacts = task_record.get("artifacts", {})
    def art(name):
        return artifacts.get(name, {}).get("data")
    lines = [
        f"## Summary\n\nTask: {task_record.get('task', '')}",
        "## Tests\n",
        "```json\n" + json.dumps(art("test_result"), indent=2)[:4000] + "\n```",
        "## Quality\n",
        "```json\n" + json.dumps(art("quality_result"), indent=2)[:4000] + "\n```",
        "## Risk Report\n",
        "```json\n" + json.dumps(art("risk_report"), indent=2)[:4000] + "\n```",
        "## Diff Summary\n",
        "```json\n" + json.dumps(art("diff_summary"), indent=2)[:4000] + "\n```",
    ]
    return "\n\n".join(lines)


def pr_create_from_task(workspace_path: str, task_record: dict, title: str | None = None, dry_run: bool = True) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    pr_title = (title or task_record.get("task") or task_record.get("task_id") or "Coding task").strip()[:200]
    body = _task_pr_body(task_record)
    argv = ["gh", "pr", "create", "--title", pr_title, "--body", body]
    if dry_run:
        return {"dry_run": True, "argv": argv, "body_preview": body[:8000], "workspace_path": str(workspace)}
    result = run_checked(argv, workspace, timeout=120)
    if result["exit_code"] != 0:
        raise PolicyError("github_pr_create_failed", result["stderr"] or result["stdout"])
    return {"created": True, "url": result["stdout"].strip(), "stderr": result["stderr"]}


def checks_diagnose(checks: list[dict]) -> dict:
    failing = []
    pending = []
    for c in checks or []:
        state = str(c.get("state", "")).lower()
        bucket = str(c.get("bucket", "")).lower()
        if state in {"fail", "failed", "failure", "error"} or bucket in {"fail", "failed", "failure"}:
            failing.append(c)
        elif state not in {"pass", "passed", "success", "completed"} and bucket not in {"pass", "passed", "success"}:
            pending.append(c)
    return {"failing": failing, "pending": pending, "passed": not failing, "summary": f"{len(failing)} failing, {len(pending)} pending checks"}


def apply_feedback_plan(workspace_path: str, comments: list[dict]) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    files = []
    actions = []
    for c in comments or []:
        path = c.get("path") or c.get("file")
        body = c.get("body") or c.get("comment") or ""
        if path:
            files.append(path)
            actions.append({"file": path, "instruction": body[:1000], "suggested_next_step": "gather_context_then_patch"})
    return {"workspace_path": str(workspace), "files": list(dict.fromkeys(files)), "actions": actions}


def pr_update_body(workspace_path: str, pr: str, body: str, dry_run: bool = True) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    pr_ref = _safe_ref(pr, "pull request")
    if not body or len(body) > 50000:
        raise PolicyError("invalid_pr_body", "PR body is required and must be under 50,000 characters.")
    argv = ["gh", "pr", "edit", pr_ref, "--body", body]
    if dry_run:
        return {"dry_run": True, "argv": argv, "workspace_path": str(workspace), "body_preview": body[:4000]}
    result = run_checked(argv, workspace, timeout=120)
    if result["exit_code"] != 0:
        raise PolicyError("github_pr_update_failed", result["stderr"] or result["stdout"])
    return {"updated": True, "stdout": result["stdout"], "stderr": result["stderr"]}


def review_comments(workspace_path: str, pr: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    pr_ref = _safe_ref(pr, "pull request")
    result = run_checked(["gh", "api", f"repos/{'{owner}'}/{'{repo}'}/pulls/{pr_ref}/comments"], workspace, timeout=60)
    if result["exit_code"] != 0:
        # Fallback to gh pr view comments, because owner/repo expansion is unavailable without parsing remotes.
        fallback = run_checked(["gh", "pr", "view", pr_ref, "--json", "comments,reviews"], workspace, timeout=60)
        if fallback["exit_code"] != 0:
            raise PolicyError("github_review_comments_failed", fallback["stderr"] or fallback["stdout"] or result["stderr"])
        return {"ok": True, **_json_or_text(fallback), "stderr": fallback["stderr"]}
    return {"ok": True, **_json_or_text(result), "stderr": result["stderr"]}


def checks_logs(workspace_path: str, ref: str | None = None, dry_run: bool = True) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    argv = ["gh", "run", "list", "--limit", "10", "--json", "databaseId,displayTitle,conclusion,status,headBranch,headSha,workflowName,url"]
    if ref:
        argv.extend(["--branch", _safe_ref(ref, "branch")])
    if dry_run:
        return {"dry_run": True, "argv": argv, "workspace_path": str(workspace)}
    result = run_checked(argv, workspace, timeout=120)
    if result["exit_code"] != 0:
        raise PolicyError("github_checks_logs_failed", result["stderr"] or result["stdout"])
    return {"ok": True, **_json_or_text(result), "stderr": result["stderr"]}


def branch_push(workspace_path: str, remote: str = "origin", branch: str | None = None, dry_run: bool = True) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    if remote not in {"origin", "upstream"}:
        raise PolicyError("invalid_remote", "Only origin or upstream remotes are allowed.")
    if branch:
        branch = _safe_ref(branch, "branch")
    else:
        current = run_checked(["git", "branch", "--show-current"], workspace, timeout=10)
        branch = current["stdout"].strip()
    argv = ["git", "push", "-u", remote, branch]
    if dry_run:
        return {"dry_run": True, "argv": argv, "workspace_path": str(workspace)}
    result = run_checked(argv, workspace, timeout=180)
    if result["exit_code"] != 0:
        raise PolicyError("github_branch_push_failed", result["stderr"] or result["stdout"])
    return {"pushed": True, "stdout": result["stdout"], "stderr": result["stderr"]}


def ci_repair_plan(workspace_path: str, checks: list[dict] | None = None, logs: str | None = None) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    diag = checks_diagnose(checks or [])
    failing_names = [c.get("name") or c.get("workflowName") or c.get("displayTitle") for c in diag.get("failing", [])]
    context_terms = []
    if logs:
        for token in re.findall(r"(?:[A-Za-z0-9_./-]+\.(?:py|js|ts|tsx|go|rs|java))", logs)[:50]:
            context_terms.append(token)
    return {
        "workspace_path": str(workspace),
        "checks": diag,
        "log_file_hints": list(dict.fromkeys(context_terms))[:25],
        "required_gpt_behavior": [
            "Read failing CI check names and log_file_hints before patching.",
            "Gather focused context for referenced files only.",
            "Create a minimal unified diff repair patch.",
            "Submit the patch via /agent/coding-task/submit and rerun tests/quality where possible.",
        ],
        "repair_strategy": "Use CI failures as diagnostics; do not change unrelated files or weaken tests.",
        "failing_check_names": [x for x in failing_names if x],
    }


def feedback_to_patch_contract(workspace_path: str, comments: list[dict]) -> dict:
    plan = apply_feedback_plan(workspace_path, comments)
    return {
        **plan,
        "required_gpt_behavior": [
            "Read only files listed in actions before patching.",
            "Preserve reviewer intent exactly; do not add unrelated refactors.",
            "If a reviewer suggestion is ambiguous, produce a minimal clarification report instead of guessing.",
            "Submit changes as a recorded patch and rerun relevant checks.",
        ],
        "patch_contract": {
            "format": "unified_diff",
            "scope": "review_feedback_only",
            "allowed_files": plan.get("files", []),
        },
    }
