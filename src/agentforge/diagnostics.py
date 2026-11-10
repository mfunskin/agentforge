"""Failure diagnostics for recorded coding benchmarks."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from agentforge.reports import load_results


def classify_result(record: dict) -> str:
    """Describe the observed outcome without inferring an unrecorded cause."""
    if record["improved"]:
        return "repaired"
    if record.get("error") is not None:
        return "recorded_error"
    candidate = record.get("candidate")
    if not isinstance(candidate, dict):
        return "missing_candidate"
    if candidate.get("timed_out"):
        return "check_timeout"
    baseline = record.get("baseline")
    if isinstance(baseline, dict) and baseline.get("passed") is True:
        return "baseline_passed"
    if candidate.get("passed") is True:
        return "passed_without_repair"
    return "candidate_check_failed"


def _clean(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")


def _details(record: dict) -> str:
    error = record.get("error")
    if isinstance(error, str) and error:
        return error[-1600:]
    candidate = record.get("candidate")
    if not isinstance(candidate, dict):
        return "No candidate result was recorded."
    parts = []
    for field in ("stdout", "stderr"):
        message = candidate.get(field)
        if isinstance(message, str) and message.strip():
            parts.append(f"{field}:\n{message.strip()}")
    if parts:
        return "\n\n".join(parts)[-1600:]
    return f"Candidate check exit code: {candidate.get('exit_code')}"


def render_diagnostics(records: list[dict], limit: int = 30) -> str:
    """Create a failure report grouped by model, task and outcome."""
    if not 1 <= limit <= 500:
        raise ValueError("Detail limit must be between 1 and 500")
    failures = [record for record in records if not record["improved"]]
    counts = Counter(classify_result(record) for record in records)
    by_case: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for record in failures:
        info = record["benchmark"]
        key = (info["suite"], info["model"], info["task_id"], classify_result(record))
        by_case[key] += 1

    lines = [
        "# AgentForge failure diagnostics",
        "",
        f"Attempts: {len(records)}",
        f"Repairs: {counts['repaired']}",
        f"Unsuccessful attempts: {len(failures)}",
        "",
        "## Outcome counts",
        "",
        "| Outcome | Attempts |",
        "| --- | ---: |",
    ]
    for outcome, count in sorted(counts.items()):
        lines.append(f"| {outcome} | {count} |")
    lines.extend([
        "",
        "## Unsuccessful attempts by case",
        "",
        "| Suite | Model | Task | Outcome | Attempts |",
        "| --- | --- | --- | --- | ---: |",
    ])
    for (suite, model, task, outcome), count in sorted(by_case.items()):
        lines.append(
            f"| {_clean(suite)} | {_clean(model)} | {_clean(task)} | "
            f"{outcome} | {count} |"
        )
    if not by_case:
        lines.append("| None | | | | 0 |")
    lines.extend(["", "## Failure details", ""])
    if not failures:
        lines.append("No unsuccessful attempts were recorded.")
    for number, record in enumerate(failures[:limit], 1):
        info = record["benchmark"]
        title = f"{info['model']} / {info['task_id']} / trial {info['iteration']}"
        lines.extend([
            f"### {number}. {_clean(title)}",
            "",
            f"Outcome: {classify_result(record)}",
            "",
            "~~~text",
            _details(record),
            "~~~",
            "",
        ])
    if len(failures) > limit:
        lines.append(f"{len(failures) - limit} additional failures omitted.")
    return "\n".join(lines).rstrip() + "\n"


def generate_diagnostics(results_file: Path, output: Path, limit: int = 30) -> dict:
    """Write a report without overwriting the recorded JSONL input."""
    records = load_results(results_file)
    content = render_diagnostics(records, limit=limit)
    destination = output.expanduser().resolve()
    if destination == results_file.expanduser().resolve():
        raise ValueError("Diagnostic report output must differ from the input JSONL file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    failures = [record for record in records if not record["improved"]]
    return {
        "attempts": len(records),
        "repaired": len(records) - len(failures),
        "unsuccessful": len(failures),
        "outcomes": dict(sorted(Counter(classify_result(r) for r in records).items())),
        "output": str(destination),
    }
