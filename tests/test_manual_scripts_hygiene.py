from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANUAL_DIR = ROOT / "scripts" / "manual"


def test_manual_scripts_live_outside_repo_root():
    assert not list(ROOT.glob("manual_*.py"))
    scripts = sorted(MANUAL_DIR.glob("manual_*.py"))
    assert scripts, "expected manual smoke scripts under scripts/manual"


def test_manual_scripts_are_import_safe_and_guarded():
    for script in sorted(MANUAL_DIR.glob("manual_*.py")):
        text = script.read_text(encoding="utf-8")
        assert "if __name__" in text, script
        assert "REPO_ROOT" in text, script
        spec = importlib.util.spec_from_file_location(f"manual_hygiene_{script.stem}", script)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert callable(getattr(module, "main", None)), script


def test_manual_scripts_readme_documents_execution_contract():
    readme = MANUAL_DIR / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "outside the repository root" in text
    assert "if __name__" in text
    assert "python scripts/manual/manual_endpoint_sandbox.py" in text
