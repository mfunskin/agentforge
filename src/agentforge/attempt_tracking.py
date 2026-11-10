"""Per-attempt patch records and public-check failure categories."""
from __future__ import annotations

import hashlib


def patch_fingerprint(diff: str) -> str | None:
    """Identify a nonempty unified diff by its exact recorded bytes."""
    return hashlib.sha256(diff.encode("utf-8")).hexdigest() if diff else None


def public_failure_kind(check: dict | None) -> str:
    """Classify a local check from its saved result, without reading verification."""
    if check is None:
        return "not_run"
    if check.get("passed") is True:
        return "passed"
    if check.get("timed_out") is True:
        return "timeout"
    output = "\n".join((check.get("stdout") or "", check.get("stderr") or ""))
    if "SyntaxError:" in output or "IndentationError:" in output:
        return "syntax_error"
    if "ERROR collecting" in output or "errors during collection" in output:
        return "collection_error"
    if "FAILED " in output or "Failed: DID NOT RAISE" in output:
        return "test_failure"
    return "check_failed"


def checked_attempt(number: int, diff: str, files: list[str], check: dict,
                    previous_passed: bool) -> dict:
    """Record precisely what one proposal changed and what its public check found."""
    passed = check["passed"]
    return {
        "attempt": number,
        "status": "candidate_checked",
        "diff": diff,
        "patch_sha256": patch_fingerprint(diff),
        "changed_files": list(files),
        "previous_public_check_passed": previous_passed,
        "public_check_passed": passed,
        "public_check_improved": not previous_passed and passed,
        "public_failure_kind": public_failure_kind(check),
    }


def rejected_attempt(number: int, error: str, previous_passed: bool) -> dict:
    """Keep a failed proposal separate from a failed candidate test."""
    return {
        "attempt": number,
        "status": "proposal_rejected",
        "diff": None,
        "patch_sha256": None,
        "changed_files": [],
        "previous_public_check_passed": previous_passed,
        "public_check_passed": None,
        "public_check_improved": False,
        "public_failure_kind": "not_run",
        "error": error,
    }
