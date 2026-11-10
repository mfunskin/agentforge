"""Command line entry point."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentforge.evaluation import evaluate
from agentforge.inspector import inspect_repo
from agentforge.runner import ALLOWED_CHECKS, run_check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentforge", description="Local-first repository evaluator"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Inventory repository files and languages")
    inspect.add_argument("repo", type=Path)
    check = sub.add_parser("check", help="Run an allowlisted local check")
    check.add_argument("repo", type=Path)
    check.add_argument("--name", choices=ALLOWED_CHECKS, default="pytest")
    check.add_argument("--timeout", type=int, default=30)
    ev = sub.add_parser("evaluate", help="Run a check and save structured JSONL")
    ev.add_argument("repo", type=Path)
    ev.add_argument("--name", choices=ALLOWED_CHECKS, default="pytest")
    ev.add_argument("--timeout", type=int, default=30)
    ev.add_argument("--output", type=Path, default=Path("runs/evaluations.jsonl"))
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_repo(args.repo)
        elif args.command == "check":
            result = run_check(args.repo, args.name, args.timeout)
        else:
            result = evaluate(args.repo, args.name, args.output, args.timeout)
        print(json.dumps(result, indent=2))
        return 0 if result.get("result", result).get("passed", True) else 1
    except (OSError, ValueError) as error:
        print(f"agentforge: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
