"""Load benchmark suites and compare model performance across coding tasks."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agentforge.comparison import evaluate_agent
from agentforge.model_agent import ModelCodingAgent, OllamaClient, TextGenerator
from agentforge.proposals import validate_edit_path
from agentforge.tasks import load_task


@dataclass(frozen=True)
class SuiteCase:
    task_file: Path
    task_id: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkSuite:
    name: str
    cases: tuple[SuiteCase, ...]

    def as_dict(self) -> dict:
        return {
            "schema_version": 1,
            "name": self.name,
            "cases": [
                {"task_id": case.task_id, "task": str(case.task_file),
                 "files": list(case.files)}
                for case in self.cases
            ],
        }


def load_suite(path: Path) -> BenchmarkSuite:
    """Validate a JSON suite and its referenced coding tasks."""
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Suite path must be a JSON file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid suite JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise TypeError("Suite must be a JSON object")
    if set(data) != {"schema_version", "name", "cases"} or type(data["schema_version"]) is not int:
        raise ValueError("Suite requires schema_version, name and cases")
    if data["schema_version"] != 1:
        raise ValueError("Unsupported suite schema_version")
    if not isinstance(data["name"], str) or not data["name"].strip():
        raise ValueError("Suite name must be a non-empty string")
    if not isinstance(data["cases"], list):
        raise TypeError("Suite cases must be an array")
    if not 1 <= len(data["cases"]) <= 25:
        raise ValueError("Suite must contain between 1 and 25 cases")
    cases = []
    seen = set()
    for entry in data["cases"]:
        if not isinstance(entry, dict):
            raise TypeError("Each suite case must be an object")
        if set(entry) != {"task", "files"}:
            raise ValueError("Each suite case requires task and files")
        if not isinstance(entry["task"], str) or not entry["task"].strip():
            raise ValueError("Case task must be a relative JSON path")
        if Path(entry["task"]).is_absolute():
            raise ValueError("Case task must be a relative JSON path")
        if not isinstance(entry["files"], list):
            raise TypeError("Case files must be an array")
        files = entry["files"]
        if not 1 <= len(files) <= 5:
            raise ValueError("Select between one and five files per case")
        if len(set(files)) != len(files):
            raise ValueError("Duplicate source file in suite case")
        for filename in files:
            validate_edit_path(filename)
        task_file = (path.parent / entry["task"]).resolve(strict=True)
        task = load_task(task_file)
        if task.task_id in seen:
            raise ValueError(f"Duplicate task_id: {task.task_id}")
        seen.add(task.task_id)
        for filename in files:
            source = task.repository.joinpath(*filename.split("/"))
            if not source.resolve().is_relative_to(task.repository.resolve()):
                raise ValueError(f"Source path escapes the repository: {filename}")
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Source file does not exist: {filename}")
        cases.append(SuiteCase(task_file, task.task_id, tuple(files)))
    return BenchmarkSuite(data["name"], tuple(cases))


def run_suite(
    suite_path: Path,
    models: list[str],
    repeats: int = 3,
    output: Path | None = None,
    model_timeout: int = 120,
    client_factory: Callable[[str], TextGenerator] | None = None,
) -> dict:
    """Evaluate every model and task for the same number of independent trials."""
    suite = load_suite(suite_path)
    if not 1 <= len(models) <= 5 or len(set(models)) != len(models):
        raise ValueError("Provide between one and five distinct models")
    if any(not isinstance(model, str) or not model.strip() for model in models):
        raise ValueError("Model names must be non-empty strings")
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError("repeats must be an integer between 1 and 10")
    if type(model_timeout) is not int or not 1 <= model_timeout <= 600:
        raise ValueError("model_timeout must be an integer between 1 and 600")

    destination = output.expanduser().resolve() if output is not None else None
    if destination is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
    metrics = {
        model: {"attempts": 0, "repaired": 0, "candidate_passed": 0, "errors": 0}
        for model in models
    }
    case_metrics = []
    for model in models:
        for case in suite.cases:
            repairs = 0
            for iteration in range(1, repeats + 1):
                start = time.monotonic()
                try:
                    generator = (client_factory(model) if client_factory is not None
                                 else OllamaClient(model, timeout=model_timeout))
                    agent = ModelCodingAgent(generator, list(case.files))
                    record = evaluate_agent(case.task_file, agent)
                    record["error"] = None
                except (OSError, TypeError, ValueError) as exc:
                    record = {
                        "task": {"task_id": case.task_id},
                        "baseline": None,
                        "candidate": None,
                        "improved": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    metrics[model]["errors"] += 1
                record["benchmark"] = {
                    "suite": suite.name, "model": model,
                    "task_id": case.task_id, "iteration": iteration,
                    "duration_seconds": round(time.monotonic() - start, 3),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                metrics[model]["attempts"] += 1
                if record["improved"]:
                    metrics[model]["repaired"] += 1
                    repairs += 1
                if record["candidate"] is not None and record["candidate"]["passed"]:
                    metrics[model]["candidate_passed"] += 1
                if destination is not None:
                    with destination.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(record, sort_keys=True) + "\n")
            case_metrics.append({
                "model": model,
                "task_id": case.task_id,
                "attempts": repeats,
                "repaired": repairs,
                "repair_rate": round(repairs / repeats, 4),
            })
    for stats in metrics.values():
        stats["repair_rate"] = round(stats["repaired"] / stats["attempts"], 4)
    return {
        "suite": suite.name,
        "repeats": repeats,
        "total_attempts": sum(stats["attempts"] for stats in metrics.values()),
        "models": metrics,
        "cases": case_metrics,
        "output": str(destination) if destination is not None else None,
    }
