"""Execute a coding task with the existing allowlisted check runner."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agentforge.inspector import inspect_repo
from agentforge.runner import run_check
from agentforge.tasks import load_task


def run_task(task_path: Path, output: Path | None = None) -> dict:
    task = load_task(task_path)
    inventory = inspect_repo(task.repository)
    result = run_check(task.repository, task.check, timeout=task.timeout)
    record = {
        "run_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task": task.as_dict(),
        "repository": inventory,
        "result": result,
    }
    if output is not None:
        destination = output.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    return record
