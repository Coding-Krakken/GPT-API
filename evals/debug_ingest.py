from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from utils import eval_telemetry

FAILURE_LAYERS = {
    "missing_api_key": "authentication",
    "invalid_api_key": "authentication",
    "action_requires_approval": "user_approval",
    "wrong_or_offline_domain": "public_tunnel",
    "ngrok_offline": "public_tunnel",
    "missing_payload_fields": "custom_gpt_behavior",
    "unsupported_category": "custom_gpt_behavior",
    "unsupported_action": "custom_gpt_behavior",
    "operation_limit": "schema",
    "instructions_too_long": "instructions",
    "schema_security_list": "schema",
    "client_response_error": "backend_route",
    "dependency_missing": "repo_environment",
}

RECOMMENDATIONS = {
    "missing_api_key": "Configure Custom GPT Action authentication as API Key with custom header x-api-key.",
    "invalid_api_key": "Verify the Action auth key matches CODING_GPT_API_KEY or OPERATOR_GPT_API_KEY/API_KEY on the server.",
    "action_requires_approval": "Approve the consequential action or split safe read-only operations to reduce approval prompts.",
    "wrong_or_offline_domain": "Re-import the latest core schema and verify servers.url points to the active ngrok domain.",
    "ngrok_offline": "Restart or repair the public tunnel before testing backend actions.",
    "missing_payload_fields": "Retry once with required fields inside payload, preferably using error.example_payload.",
    "unsupported_category": "Use only allowlisted dispatcher categories from the knowledge docs.",
    "unsupported_action": "Use only allowlisted actions for that dispatcher category.",
    "operation_limit": "Upload only coding-gpt-core-openapi.yaml, not the full schema.",
    "instructions_too_long": "Use the short coding-gpt-instructions.md and upload details as Knowledge files.",
    "schema_security_list": "Ensure ApiKeyAuth security entries are emitted as arrays: ApiKeyAuth: [].",
    "client_response_error": "Inspect the backend route response and telemetry for server/client failure details.",
    "dependency_missing": "Use env prepare_dry_run and ask for approval before installing dependencies.",
}


def _now_id(prefix: str = "debug_ingest") -> str:
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%10000:04d}"


def _json_objects_after_marker(text: str, marker: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    start = 0
    decoder = json.JSONDecoder()
    while True:
        idx = text.find(marker, start)
        if idx == -1:
            break
        brace = text.find("{", idx)
        if brace == -1:
            break
        try:
            obj, end = decoder.raw_decode(text[brace:])
            if isinstance(obj, dict):
                objects.append(obj)
            start = brace + end
        except json.JSONDecodeError:
            start = brace + 1
    return objects


def extract_debug_calls(log_text: str) -> list[dict[str, Any]]:
    call_objs = _json_objects_after_marker(log_text, "[debug] Calling HTTP endpoint")
    responses = _json_objects_after_marker(log_text, "[debug] Response received")
    failed = _json_objects_after_marker(log_text, "[debug] Failed Outbound Call")
    calls: list[dict[str, Any]] = []
    max_len = max(len(call_objs), len(responses), len(failed))
    for i in range(max_len):
        call = call_objs[i] if i < len(call_objs) else {}
        response = responses[i] if i < len(responses) else {}
        fail = failed[i] if i < len(failed) else {}
        combined = {
            "index": i,
            "domain": call.get("domain") or response.get("domain") or fail.get("domain"),
            "method": call.get("method") or fail.get("method"),
            "path": call.get("path") or fail.get("path"),
            "operation": call.get("operation") or fail.get("operation"),
            "operation_hash": call.get("operation_hash") or fail.get("operation_hash"),
            "is_consequential": call.get("is_consequential"),
            "params": call.get("params") or fail.get("params") or {},
            "response": response,
            "failed_outbound": fail,
        }
        combined["http_status"] = response.get("status_code") or response.get("http_status") or fail.get("http_status")
        data = response.get("response_data") if isinstance(response, dict) else None
        detail = response.get("detail") if isinstance(response, dict) else None
        combined["response_data"] = data
        combined["detail"] = detail
        combined["error_code"] = _detect_error_code(combined, log_text)
        combined["failure_layer"] = FAILURE_LAYERS.get(combined["error_code"], "unknown") if combined["error_code"] else None
        calls.append(combined)
    return calls


def _detect_error_code(call: dict[str, Any], full_text: str | None = None) -> str | None:
    status = call.get("http_status")
    response = call.get("response") or {}
    data = call.get("response_data")
    detail = call.get("detail")
    fail = call.get("failed_outbound") or {}
    text_parts = [json.dumps(x, default=str) for x in (response, data, detail, fail, call.get("params")) if x is not None]
    text = "\n".join(text_parts)
    lower = text.lower()
    if status == 403 or "no api key" in lower or "invalid key" in lower:
        return "missing_api_key"
    if "requires approval" in lower:
        return "action_requires_approval"
    if "err_ngrok_3200" in lower or "endpoint" in lower and "offline" in lower:
        return "ngrok_offline"
    if "gpt-api.ngrok.app" in lower and "unscrutinized-immotile-jermaine" not in lower:
        return "wrong_or_offline_domain"
    if isinstance(data, dict):
        err = data.get("error") or {}
        if isinstance(err, dict) and err.get("code"):
            return str(err.get("code"))
        if data.get("status") == 400 and isinstance(err, dict) and "missing required payload" in str(err.get("message", "")).lower():
            return "missing_payload_fields"
    if "missing_payload_fields" in lower or "missing required payload fields" in lower:
        return "missing_payload_fields"
    if "maximum of 30 operations" in lower or "maximum allowed operations" in lower:
        return "operation_limit"
    if "8000" in lower and "instructions" in lower:
        return "instructions_too_long"
    if "apikeyauth" in lower and "valid list" in lower:
        return "schema_security_list"
    if "clientresponseerror" in lower:
        return "client_response_error"
    if "eslint: command not found" in lower or "command not found" in lower or "exit_code\": 127" in lower:
        return "dependency_missing"
    if full_text:
        ft = full_text.lower()
        if "maximum of 30 operations" in ft:
            return "operation_limit"
        if "input should be a valid list" in ft and "apikeyauth" in ft:
            return "schema_security_list"
    return None


def classify_debug_log(log_text: str) -> dict[str, Any]:
    calls = extract_debug_calls(log_text)
    codes = Counter(c.get("error_code") for c in calls if c.get("error_code"))
    layers = Counter(c.get("failure_layer") for c in calls if c.get("failure_layer"))
    warnings: list[dict[str, Any]] = []
    for code, count in codes.items():
        warnings.append({
            "code": code,
            "count": count,
            "failure_layer": FAILURE_LAYERS.get(code, "unknown"),
            "recommendation": RECOMMENDATIONS.get(code, "Inspect the parsed call and backend telemetry."),
        })
    successful = sum(1 for c in calls if c.get("http_status") and 200 <= int(c.get("http_status")) < 300 and not c.get("error_code"))
    failed = sum(1 for c in calls if c.get("error_code") or (c.get("http_status") and int(c.get("http_status")) >= 400))
    score = max(0, min(100, 100 - failed * 20 - codes.get("missing_api_key", 0) * 10 - codes.get("missing_payload_fields", 0) * 10))
    return {
        "call_count": len(calls),
        "successful_calls": successful,
        "failed_calls": failed,
        "agent_behavior_score": score,
        "failure_codes": dict(codes),
        "failure_layers": dict(layers),
        "warnings": sorted(warnings, key=lambda x: (-x["count"], x["code"])),
        "calls": calls,
    }


def debug_log_to_events(log_text: str, *, run_id: str | None = None, source: str = "custom_gpt_debug") -> list[dict[str, Any]]:
    run_id = run_id or _now_id("debug")
    parsed = classify_debug_log(log_text)
    events: list[dict[str, Any]] = []
    base = {"run_id": run_id, "source": source}
    events.append({**base, "event_type": "custom_gpt_debug_ingested", "timestamp": int(time.time() * 1000), "call_count": parsed["call_count"], "agent_behavior_score": parsed["agent_behavior_score"]})
    for call in parsed["calls"]:
        endpoint = call.get("path")
        params = call.get("params") or {}
        payload = params.get("payload") if isinstance(params, dict) else None
        payload_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
        events.append({
            **base,
            "event_type": "custom_gpt_action_call",
            "timestamp": int(time.time() * 1000),
            "endpoint": endpoint,
            "domain": call.get("domain"),
            "method": call.get("method"),
            "operation": call.get("operation"),
            "is_consequential": call.get("is_consequential"),
            "param_keys": sorted(params.keys()) if isinstance(params, dict) else [],
            "payload_keys": payload_keys,
            "status": call.get("http_status"),
            "error_code": call.get("error_code"),
            "failure_layer": call.get("failure_layer"),
        })
        if call.get("error_code"):
            events.append({
                **base,
                "event_type": "custom_gpt_failure_classified",
                "timestamp": int(time.time() * 1000),
                "endpoint": endpoint,
                "error_code": call.get("error_code"),
                "failure_layer": call.get("failure_layer"),
                "recommendation": RECOMMENDATIONS.get(call.get("error_code"), "Inspect parsed debug call."),
            })
    return events


def write_ingest_report(parsed: dict[str, Any], *, run_id: str | None = None) -> dict[str, str]:
    run_id = run_id or _now_id("debug_ingest")
    root = eval_telemetry.eval_root() / "debug_ingests"
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{run_id}.json"
    md_path = root / f"{run_id}.md"
    json_path.write_text(json.dumps(parsed, indent=2, sort_keys=True), encoding="utf-8")
    lines = [f"# Custom GPT Debug Ingest: {run_id}", "", "## Summary", ""]
    lines.append(f"- Calls parsed: {parsed.get('call_count')}")
    lines.append(f"- Successful calls: {parsed.get('successful_calls')}")
    lines.append(f"- Failed calls: {parsed.get('failed_calls')}")
    lines.append(f"- Agent behavior score: {parsed.get('agent_behavior_score')}")
    lines.append("")
    lines.append("## Failure layers")
    for layer, count in (parsed.get("failure_layers") or {}).items():
        lines.append(f"- {layer}: {count}")
    lines.append("")
    lines.append("## Warnings and recommendations")
    for w in parsed.get("warnings") or []:
        lines.append(f"- `{w['code']}` ({w['failure_layer']}, count {w['count']}): {w['recommendation']}")
    lines.append("")
    lines.append("## Calls")
    for c in parsed.get("calls") or []:
        lines.append(f"- #{c.get('index')} {c.get('method')} {c.get('domain')}{c.get('path')} status={c.get('http_status')} error={c.get('error_code')} layer={c.get('failure_layer')}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def regression_from_debug(parsed: dict[str, Any], *, title: str | None = None, source: str = "custom_gpt_debug") -> dict[str, Any]:
    warnings = parsed.get("warnings") or []
    primary = warnings[0] if warnings else {"code": "unknown_debug_failure", "failure_layer": "unknown", "recommendation": "Inspect debug transcript."}
    return {
        "id": f"debug_{primary['code']}_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%10000:04d}",
        "title": title or f"Custom GPT debug regression: {primary['code']}",
        "source": source,
        "failure_layer": primary.get("failure_layer", "unknown"),
        "symptom": f"Parsed Custom GPT debug log produced {primary.get('code')} ({primary.get('count', 1)} occurrence(s)).",
        "expected_behavior": primary.get("recommendation", "The agent should avoid or recover from this failure."),
        "details": {
            "failure_codes": parsed.get("failure_codes"),
            "failure_layers": parsed.get("failure_layers"),
            "call_count": parsed.get("call_count"),
            "calls": [
                {
                    "domain": c.get("domain"),
                    "path": c.get("path"),
                    "method": c.get("method"),
                    "http_status": c.get("http_status"),
                    "error_code": c.get("error_code"),
                    "failure_layer": c.get("failure_layer"),
                    "param_keys": sorted((c.get("params") or {}).keys()) if isinstance(c.get("params"), dict) else [],
                }
                for c in parsed.get("calls", [])
            ],
        },
    }
