"""Validated task definitions for repeatable repository evaluations."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agentforge.runner import ALLOWED_CHECKS


@dataclass(frozen=True)
class CodingTask:
    task_id: str
    title: str
    repository: Path
    check: str
    timeout: int

    def as_dict(self) -> dict:
        return {
            "schema_version": 1,
            "task_id": self.task_id,
            "title": self.title,
            "repository": str(self.repository),
            "check": self.check,
            "timeout": self.timeout,
        }


def load_task(path: Path) -> CodingTask:
    """Load a local JSON task, resolving the repository relative to its file."""
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Task path must be a JSON file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid task JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise TypeError("Task definition must be a JSON object")
    if data.get("schema_version") != 1 or type(data.get("schema_version")) is not int:
        raise ValueError("Unsupported task schema_version; expected 1")
    required = {"schema_version", "task_id", "title", "repository", "check", "timeout"}
    if set(data) != required:
        raise ValueError("Task fields must be exactly: " + ", ".join(sorted(required)))
    for key in ("task_id", "title", "repository", "check"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    if not all(character.isalnum() or character in "_-" for character in data["task_id"]):
        raise ValueError("task_id may only contain letters, numbers, underscores and hyphens")
    if data["check"] not in ALLOWED_CHECKS:
        raise ValueError(f"Unsupported check: {data['check']}")
    if type(data["timeout"]) is not int or not 1 <= data["timeout"] <= 300:
        raise ValueError("timeout must be an integer between 1 and 300")
    location = Path(data["repository"]).expanduser()
    repository = (path.parent / location).resolve()
    if not repository.is_dir():
        raise ValueError("repository must point to a directory")
    return CodingTask(data["task_id"], data["title"], repository, data["check"], data["timeout"])
