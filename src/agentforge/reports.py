"""Read benchmark results and produce a reproducible Markdown summary."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path


def load_results(path: Path) -> list[dict]:
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Benchmark results must be a JSONL file")
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at line {line_number}: {exc.msg}") from exc
        if not isinstance(record, dict):
            raise TypeError(f"Expected a JSON object at line {line_number}")
        info = record.get("benchmark")
        if not isinstance(info, dict):
            raise TypeError(f"Missing benchmark metadata at line {line_number}")
        if any(not isinstance(info.get(k), str) or not info[k].strip()
               for k in ("suite", "model", "task_id")):
            raise ValueError(f"Invalid benchmark identifiers at line {line_number}")
        if type(info.get("iteration")) is not int or info["iteration"] < 1:
            raise ValueError(f"Invalid iteration at line {line_number}")
        duration = info.get("duration_seconds")
        if type(duration) not in {int, float} or not 0 <= duration < float("inf"):
            raise ValueError(f"Invalid duration at line {line_number}")
        if type(record.get("improved")) is not bool:
            raise ValueError(f"Missing repair outcome at line {line_number}")
        if record.get("error") is not None and not isinstance(record["error"], str):
            raise TypeError(f"Invalid error field at line {line_number}")
        records.append(record)
    if not records:
        raise ValueError("Benchmark results file is empty")
    return records


def _cell(value: str) -> str:
    """Keep free-text model and task names inside a Markdown table cell."""
    return value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")


def _summary(records: list[dict]) -> dict:
    durations = [r["benchmark"]["duration_seconds"] for r in records]
    repaired = sum(r["improved"] for r in records)
    return {
        "attempts": len(records),
        "repairs": repaired,
        "rate": repaired / len(records),
        "errors": sum(r.get("error") is not None for r in records),
        "median": statistics.median(durations),
    }


def render_report(records: list[dict]) -> str:
    """Summarize each suite and model without combining unrelated benchmark suites."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["benchmark"]["suite"]].append(record)

    lines = [
        "# AgentForge benchmark results",
        "",
        "Repair rate is the share of attempts where the baseline failed and the candidate passed.",
        "Failed model calls count as unsuccessful attempts.",
        "",
    ]
    for suite in sorted(grouped):
        suite_records = grouped[suite]
        lines.extend([f"## {_cell(suite)}", ""])
        models: dict[str, list[dict]] = defaultdict(list)
        for record in suite_records:
            models[record["benchmark"]["model"]].append(record)
        lines.extend([
            "| Model | Attempts | Repairs | Repair rate | Errors | Median time (s) |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ])
        for model in sorted(models):
            stats = _summary(models[model])
            lines.append(
                f"| {_cell(model)} | {stats['attempts']} | {stats['repairs']} | "
                f"{stats['rate']:.1%} | {stats['errors']} | {stats['median']:.3f} |"
            )
        lines.extend([
            "",
            "### Results by task",
            "",
            "| Model | Task | Attempts | Repairs | Repair rate |",
            "| --- | --- | ---: | ---: | ---: |",
        ])
        by_task: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for record in suite_records:
            info = record["benchmark"]
            by_task[(info["model"], info["task_id"])].append(record)
        for (model, task), task_records in sorted(by_task.items()):
            stats = _summary(task_records)
            lines.append(
                f"| {_cell(model)} | {_cell(task)} | {stats['attempts']} | "
                f"{stats['repairs']} | {stats['rate']:.1%} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_report(results_file: Path, output: Path) -> dict:
    """Build a Markdown report from the JSONL file and return report metadata."""
    records = load_results(results_file)
    content = render_report(records)
    destination = output.expanduser().resolve()
    source = results_file.expanduser().resolve()
    if destination == source:
        raise ValueError("Report output must differ from the input JSONL file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return {
        "attempts": len(records),
        "suites": sorted({r["benchmark"]["suite"] for r in records}),
        "models": sorted({r["benchmark"]["model"] for r in records}),
        "output": str(destination),
    }
