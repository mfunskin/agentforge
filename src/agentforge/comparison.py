"""Compare baseline and proposed changes using a temporary repository copy."""
from __future__ import annotations

import difflib
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agentforge.proposals import CodingAgent, FileEdit, ManifestAgent, validate_edit_path
from agentforge.runner import run_check
from agentforge.tasks import load_task
from agentforge.verification import run_verification

EXCLUDED = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    "node_modules", "runs",
}
MAX_FILES = 3000
MAX_BYTES = 32 * 1024 * 1024


def copy_workspace(source: Path, destination: Path) -> None:
    """Copy source files with a size bound, excluding generated files and links."""
    destination.mkdir(parents=True)
    file_count = 0
    byte_count = 0
    for directory, subdirs, filenames in os.walk(source, followlinks=False):
        subdirs[:] = sorted(
            name for name in subdirs
            if name not in EXCLUDED and not (Path(directory) / name).is_symlink()
        )
        relative = Path(directory).relative_to(source)
        target_dir = destination / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in sorted(filenames):
            current = Path(directory) / name
            if current.is_symlink():
                continue
            stat = current.stat()
            file_count += 1
            byte_count += stat.st_size
            if file_count > MAX_FILES or byte_count > MAX_BYTES:
                raise ValueError("Repository exceeds workspace file or size limit")
            shutil.copy2(current, target_dir / name)


def apply_edits(workspace: Path, edits: tuple[FileEdit, ...]) -> str:
    """Replace existing files and return the corresponding unified diff."""
    diffs = []
    for edit in edits:
        validate_edit_path(edit.path)
        destination = workspace.joinpath(*edit.path.split("/"))
        if destination.is_symlink() or not destination.is_file():
            raise ValueError(f"Edit target must be an existing regular file: {edit.path}")
        before = destination.read_text(encoding="utf-8")
        diffs.extend(difflib.unified_diff(
            before.splitlines(keepends=True), edit.content.splitlines(keepends=True),
            fromfile=f"a/{edit.path}", tofile=f"b/{edit.path}",
        ))
        destination.write_text(edit.content, encoding="utf-8")
    return "".join(diffs)


def evaluate_agent(task_file: Path, agent: CodingAgent, output: Path | None = None,
                   verification: Path | None = None) -> dict:
    """Check the task before and after an agent's candidate file replacements."""
    task = load_task(task_file)
    edits = agent.propose(task)
    events = []
    with tempfile.TemporaryDirectory(prefix="agentforge-") as temporary:
        workspace = Path(temporary) / "repo"
        copy_workspace(task.repository, workspace)

        baseline = run_check(workspace, task.check, timeout=task.timeout)
        verify_baseline = (
            run_verification(workspace, verification, task.timeout)
            if verification is not None else None
        )
        events.append({"action": "baseline_check", "passed": baseline["passed"]})

        started = time.monotonic()
        difference = apply_edits(workspace, edits)
        events.append({
            "action": "apply_proposal", "files": [edit.path for edit in edits],
            "duration_seconds": round(time.monotonic() - started, 3),
        })

        candidate = run_check(workspace, task.check, timeout=task.timeout)
        events.append({"action": "candidate_check", "passed": candidate["passed"]})
        verify_candidate = (
            run_verification(workspace, verification, task.timeout)
            if verification is not None else None
        )

    visible_improved = not baseline["passed"] and candidate["passed"]
    verified = (
        visible_improved and not verify_baseline["passed"] and verify_candidate["passed"]
        if verification is not None else None
    )
    record = {
        "run_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task": task.as_dict(),
        "agent": type(agent).__name__,
        "agent_details": agent.metadata() if callable(getattr(agent, "metadata", None)) else {},
        "baseline": baseline,
        "candidate": candidate,
        "improved": verified if verified is not None else visible_improved,
        "visible_improved": visible_improved if verification is not None else None,
        "verification_baseline": verify_baseline,
        "verification": verify_candidate,
        "changed_files": [edit.path for edit in edits],
        "diff": difference,
        "trajectory": events,
        "result": {"passed": verified if verified is not None else candidate["passed"]},
    }
    if output is not None:
        destination = output.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def compare_proposal(task_file: Path, proposal_file: Path, output: Path | None = None) -> dict:
    """Evaluate file edits supplied through a local JSON proposal."""
    return evaluate_agent(task_file, ManifestAgent(proposal_file), output)
