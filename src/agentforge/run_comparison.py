"""Compare saved benchmark experiments without combining their results."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path

from agentforge.reports import load_results


@dataclass(frozen=True)
class Run:
    label: str
    suite: str
    model: str
    strategy: str
    context: str
    max_attempts: int
    records: list[dict]

    def trials(self) -> set[tuple[str, int]]:
        return {
            (item["benchmark"]["task_id"], item["benchmark"]["iteration"])
            for item in self.records
        }


def _safe_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")


def _read_run(path: Path) -> Run:
    records = load_results(path)
    conditions = set()
    attempts = set()
    for record in records:
        info = record["benchmark"]
        strategy = info.get("strategy", "single")
        context = info.get("context", "source")
        max_attempts = record.get("max_attempts", 1)
        if strategy not in {"single", "feedback"} or context not in {"source", "tests"}:
            raise ValueError(f"Unknown strategy or context in {path.name}")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
            raise ValueError(f"Invalid attempt limit in {path.name}")
        conditions.add((info["suite"], info["model"], strategy, context, max_attempts))
        trial = (info["task_id"], info["iteration"])
        if trial in attempts:
            raise ValueError(f"Duplicate task and iteration in {path.name}: {trial}")
        attempts.add(trial)
    if len(conditions) != 1:
        raise ValueError(f"Expected one benchmark condition per file: {path.name}")
    suite, model, strategy, context, limit = conditions.pop()
    return Run(path.stem, suite, model, strategy, context, limit, records)


def _stats(records: list[dict]) -> dict:
    attempts = len(records)
    repaired = sum(record["improved"] for record in records)
    model_calls = sum(record.get("attempts_used", 1) for record in records)
    if any(type(record.get("attempts_used", 1)) is not int
           or record.get("attempts_used", 1) < 1 for record in records):
        raise ValueError("Invalid recorded model-call count")
    return {
        "attempts": attempts,
        "repaired": repaired,
        "repair_rate": repaired / attempts,
        "errors": sum(record.get("error") is not None for record in records),
        "model_calls": model_calls,
        "median_seconds": statistics.median(
            record["benchmark"]["duration_seconds"] for record in records
        ),
    }


def _case_fingerprints(run: Run) -> tuple[int, dict]:
    """Keep v2 comparisons tied to identical task and verifier contents."""
    fingerprints = {}
    versions = set()
    for record in run.records:
        info = record["benchmark"]
        version = info.get("suite_version", 1)
        if version not in {1, 2}:
            raise ValueError("Unknown benchmark suite version")
        versions.add(version)
        if version == 1:
            continue
        hashes = tuple(info.get(field) for field in (
            "suite_sha256", "task_sha256", "repository_sha256", "verification_sha256",
        ))
        if any(not isinstance(value, str) or len(value) != 64 for value in hashes):
            raise ValueError("Missing or invalid v2 benchmark fingerprints")
        task = info["task_id"]
        if task in fingerprints and fingerprints[task] != hashes:
            raise ValueError("Inconsistent v2 fingerprints within one run")
        fingerprints[task] = hashes
    if len(versions) != 1:
        raise ValueError("Cannot mix suite versions within a run")
    return versions.pop(), fingerprints


def _validate_runs(paths: list[Path], output: Path) -> list[Run]:
    if not 2 <= len(paths) <= 6:
        raise ValueError("Provide between two and six benchmark result files")
    sources = [path.expanduser().resolve(strict=True) for path in paths]
    if len(set(sources)) != len(sources):
        raise ValueError("Benchmark inputs must be distinct files")
    if output.expanduser().resolve() in sources:
        raise ValueError("Comparison output must differ from input JSONL files")
    runs = [_read_run(path) for path in sources]
    if len({run.label for run in runs}) != len(runs):
        raise ValueError("Result filenames must have distinct stems")
    first = runs[0]
    fingerprints = _case_fingerprints(first)
    for run in runs[1:]:
        if run.suite != first.suite:
            raise ValueError("Cannot compare different benchmark suites")
        if run.trials() != first.trials():
            raise ValueError("Runs must contain the same task IDs and trial numbers")
        if _case_fingerprints(run) != fingerprints:
            raise ValueError("V2 benchmark fingerprints differ between runs")
    return runs


def render_comparison(runs: list[Run]) -> str:
    """Format a comparison with the first run as the reference."""
    baseline = _stats(runs[0].records)["repair_rate"]
    lines = [
        "# AgentForge benchmark comparison",
        "",
        f"Suite: {_safe_cell(runs[0].suite)}",
        "",
        "The first file is the reference. Differences are percentage points, not relative percentages.",
        "Model calls count recorded attempts; older single-attempt records count as one call per trial.",
        "Matching task IDs and trial numbers do not establish identical task content or paired randomness.",
        "",
        "## Summary",
        "",
        "| Run | Model | Strategy | Context | Max attempts | Repairs | Rate | Change | Errors | Calls | Median time (s) |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        stats = _stats(run.records)
        delta = 100 * (stats["repair_rate"] - baseline)
        lines.append(
            f"| {_safe_cell(run.label)} | {_safe_cell(run.model)} | "
            f"{run.strategy} | {run.context} | {run.max_attempts} | "
            f"{stats['repaired']}/{stats['attempts']} | "
            f"{stats['repair_rate']:.1%} | {delta:+.1f} pp | "
            f"{stats['errors']} | {stats['model_calls']} | {stats['median_seconds']:.3f} |"
        )

    lines.extend([
        "",
        "## Results by task",
        "",
        "| Task | " + " | ".join(_safe_cell(run.label) for run in runs) + " |",
        "| --- | " + " | ".join("---:" for _ in runs) + " |",
    ])
    task_ids = sorted({task_id for task_id, _ in runs[0].trials()})
    for task_id in task_ids:
        rates = []
        for run in runs:
            records = [record for record in run.records
                       if record["benchmark"]["task_id"] == task_id]
            stats = _stats(records)
            rates.append(f"{stats['repaired']}/{stats['attempts']} ({stats['repair_rate']:.1%})")
        lines.append(f"| {_safe_cell(task_id)} | " + " | ".join(rates) + " |")

    return "\n".join(lines).rstrip() + "\n"


def compare_results(paths: list[Path], output: Path) -> dict:
    """Save a comparison using existing JSONL files without rerunning models."""
    runs = _validate_runs(paths, output)
    destination = output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_comparison(runs), encoding="utf-8")
    return {
        "suite": runs[0].suite,
        "runs": [
            {"label": run.label, "model": run.model, "strategy": run.strategy,
             "context": run.context, **_stats(run.records)}
            for run in runs
        ],
        "output": str(destination),
    }
