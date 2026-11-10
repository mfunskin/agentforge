"""Evaluate coding proposals with optional test-guided correction attempts."""
from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agentforge.comparison import apply_edits, copy_workspace
from agentforge.model_agent import ModelCodingAgent, TextGenerator
from agentforge.runner import run_check
from agentforge.tasks import load_task


class FeedbackGenerator:
    """Attach the previous failed check or rejected proposal to a new model prompt."""

    def __init__(self, generator: TextGenerator, feedback: str):
        self.generator = generator
        self.feedback = feedback

    def generate(self, prompt: str) -> str:
        return self.generator.generate(
            prompt
            + "\n\nFeedback from the previous attempt:\n"
            + self.feedback
            + "\nReturn at least one valid replacement for a selected file. "
            + "Use the check failures to correct the underlying issue. "
            + "Return only the requested JSON object."
        )


def _check_feedback(result: dict) -> str:
    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")
    return (
        f"The candidate did not pass the {result['check']} check.\n"
        f"stdout:\n{stdout[-5000:]}\n"
        f"stderr:\n{stderr[-2000:]}"
    )


def evaluate_with_feedback(
    task_file: Path,
    generator: TextGenerator,
    files: list[str],
    max_attempts: int = 2,
    output: Path | None = None,
    context: str = "source",
) -> dict:
    """Try a model proposal again after a rejected edit or failed check."""
    if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be an integer between 1 and 5")
    task = load_task(task_file)
    initial_agent = ModelCodingAgent(generator, files, context=context)
    rounds = []
    changed_files = []
    diffs = []
    candidate = None
    final_error = None
    feedback = ""
    first_attempt_improved = False

    with tempfile.TemporaryDirectory(prefix="agentforge-feedback-") as temporary:
        workspace = Path(temporary) / "repo"
        copy_workspace(task.repository, workspace)
        workspace_task = replace(task, repository=workspace)
        baseline = run_check(workspace, task.check, timeout=task.timeout)

        for number in range(1, max_attempts + 1):
            current_generator = FeedbackGenerator(generator, feedback) if feedback else generator
            agent = ModelCodingAgent(current_generator, files, context=context)
            try:
                edits = agent.propose(workspace_task)
                difference = apply_edits(workspace, edits)
                diffs.append(difference)
                changed_files.extend(edit.path for edit in edits)
                candidate = run_check(workspace, task.check, timeout=task.timeout)
                repaired = not baseline["passed"] and candidate["passed"]
                rounds.append({
                    "attempt": number,
                    "action": "candidate_check",
                    "passed": candidate["passed"],
                    "repaired": repaired,
                    "changed_files": [edit.path for edit in edits],
                    "result": candidate,
                })
                if number == 1:
                    first_attempt_improved = repaired
                final_error = None
                if repaired or candidate["passed"]:
                    break
                feedback = _check_feedback(candidate)
            except (OSError, TypeError, ValueError) as exc:
                final_error = f"{type(exc).__name__}: {exc}"
                rounds.append({
                    "attempt": number,
                    "action": "proposal_rejected",
                    "error": final_error,
                })
                feedback = (
                    f"Your proposal was rejected: {final_error}\n"
                    f"Baseline check output:\n{baseline.get('stdout', '')[-4000:]}\n"
                    f"{baseline.get('stderr', '')[-1000:]}"
                )

    repaired = (
        not baseline["passed"]
        and candidate is not None
        and candidate["passed"]
    )
    record = {
        "run_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task": task.as_dict(),
        "agent": "ModelCodingAgent",
        "agent_details": initial_agent.metadata(),
        "strategy": "feedback",
        "max_attempts": max_attempts,
        "attempts_used": len(rounds),
        "first_attempt_improved": first_attempt_improved,
        "baseline": baseline,
        "candidate": candidate,
        "improved": repaired,
        "error": final_error,
        "changed_files": list(dict.fromkeys(changed_files)),
        "diff": "".join(diffs),
        "trajectory": [{"action": "baseline_check", "passed": baseline["passed"]}, *rounds],
        "result": {"passed": bool(candidate and candidate["passed"])},
    }
    if output is not None:
        destination = output.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    return record
