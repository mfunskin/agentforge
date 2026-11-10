"""Deterministic check results and JSONL run records."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agentforge.inspector import inspect_repo
from agentforge.runner import run_check


def evaluate(repo: Path, check: str, output: Path, timeout: int = 30) -> dict:
    inventory = inspect_repo(repo)
    result = run_check(repo, check, timeout=timeout)
    record = {"run_id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
              "repository": inventory, "result": result}
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, sort_keys=True) + "\n")
    return record
