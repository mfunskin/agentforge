"""Command line entry point."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentforge.benchmark import run_task
from agentforge.benchmark_audit import audit_results
from agentforge.comparison import compare_proposal, evaluate_agent
from agentforge.diagnostics import generate_diagnostics
from agentforge.evaluation import evaluate
from agentforge.inspector import inspect_repo
from agentforge.model_agent import ModelCodingAgent, OllamaClient
from agentforge.reports import generate_report
from agentforge.run_comparison import compare_results
from agentforge.runner import ALLOWED_CHECKS, run_check
from agentforge.suite import load_suite, run_suite
from agentforge.tasks import load_task


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
    task = sub.add_parser("task", help="Validate or run a coding task")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    validate = task_sub.add_parser("validate", help="Validate a JSON task")
    validate.add_argument("file", type=Path)
    execute = task_sub.add_parser("run", help="Execute an allowlisted task check")
    execute.add_argument("file", type=Path)
    execute.add_argument("--output", type=Path)
    compare = task_sub.add_parser("compare", help="Compare a code proposal with the baseline")
    compare.add_argument("file", type=Path)
    compare.add_argument("--proposal", type=Path, required=True)
    compare.add_argument("--output", type=Path)
    solve = task_sub.add_parser("solve", help="Generate and evaluate an Ollama code proposal")
    solve.add_argument("file", type=Path)
    solve.add_argument("--model", required=True)
    solve.add_argument("--file", action="append", required=True, dest="source_files")
    solve.add_argument("--context", choices=["source", "tests"], default="source")
    solve.add_argument("--model-timeout", type=int, default=120)
    solve.add_argument("--output", type=Path)
    benchmark = sub.add_parser("benchmark", help="Validate and run benchmark suites")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    suite_validate = benchmark_sub.add_parser("validate", help="Validate a benchmark suite")
    suite_validate.add_argument("file", type=Path)
    suite_run = benchmark_sub.add_parser("run", help="Evaluate models on a suite")
    suite_run.add_argument("file", type=Path)
    suite_run.add_argument("--model", action="append", required=True, dest="models")
    suite_run.add_argument("--repeats", type=int, default=3)
    suite_run.add_argument("--model-timeout", type=int, default=120)
    suite_run.add_argument("--strategy", choices=["single", "feedback"], default="single")
    suite_run.add_argument("--context", choices=["source", "tests"], default="source")
    suite_run.add_argument("--max-attempts", type=int, default=2)
    suite_run.add_argument("--output", type=Path, default=Path("runs/benchmarks.jsonl"))
    audit = benchmark_sub.add_parser(
        "audit", help="Audit duplicate patches and recorded benchmark conditions"
    )
    audit.add_argument("file", type=Path)
    audit.add_argument("--output", type=Path, required=True)
    report = benchmark_sub.add_parser("report", help="Summarize saved benchmark results")
    report.add_argument("file", type=Path)
    report.add_argument("--output", type=Path, required=True)
    diagnose = benchmark_sub.add_parser("diagnose", help="Inspect unsuccessful benchmark attempts")
    diagnose.add_argument("file", type=Path)
    diagnose.add_argument("--output", type=Path, required=True)
    diagnose.add_argument("--limit", type=int, default=30)
    compare_runs = benchmark_sub.add_parser(
        "compare", help="Compare saved benchmark runs and evaluation conditions"
    )
    compare_runs.add_argument("files", type=Path, nargs="+")
    compare_runs.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_repo(args.repo)
        elif args.command == "check":
            result = run_check(args.repo, args.name, args.timeout)
        elif args.command == "evaluate":
            result = evaluate(args.repo, args.name, args.output, args.timeout)
        elif args.command == "benchmark" and args.benchmark_command == "validate":
            result = load_suite(args.file).as_dict()
        elif args.command == "benchmark" and args.benchmark_command == "compare":
            result = compare_results(args.files, args.output)
        elif args.command == "benchmark" and args.benchmark_command == "audit":
            result = audit_results(args.file, args.output)
        elif args.command == "benchmark" and args.benchmark_command == "diagnose":
            result = generate_diagnostics(args.file, args.output, limit=args.limit)
        elif args.command == "benchmark" and args.benchmark_command == "report":
            result = generate_report(args.file, args.output)
        elif args.command == "benchmark":
            result = run_suite(
                args.file, args.models, repeats=args.repeats, output=args.output,
                model_timeout=args.model_timeout,
                strategy=args.strategy, max_attempts=args.max_attempts,
                context=args.context,
            )
        elif args.command == "task" and args.task_command == "solve":
            agent = ModelCodingAgent(
                OllamaClient(args.model, timeout=args.model_timeout),
                args.source_files, context=args.context,
            )
            result = evaluate_agent(args.file, agent, args.output)
        elif args.command == "task" and args.task_command == "compare":
            result = compare_proposal(args.file, args.proposal, args.output)
        elif args.task_command == "validate":
            result = load_task(args.file).as_dict()
        else:
            result = run_task(args.file, args.output)
        print(json.dumps(result, indent=2))
        return 0 if result.get("result", result).get("passed", True) else 1
    except (OSError, TypeError, ValueError) as error:
        print(f"agentforge: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
