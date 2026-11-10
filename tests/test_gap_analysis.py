"""Verify gap reports distinguish public and independent checks."""
import json

import pytest

from agentforge.cli import main
from agentforge.gap_analysis import (
    failed_test_ids,
    generate_gap_report,
    render_gaps,
    summarize_gaps,
)


def _record(model, task, candidate, verification=None, improved=False, iteration=1):
    return {
        "benchmark": {
            "suite": "python-repairs-v2-twelve",
            "model": model,
            "task_id": task,
            "iteration": iteration,
            "duration_seconds": 2.0,
            "suite_version": 2,
        },
        "improved": improved,
        "visible_improved": bool(candidate and candidate.get("passed")),
        "baseline": {"passed": False},
        "candidate": candidate,
        "verification": verification,
        "error": None,
    }


def _file(tmp_path, records):
    path = tmp_path / "results.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in records) + "\n")
    return path


def test_extract_pytest_failure_names_without_assertion_body():
    check = {
        "stdout": (
            "FAILED .agentforge_verification/test_guard.py::test_missing_user - error\n"
            "FAILED .agentforge_verification/test_guard.py::test_missing_user - error\n"
            "E       AttributeError: missing\n"
        ),
        "stderr": (
            "ERROR .agentforge_verification/test_guard.py::test_collect - import error\n"
        ),
    }
    assert failed_test_ids(check) == [
        ".agentforge_verification/test_guard.py::test_collect",
        ".agentforge_verification/test_guard.py::test_missing_user",
    ]
    assert failed_test_ids(None) == []


def test_reports_each_model_and_failing_test(tmp_path):
    failure = {
        "passed": False,
        "stdout": (
            "FAILED .agentforge_verification/test_guard.py::test_unknown_action - assertion\n"
            "FAILED .agentforge_verification/test_guard.py::test_missing_user - assertion\n"
        ),
        "stderr": "",
    }
    records = [
        _record("qwen:3b", "access-policy", {"passed": True}, failure),
        _record("qwen:3b", "rate-limiter", {
            "passed": False, "stdout": "FAILED tests/test_limit.py::test_exact - assertion",
        }),
        _record("qwen:7b", "rate-limiter", {"passed": True}, {"passed": True}, True),
    ]
    source = _file(tmp_path, records)
    destination = tmp_path / "reports" / "gaps.md"
    result = generate_gap_report(source, destination)
    assert result == {
        "conditions": 2,
        "trials": 3,
        "public_passed": 2,
        "verified": 1,
        "verification_failed": 1,
        "output": str(destination.resolve()),
    }
    contents = destination.read_text()
    assert "qwen:3b" in contents
    assert "qwen:7b" in contents
    assert "test_unknown_action" in contents
    assert "test_missing_user" in contents
    assert "test_failure (1)" in contents
    assert "AttributeError" not in contents
    assert "### Verification failures" in contents
    assert source.read_text().startswith("{")


def test_groups_repeated_failing_checks_by_task():
    failure = {
        "passed": False,
        "stdout": "FAILED tests/test_app.py::test_safe - validation",
    }
    records = [
        _record("qwen:3b", "app", {"passed": True}, failure, iteration=1),
        _record("qwen:3b", "app", {"passed": True}, failure, iteration=2),
    ]
    run = summarize_gaps(records)[0]
    assert run["verification_failed"] == 2
    assert run["tasks"][0]["verification_failures"] == {
        "tests/test_app.py::test_safe": 2,
    }


def test_verification_without_named_pytest_failure():
    result = render_gaps(summarize_gaps([
        _record("qwen:3b", "app", {"passed": True}, {
            "passed": False, "stdout": "Timed out",
        }),
    ]))
    assert "No named failing test was found" in result


def test_public_failure_not_reported_as_verification_gap():
    result = summarize_gaps([
        _record("qwen:3b", "app", {
            "passed": False, "stdout": "E  SyntaxError: invalid",
        }),
    ])[0]
    assert result["verification_failed"] == 0
    assert result["tasks"][0]["public_failures"] == {"syntax_error": 1}


def test_legacy_v1_without_verification():
    record = _record("qwen:3b", "app", {"passed": True}, None, True)
    record["benchmark"].pop("suite_version")
    record.pop("visible_improved")
    result = summarize_gaps([record])[0]
    assert result["verified"] == 1
    assert result["verification_failed"] == 0


def test_cli_accepts_gap_command(tmp_path, capsys):
    source = _file(tmp_path, [
        _record("qwen:7b", "app", {"passed": False, "stdout": "test failure"}),
    ])
    output = tmp_path / "gaps.md"
    assert main(["benchmark", "gaps", str(source), "--output", str(output)]) == 0
    assert '"trials": 1' in capsys.readouterr().out
    assert output.exists()


def test_gap_output_cannot_overwrite_source(tmp_path):
    source = _file(tmp_path, [_record("qwen:7b", "app", {"passed": False})])
    with pytest.raises(ValueError, match="must differ"):
        generate_gap_report(source, source)


def test_empty_failed_tests_are_distinct_from_verification_passed():
    records = [
        _record("qwen:3b", "app", {"passed": True}, {"passed": False, "stdout": ""}),
    ]
    result = summarize_gaps(records)[0]
    assert result["tasks"][0]["outcomes"] == {"verification_failed": 1}
    assert result["tasks"][0]["verification_failures"] == {}
