from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_metrics_endpoint_records_requests(client, auth_headers):
    client.get("/health")
    response = client.get("/metrics", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["total_requests"] >= 1
    assert "latency_ms" in payload
    assert "status_counts" in payload
    assert "top_slowest" in payload


def test_diagnostics_performance_exposes_metrics(client, auth_headers):
    response = client.get("/diagnostics/performance", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "active_requests" in payload
    assert "redirect_count" in payload
    assert "validation_failures" in payload


def test_diagnostics_ngrok_has_stable_shape(client, auth_headers):
    response = client.get("/diagnostics/ngrok", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "unavailable"}
    assert isinstance(payload["admin_alive"], bool)
    assert isinstance(payload["public_urls"], list)
    assert "latency_ms" in payload


def test_openapi_validator_script_passes_basic_checks():
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/validate_openapi.py"],
        cwd=repo,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "openapi validation passed" in result.stdout


def test_run_script_forces_ngrok_stdout_logging():
    repo = Path(__file__).resolve().parents[1]
    script = (repo / "run_gpt_service.sh").read_text(encoding="utf-8")
    assert "ngrok start --all --log=stdout" in script
    assert ">> logs/ngrok.log 2>&1" in script
