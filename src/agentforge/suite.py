"""Load benchmark suites and compare model performance across coding tasks."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agentforge.comparison import evaluate_agent
from agentforge.feedback import evaluate_with_feedback
from agentforge.model_agent import (
    ModelCodingAgent,
    OllamaClient,
    TextGenerator,
    ollama_model_digest,
)
from agentforge.proposals import validate_edit_path
from agentforge.tasks import load_task
from agentforge.verification import (
    directory_digest,
    file_digest,
    git_commit,
    repository_digest,
    verification_files,
)


@dataclass(frozen=True)
class SuiteCase:
    task_file: Path
    task_id: str
    files: tuple[str, ...]
    verification: Path | None = None


@dataclass(frozen=True)
class BenchmarkSuite:
    name: str
    cases: tuple[SuiteCase, ...]
    schema_version: int = 1

    def as_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "cases": [
                {
                    "task_id": case.task_id, "task": str(case.task_file),
                    "files": list(case.files),
                    **({"verification": str(case.verification)}
                       if case.verification is not None else {}),
                }
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
    if data["schema_version"] not in {1, 2}:
        raise ValueError("Unsupported suite schema_version")
    version = data["schema_version"]
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
        required_fields = {"task", "files"} if version == 1 else {
            "task", "files", "verification",
        }
        if set(entry) != required_fields:
            raise ValueError("Suite cases require task and files, plus verification in v2")
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
        verification = None
        if version == 2:
            value = entry["verification"]
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Verification must be a relative directory")
            if Path(value).is_absolute():
                raise ValueError("Verification must be a relative directory")
            verification = (path.parent / value).resolve(strict=True)
            if not verification.is_relative_to(path.parent.parent):
                raise ValueError("Verification must remain inside the benchmark tree")
            if verification.is_relative_to(task.repository):
                raise ValueError("Verification must be outside the task repository")
            verification_files(verification)
        cases.append(SuiteCase(task_file, task.task_id, tuple(files), verification))
    return BenchmarkSuite(data["name"], tuple(cases), version)


def run_suite(
    suite_path: Path,
    models: list[str],
    repeats: int = 3,
    output: Path | None = None,
    model_timeout: int = 120,
    client_factory: Callable[[str], TextGenerator] | None = None,
    strategy: str = "single",
    max_attempts: int = 2,
    context: str = "source",
) -> dict:
    """Evaluate every model and task for the same number of independent trials."""
    suite = load_suite(suite_path)
    if strategy not in {"single", "feedback"}:
        raise ValueError("strategy must be single or feedback")
    if context not in {"source", "tests"}:
        raise ValueError("context must be source or tests")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be an integer between 1 and 5")
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
        model: {"attempts": 0, "repaired": 0, "candidate_passed": 0, "errors": 0,
                "first_attempt_repairs": 0, "model_calls": 0}
        for model in models
    }
    case_metrics = []
    version = suite.schema_version
    provenance = {}
    if version == 2:
        for stats in metrics.values():
            stats["visible_repairs"] = 0
        provenance = {
            case.task_id: {
                "task_sha256": file_digest(case.task_file),
                "repository_sha256": repository_digest(load_task(case.task_file).repository),
                "verification_sha256": directory_digest(case.verification),
            }
            for case in suite.cases
        }
    suite_sha = file_digest(suite_path.expanduser().resolve()) if version == 2 else None
    commit = git_commit(suite_path.expanduser().resolve().parent) if version == 2 else None
    model_digests = {
        model: (ollama_model_digest(model) if version == 2 and client_factory is None
                else None)
        for model in models
    }
    for model in models:
        for case in suite.cases:
            repairs = 0
            for iteration in range(1, repeats + 1):
                start = time.monotonic()
                try:
                    generator = (client_factory(model) if client_factory is not None
                                 else OllamaClient(model, timeout=model_timeout))
                    agent = ModelCodingAgent(generator, list(case.files), context=context)
                    if strategy == "feedback":
                        record = evaluate_with_feedback(
                            case.task_file, generator, list(case.files),
                            max_attempts=max_attempts, context=context,
                            verification=case.verification,
                        )
                    else:
                        record = evaluate_agent(
                            case.task_file, agent, verification=case.verification,
                        )
                        record["error"] = None
                    if record["error"] is not None:
                        metrics[model]["errors"] += 1
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
                    "suite": suite.name, "model": model, "strategy": strategy,
                    "context": context,
                    "task_id": case.task_id, "iteration": iteration,
                    "duration_seconds": round(time.monotonic() - start, 3),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    **({
                        "suite_version": version,
                        "suite_sha256": suite_sha,
                        "git_commit": commit,
                        "model_digest": model_digests[model],
                        "model_timeout_seconds": model_timeout,
                        **provenance[case.task_id],
                    } if version == 2 else {}),
                }
                if version == 2:
                    difference = record.get("diff", "")
                    lines = difference.splitlines()
                    record["patch_metrics"] = {
                        "added_lines": sum(
                            line.startswith("+") and not line.startswith("+++")
                            for line in lines
                        ),
                        "removed_lines": sum(
                            line.startswith("-") and not line.startswith("---")
                            for line in lines
                        ),
                        "changed_files": len(record.get("changed_files", [])),
                    }
                metrics[model]["attempts"] += 1
                metrics[model]["model_calls"] += record.get("attempts_used", 1)
                if (record.get("first_attempt_improved", record["improved"])
                        and (version == 1 or record["improved"])):
                    metrics[model]["first_attempt_repairs"] += 1
                if version == 2 and record.get("visible_improved") is True:
                    metrics[model]["visible_repairs"] += 1
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
        "schema_version": version,
        "repeats": repeats,
        "strategy": strategy,
        "context": context,
        "max_attempts": max_attempts if strategy == "feedback" else 1,
        "total_attempts": sum(stats["attempts"] for stats in metrics.values()),
        "models": metrics,
        "cases": case_metrics,
        "output": str(destination) if destination is not None else None,
    }
