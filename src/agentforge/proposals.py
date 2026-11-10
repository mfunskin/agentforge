"""File-edit proposals from deterministic agents and future coding models."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agentforge.tasks import CodingTask


@dataclass(frozen=True)
class FileEdit:
    path: str
    content: str


class CodingAgent(Protocol):
    def propose(self, task: CodingTask) -> tuple[FileEdit, ...]: ...


class ManifestAgent:
    """Read a candidate's file replacements from a local JSON manifest."""

    def __init__(self, manifest: Path):
        self.manifest = manifest

    def propose(self, task: CodingTask) -> tuple[FileEdit, ...]:
        return load_proposal(self.manifest)


def validate_edit_path(filename: str) -> None:
    if not isinstance(filename, str):
        raise TypeError("Edit path must be a string")
    parts = filename.split("/")
    if (filename.startswith("/") or "\\" in filename or ":" in filename
            or "\x00" in filename or any(part in {"", ".", ".."} for part in parts)):
        raise ValueError(f"Invalid relative edit path: {filename!r}")


def load_proposal(path: Path) -> tuple[FileEdit, ...]:
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Proposal path must be a JSON file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid proposal JSON: {exc.msg}") from exc
    return parse_proposal(data)


def parse_proposal(data: object) -> tuple[FileEdit, ...]:
    """Validate a proposal document from disk or a model response."""
    if not isinstance(data, dict):
        raise TypeError("Proposal must be a JSON object")
    if set(data) != {"schema_version", "edits"} or type(data["schema_version"]) is not int:
        raise ValueError("Proposal requires schema_version and edits")
    if data["schema_version"] != 1:
        raise ValueError("Unsupported proposal schema_version")
    edits = data["edits"]
    if not isinstance(edits, list):
        raise TypeError("edits must be an array")
    if not 1 <= len(edits) <= 20:
        raise ValueError("A proposal must contain between 1 and 20 edits")
    proposed = []
    seen = set()
    for entry in edits:
        if not isinstance(entry, dict):
            raise TypeError("Each edit must be an object")
        if set(entry) != {"path", "content"}:
            raise ValueError("Each edit requires path and content")
        filename, content = entry["path"], entry["content"]
        if not isinstance(filename, str) or not isinstance(content, str):
            raise TypeError("Edit path and content must be strings")
        validate_edit_path(filename)
        if len(content.encode("utf-8")) > 1024 * 1024:
            raise ValueError("Edit content exceeds 1 MiB")
        if filename in seen:
            raise ValueError(f"Duplicate edit path: {filename}")
        seen.add(filename)
        proposed.append(FileEdit(filename, content))
    return tuple(proposed)
