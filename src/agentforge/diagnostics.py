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
        verification = record.get("verification")
        if isinstance(verification, dict) and not verification.get("passed"):
            return "verification_failed"
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
    verification = record.get("verification")
    if candidate.get("passed") and isinstance(verification, dict) and not verification.get("passed"):
        candidate = verification
    parts = []
    for field in ("stdout", "stderr"):
        message = candidate.get(field)
        if isinstance(message, str) and message.strip():
            parts.append(f"{field}:\n{message.strip()}")
    if parts:
        return "\n\n".join(parts)[-1600:]
    return f"Candidate check exit code: {candidate.get('exit_code')}"


def _feedback_events(record: dict) -> list[dict]:
    """Return saved model attempts without counting the baseline check."""
    trajectory = record.get("trajectory")
    if not isinstance(trajectory, list):
        return []
    return [
        event for event in trajectory
        if isinstance(event, dict)
        and type(event.get("attempt")) is int
        and event["attempt"] > 0
        and event.get("action") in {"proposal_rejected", "candidate_check"}
    ]


def _feedback_counts(records: list[dict]) -> Counter:
    counts: Counter[str] = Counter()
    for record in records:
        events = _feedback_events(record)
        if events:
            counts["model_calls"] += len(events)
            if len(events) > 1:
                counts["retried_trials"] += 1
        for event in events:
            if event["action"] == "proposal_rejected":
                counts["rejected_proposals"] += 1
            elif event.get("passed"):
                counts["passing_checks"] += 1
            else:
                counts["failed_checks"] += 1
    return counts


def _feedback_detail(event: dict) -> tuple[str, str]:
    if event["action"] == "proposal_rejected":
        error = event.get("error")
        return "Proposal rejected", error[-1600:] if isinstance(error, str) else "Rejected"
    result = event.get("result")
    status = "Check passed" if event.get("passed") else "Check failed"
    if isinstance(result, dict):
        return status, _details({"error": None, "candidate": result})
    return status, "No check output was recorded."


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
    feedback_counts = _feedback_counts(records)
    if feedback_counts["model_calls"]:
        lines.extend([
            "",
            "## Feedback attempt outcomes",
            "",
            "| Measurement | Count |",
            "| --- | ---: |",
        ])
        for label, key in (
            ("Model calls", "model_calls"),
            ("Trials with retries", "retried_trials"),
            ("Rejected proposals", "rejected_proposals"),
            ("Failed candidate checks", "failed_checks"),
            ("Passing candidate checks", "passing_checks"),
        ):
            lines.append(f"| {label} | {feedback_counts[key]} |")
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
        ])
        events = _feedback_events(record)
        if events:
            for event in events:
                status, detail = _feedback_detail(event)
                lines.extend([
                    f"#### Attempt {event['attempt']}: {status}",
                    "",
                    "~~~text",
                    detail,
                    "~~~",
                    "",
                ])
        else:
            lines.extend(["~~~text", _details(record), "~~~", ""])
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
        "feedback_attempts": dict(sorted(_feedback_counts(records).items())),
        "output": str(destination),
    }
