import json

import pytest

from agentforge.cli import main
from agentforge.diagnostics import classify_result, generate_diagnostics, render_diagnostics


def record(*, improved=False, error=None, baseline=None, candidate=None, task="parser",
           iteration=1):
    return {
        "benchmark": {
            "suite": "python-repairs-extended",
            "model": "qwen2.5-coder:3b",
            "task_id": task,
            "iteration": iteration,
            "duration_seconds": 1.5,
        },
        "improved": improved,
        "error": error,
        "baseline": baseline,
        "candidate": candidate,
    }


def save(tmp_path, records):
    path = tmp_path / "results.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


@pytest.mark.parametrize(("candidate", "baseline", "error", "improved", "expected"), [
    ({"passed": True}, {"passed": False}, None, True, "repaired"),
    (None, None, "ValueError: Invalid JSON", False, "recorded_error"),
    (None, None, None, False, "missing_candidate"),
    ({"passed": False, "timed_out": True}, None, None, False, "check_timeout"),
    ({"passed": True}, {"passed": True}, None, False, "baseline_passed"),
    ({"passed": True}, {"passed": False}, None, False, "passed_without_repair"),
    ({"passed": False, "exit_code": 1}, None, None, False, "candidate_check_failed"),
])
def test_classify_outcomes(candidate, baseline, error, improved, expected):
    item = record(improved=improved, error=error, baseline=baseline, candidate=candidate)
    assert classify_result(item) == expected


def test_report_preserves_specific_failure_messages(tmp_path):
    records = [
        record(improved=True, candidate={"passed": True}, task="syntax"),
        record(error="ValueError: Model returned invalid proposal JSON", task="csv"),
        record(candidate={"passed": False, "stdout": "FAILED test_quoted_field"}),
    ]
    source = save(tmp_path, records)
    destination = tmp_path / "diagnostics.md"
    result = generate_diagnostics(source, destination)
    content = destination.read_text()
    assert result["attempts"] == 3
    assert result["repaired"] == 1
    assert result["unsuccessful"] == 2
    assert result["outcomes"]["recorded_error"] == 1
    assert "Model returned invalid proposal JSON" in content
    assert "FAILED test_quoted_field" in content
    assert "qwen2.5-coder:3b / csv" in content
    assert source.read_text().startswith("{")


def test_limits_detailed_failures():
    records = [record(error="bad response", iteration=n) for n in range(1, 4)]
    rendered = render_diagnostics(records, limit=1)
    assert "2 additional failures omitted." in rendered
    assert "trial 1" in rendered
    assert "trial 2" not in rendered


def test_successful_results_report_no_failures():
    report = render_diagnostics([record(improved=True)])
    assert "No unsuccessful attempts were recorded." in report


def test_cli_generates_diagnostics(tmp_path, capsys):
    input_file = save(tmp_path, [record(error="ValueError: invalid proposal")])
    output = tmp_path / "diagnostics.md"
    assert main([
        "benchmark", "diagnose", str(input_file), "--output", str(output),
    ]) == 0
    assert '"unsuccessful": 1' in capsys.readouterr().out
    assert output.exists()


def test_diagnostics_cannot_overwrite_results(tmp_path):
    source = save(tmp_path, [record(error="bad reply")])
    with pytest.raises(ValueError, match="must differ"):
        generate_diagnostics(source, source)


@pytest.mark.parametrize("limit", [0, -1, 501])
def test_invalid_limit(limit):
    with pytest.raises(ValueError, match="Detail limit"):
        render_diagnostics([record(error="failure")], limit=limit)


def test_excerpt_is_bounded():
    report = render_diagnostics([record(error="X" * 10000)])
    assert "X" * 1600 in report
    assert "X" * 1601 not in report


def test_feedback_diagnostics_show_each_retry(tmp_path):
    failed = record(
        task="csv-records-001",
        candidate={"passed": False, "stdout": "FAILED test_quoted_comma"},
    )
    failed["trajectory"] = [
        {"action": "baseline_check", "passed": False},
        {
            "attempt": 1,
            "action": "proposal_rejected",
            "error": "ValueError: A proposal must contain between 1 and 20 edits",
        },
        {
            "attempt": 2,
            "action": "candidate_check",
            "passed": False,
            "result": {"passed": False, "stdout": "FAILED test_escaped_quote", "stderr": ""},
        },
    ]
    output = tmp_path / "feedback_details.md"
    summary = generate_diagnostics(save(tmp_path, [failed]), output)
    content = output.read_text()
    assert "## Feedback attempt outcomes" in content
    assert "| Model calls | 2 |" in content
    assert "| Trials with retries | 1 |" in content
    assert "| Rejected proposals | 1 |" in content
    assert "| Failed candidate checks | 1 |" in content
    assert "#### Attempt 1: Proposal rejected" in content
    assert "between 1 and 20 edits" in content
    assert "#### Attempt 2: Check failed" in content
    assert "FAILED test_escaped_quote" in content
    assert summary["feedback_attempts"]["model_calls"] == 2
    assert "feedback" not in failed.get("benchmark", {})


def test_feedback_recovered_rejection_still_counted():
    repaired = record(improved=True, candidate={"passed": True})
    repaired["trajectory"] = [
        {"action": "baseline_check", "passed": False},
        {"attempt": 1, "action": "proposal_rejected", "error": "Empty edits"},
        {"attempt": 2, "action": "candidate_check", "passed": True,
         "result": {"passed": True, "stdout": "all passed"}},
    ]
    rendered = render_diagnostics([repaired])
    assert "| Rejected proposals | 1 |" in rendered
    assert "| Passing candidate checks | 1 |" in rendered
    assert "No unsuccessful attempts were recorded." in rendered


def test_legacy_diagnostics_do_not_invent_retry_statistics():
    rendered = render_diagnostics([record(error="bad reply")])
    assert "## Feedback attempt outcomes" not in rendered
    assert "bad reply" in rendered
