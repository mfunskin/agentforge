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
MAX_CONTEXT_BYTES = 96 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class TextGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...


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
        if not isinstance(result, dict) or not isinstance(result.get("response"), str):
            raise ValueError("Ollama response is missing generated text")
        return result["response"]


class ModelCodingAgent:
    """Request replacement source files for an explicit list of repository paths."""

    def __init__(self, generator: TextGenerator, files: list[str]):
        if not 1 <= len(files) <= 5 or len(set(files)) != len(files):
            raise ValueError("Choose between one and five distinct source files")
        for filename in files:
            validate_edit_path(filename)
        self.generator = generator
        self.files = tuple(files)

    def metadata(self) -> dict:
        return {
            "provider": "ollama" if isinstance(self.generator, OllamaClient) else "custom",
            "model": getattr(self.generator, "model", None),
            "input_files": list(self.files),
        }

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

        prompt = (
            "You are fixing a software issue in a trusted local repository. "
            "Return one JSON object with schema_version 1 and an edits array. "
            "Each edit must contain path and the complete replacement content. "
            "Only edit listed input files. No Markdown or explanations.\n"
            f"Issue: {task.title}\n"
            f"Input files: {json.dumps(source_files, ensure_ascii=False)}\n"
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
