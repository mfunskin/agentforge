"""Per-attempt code records classify only public checks."""
import hashlib

import pytest

from agentforge.attempt_tracking import (
    checked_attempt,
    patch_fingerprint,
    public_failure_kind,
    rejected_attempt,
)


@pytest.mark.parametrize(("result", "expected"), [
    (None, "not_run"),
    ({"passed": True, "stdout": "3 passed"}, "passed"),
    ({"passed": False, "timed_out": True}, "timeout"),
    ({"passed": False, "stdout": "E   SyntaxError: '(' was never closed"},
     "syntax_error"),
    ({"passed": False, "stdout": "ERROR collecting tests/test_parser.py"},
     "collection_error"),
    ({"passed": False, "stdout": "FAILED tests/test_pager.py"},
     "test_failure"),
    ({"passed": False, "stdout": "E   Failed: DID NOT RAISE ValueError"},
     "test_failure"),
    ({"passed": False, "stderr": "no tests collected"}, "check_failed"),
])
def test_classifies_public_checks(result, expected):
    assert public_failure_kind(result) == expected


def test_checked_attempt_records_exact_patch_and_transition():
    diff = "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-bad\n+good\n"
    result = checked_attempt(
        2, diff, ["src/app.py"], {"passed": True, "stdout": "3 passed"}, False,
    )
    assert result["attempt"] == 2
    assert result["status"] == "candidate_checked"
    assert result["diff"] == diff
    assert result["patch_sha256"] == hashlib.sha256(diff.encode()).hexdigest()
    assert result["previous_public_check_passed"] is False
    assert result["public_check_passed"] is True
    assert result["public_check_improved"] is True
    assert result["public_failure_kind"] == "passed"


def test_empty_diff_is_not_considered_a_distinct_patch():
    result = checked_attempt(1, "", ["src/app.py"], {"passed": False}, False)
    assert result["patch_sha256"] is None
    assert result["public_check_improved"] is False
    assert patch_fingerprint("") is None


def test_rejected_attempt_is_not_treated_as_a_test_failure():
    result = rejected_attempt(1, "ValueError: bad proposal", False)
    assert result["status"] == "proposal_rejected"
    assert result["public_check_passed"] is None
    assert result["diff"] is None
    assert result["patch_sha256"] is None
    assert result["public_failure_kind"] == "not_run"


def test_nonimproving_public_check_is_not_marked_as_progress():
    result = checked_attempt(2, "-a\n+b", ["src/app.py"], {"passed": False}, False)
    assert result["public_failure_kind"] == "check_failed"
    assert not result["public_check_improved"]
