from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals import regression_loader

DEFAULT_REPO = "/home/obsidian/Elevate_test"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Coding GPT permanent regression suite")
    parser.add_argument("--repo-path", default=DEFAULT_REPO)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--id", default=None, help="Run one regression id")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    if args.list:
        print(json.dumps({"regressions": regression_loader.list_regressions()}, indent=2))
        return 0
    if args.id:
        matches = [r for r in regression_loader.list_regressions() if r.get("id") == args.id]
        if not matches:
            print(json.dumps({"status": 404, "error": f"Regression not found: {args.id}"}, indent=2))
            return 1
        reg = regression_loader.load_regression(REPO_ROOT / matches[0]["source_file"])
        result = regression_loader.run_regression(reg, repo_path=args.repo_path, run_id=args.run_id)
    else:
        result = regression_loader.run_all(repo_path=args.repo_path, run_id=args.run_id)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == 200 and result.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
