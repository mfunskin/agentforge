"""Summarize public-check and verification gaps from saved benchmark results."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from agentforge.attempt_tracking import public_failure_kind
from agentforge.diagnostics import classify_result
from agentforge.reports import load_results

FAILED_TEST = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)


def _cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")


def failed_test_ids(check: dict | None) -> list[str]:
    """Extract pytest short-summary identifiers without analyzing their meaning."""
    if not isinstance(check, dict):
        return []
    output = "\n".join(
        value for name in ("stdout", "stderr")
        if isinstance((value := check.get(name)), str)
    )
    return sorted(set(FAILED_TEST.findall(output)))


def summarize_gaps(records: list[dict]) -> list[dict]:
    """Keep benchmarks and models separate; summarize recorded final checks."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        info = record["benchmark"]
        groups[(info["suite"], info["model"])].append(record)

    reports = []
    for (suite, model), items in sorted(groups.items()):
        outcomes = Counter(classify_result(record) for record in items)
        tasks: dict[str, list[dict]] = defaultdict(list)
        for record in items:
            tasks[record["benchmark"]["task_id"]].append(record)

        task_rows = []
        for task, attempts in sorted(tasks.items()):
            task_outcomes = Counter(classify_result(record) for record in attempts)
            public_failures = Counter()
            verification_failures = Counter()
            for record in attempts:
                kind = classify_result(record)
                if kind == "candidate_check_failed" or kind == "check_timeout":
                    check = record.get("candidate")
                    if isinstance(check, dict):
                        public_failures[public_failure_kind(check)] += 1
                if kind == "verification_failed":
                    verification_failures.update(failed_test_ids(record.get("verification")))
            task_rows.append({
                "task_id": task,
                "trials": len(attempts),
                "public_passed": sum(
                    isinstance(record.get("candidate"), dict)
                    and record["candidate"].get("passed") is True
                    for record in attempts
                ),
                "verified": sum(record["improved"] for record in attempts),
                "outcomes": dict(sorted(task_outcomes.items())),
                "public_failures": dict(sorted(public_failures.items())),
                "verification_failures": dict(sorted(verification_failures.items())),
            })

        reports.append({
            "suite": suite,
            "model": model,
            "trials": len(items),
            "public_passed": sum(row["public_passed"] for row in task_rows),
            "verified": sum(row["verified"] for row in task_rows),
            "verification_failed": outcomes["verification_failed"],
            "outcomes": dict(sorted(outcomes.items())),
            "tasks": task_rows,
        })
    return reports


def render_gaps(reports: list[dict]) -> str:
    """Render diagnostic observations without reclassifying model capability."""
    lines = [
        "# AgentForge verification gap report",
        "",
        "This report summarizes saved final checks. No model is called and no",
        "verification output is supplied to a model during evaluation.",
        "Failed test identifiers come from recorded pytest short summaries.",
        "They identify unsuccessful checks, not independently established root causes.",
        "",
    ]
    for report in reports:
        title = f"{report['suite']} / {report['model']}"
        lines.extend([
            f"## {_cell(title)}",
            "",
            "| Measurement | Count |",
            "| --- | ---: |",
            f"| Trials | {report['trials']} |",
            f"| Public checks passed | {report['public_passed']} |",
            f"| Verified repairs | {report['verified']} |",
            f"| Public passed, verification failed | {report['verification_failed']} |",
            "",
            "### Outcomes by task",
            "",
            "| Task | Trials | Public passed | Verified | Verification failures |",
            "| --- | ---: | ---: | ---: | ---: |",
        ])
        for row in report["tasks"]:
            count = row["outcomes"].get("verification_failed", 0)
            lines.append(
                f"| {_cell(row['task_id'])} | {row['trials']} | "
                f"{row['public_passed']} | {row['verified']} | {count} |"
            )
        lines.extend(["", "### Failed public checks", ""])
        present = False
        for row in report["tasks"]:
            for kind, count in row["public_failures"].items():
                present = True
                lines.append(f"- {_cell(row['task_id'])}: {_cell(kind)} ({count})")
        if not present:
            lines.append("No recorded final public-check failures.")
        lines.extend(["", "### Verification failures", ""])
        present = False
        for row in report["tasks"]:
            if not row["outcomes"].get("verification_failed"):
                continue
            present = True
            lines.append(f"**{_cell(row['task_id'])}**")
            if not row["verification_failures"]:
                lines.append("No named failing test was found in the recorded output.")
            for test_id, count in row["verification_failures"].items():
                lines.append(f"- `{_cell(test_id)}` ({count})")
            lines.append("")
        if not present:
            lines.append("No public-pass verification failures were recorded.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_gap_report(results_file: Path, output: Path) -> dict:
    """Produce a report without altering input JSONL or running any check."""
    source = results_file.expanduser().resolve(strict=True)
    destination = output.expanduser().resolve()
    if source == destination:
        raise ValueError("Gap report output must differ from the input JSONL file")
    reports = summarize_gaps(load_results(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_gaps(reports), encoding="utf-8")
    return {
        "conditions": len(reports),
        "trials": sum(row["trials"] for row in reports),
        "public_passed": sum(row["public_passed"] for row in reports),
        "verified": sum(row["verified"] for row in reports),
        "verification_failed": sum(row["verification_failed"] for row in reports),
        "output": str(destination),
    }
