"""Generate coding proposals with a locally running Ollama model."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agentforge.proposals import FileEdit, parse_proposal, validate_edit_path
from agentforge.tasks import CodingTask

OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
MAX_CONTEXT_BYTES = 96 * 1024
MAX_TEST_CONTEXT_BYTES = 16 * 1024
MAX_TEST_CONTEXT_FILES = 8
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class TextGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...


def ollama_model_digest(model: str) -> str | None:
    """Record the installed model digest when the local Ollama service responds."""
    try:
        with urlopen(Request(OLLAMA_TAGS_URL), timeout=3) as response:
            data = json.loads(response.read(256 * 1024))
    except (OSError, TimeoutError, ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        return None
    for item in data["models"]:
        if not isinstance(item, dict):
            continue
        if item.get("name") == model or item.get("model") == model:
            digest = item.get("digest")
            return digest if isinstance(digest, str) and digest else None
    return None


class OllamaClient:
    """Use Ollama's local generate endpoint without extra Python dependencies."""

    def __init__(self, model: str, timeout: int = 120):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model):
            raise ValueError("Invalid Ollama model name")
        if not 1 <= timeout <= 600:
            raise ValueError("Model timeout must be between 1 and 600 seconds")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        }).encode("utf-8")
        request = Request(
            OLLAMA_GENERATE_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ValueError(f"Cannot generate proposal with Ollama: {exc}") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Ollama response exceeds the size limit")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Ollama returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise TypeError("Ollama response must be a JSON object")
        if "response" not in result:
            raise ValueError("Ollama response is missing generated text")
        if not isinstance(result["response"], str):
            raise TypeError("Ollama generated text must be a string")
        return result["response"]


class ModelCodingAgent:
    """Request replacement source files for an explicit list of repository paths."""

    def __init__(self, generator: TextGenerator, files: list[str], context: str = "source"):
        if not 1 <= len(files) <= 5 or len(set(files)) != len(files):
            raise ValueError("Choose between one and five distinct source files")
        if context not in {"source", "tests"}:
            raise ValueError("context must be source or tests")
        for filename in files:
            validate_edit_path(filename)
        self.generator = generator
        self.files = tuple(files)
        self.context = context

    def metadata(self) -> dict:
        return {
            "provider": "ollama" if isinstance(self.generator, OllamaClient) else "custom",
            "model": getattr(self.generator, "model", None),
            "input_files": list(self.files),
            "context": self.context,
        }

    def _read_tests(self, task: CodingTask) -> list[dict]:
        if self.context != "tests":
            return []
        test_root = task.repository / "tests"
        if test_root.is_symlink() or not test_root.is_dir():
            return []
        names = {Path(filename).stem for filename in self.files}
        candidates = sorted(
            test_root.rglob("test_*.py"),
            key=lambda item: (
                not any(name in item.stem for name in names),
                item.relative_to(test_root).as_posix(),
            ),
        )
        selected = []
        total_bytes = 0
        for path in candidates:
            if len(selected) >= MAX_TEST_CONTEXT_FILES:
                break
            if path.is_symlink() or not path.is_file():
                continue
            if not path.resolve().is_relative_to(test_root.resolve()):
                continue
            contents = path.read_bytes()
            total_bytes += len(contents)
            if total_bytes > MAX_TEST_CONTEXT_BYTES:
                raise ValueError("Repository tests exceed the test context limit")
            try:
                text = contents.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Test file is not UTF-8 text: {path.name}") from exc
            selected.append({
                "path": path.relative_to(task.repository).as_posix(),
                "content": text,
            })
        return selected

    def propose(self, task: CodingTask) -> tuple[FileEdit, ...]:
        source_files = []
        total_bytes = 0
        for filename in self.files:
            source = task.repository.joinpath(*filename.split("/"))
            # Resolve before reading, including any symlink in a parent directory.
            if source.resolve().is_relative_to(task.repository.resolve()) is False:
                raise ValueError(f"Source path escapes the repository: {filename}")
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Source file does not exist: {filename}")
            contents = source.read_bytes()
            total_bytes += len(contents)
            if total_bytes > MAX_CONTEXT_BYTES:
                raise ValueError("Selected source files exceed the context limit")
            try:
                text = contents.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Source file is not UTF-8 text: {filename}") from exc
            source_files.append({"path": filename, "content": text})

        test_files = self._read_tests(task)
        test_context = (
            "Repository tests (read-only; do not modify these files): "
            f"{json.dumps(test_files, ensure_ascii=False)}\n"
            if self.context == "tests" else ""
        )
        prompt = (
            "You are fixing a software issue in a trusted local repository. "
            "Return one JSON object with schema_version 1 and an edits array. "
            "Each edit must contain path and the complete replacement content. "
            "Only edit listed input files. No Markdown or explanations.\n"
            f"Issue: {task.title}\n"
            f"Input files: {json.dumps(source_files, ensure_ascii=False)}\n"
            f"{test_context}"
            "Response example: "
            '{"schema_version":1,"edits":[{"path":"src/app.py","content":"..."}]}'
        )
        generated = self.generator.generate(prompt)
        try:
            data = json.loads(generated)
        except json.JSONDecodeError as exc:
            raise ValueError("Model returned invalid proposal JSON") from exc
        edits = parse_proposal(data)
        permitted = set(self.files)
        if any(edit.path not in permitted for edit in edits):
            raise ValueError("Model proposed a change outside the selected files")
        return edits
