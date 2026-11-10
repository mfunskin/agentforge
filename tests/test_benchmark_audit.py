"""Audit duplicate patches without rerunning benchmark models."""
import json

import pytest

from agentforge.benchmark_audit import audit_results, render_audit, summarize_audit
from agentforge.cli import main


def make_record(task, iteration, diff, *, repaired=False, public=False,
                model="coder:7b", strategy="single", calls=None, version=2):
    record = {
        "benchmark": {
            "suite": "python-repairs-v2",
            "model": model,
            "strategy": strategy,
            "context": "source",
            "task_id": task,
            "iteration": iteration,
            "duration_seconds": 1.0,
            "suite_version": version,
        },
        "improved": repaired,
        "visible_improved": public,
        "error": None,
    }
    if diff is not None:
        record["diff"] = diff
    if calls is not None:
        record["attempts_used"] = calls
    return record


def save(tmp_path, name, rows):
    file = tmp_path / name
    file.write_text("\n".join(json.dumps(item) for item in rows) + "\n")
    return file


def test_identical_patches_count_once_per_task(tmp_path):
    rows = [
        make_record("csv", 1, "--- original\n+++ new\n+fix", public=True),
        make_record("csv", 2, "--- original\n+++ new\n+fix", public=True),
        make_record("csv", 3, "--- original\n+++ new\n+fix", public=True),
        make_record("pager", 1, "--- original\n+++ new\n+fix", repaired=True, public=True),
        make_record("pager", 2, "--- original\n+++ new\n+other"),
    ]
    path = save(tmp_path, "results.jsonl", rows)
    output = tmp_path / "audit.md"
    summary = audit_results(path, output)
    assert summary["conditions"] == 1
    run = summary["runs"][0]
    assert run["trials"] == 5
    assert run["public_repairs"] == 4
    assert run["repairs"] == 1
    assert run["model_calls"] == 5
    assert run["unique_patches"] == 3
    assert run["repeated_patches"] == 2
    assert run["missing_diffs"] == 0
    rendered = output.read_text()
    assert "| csv | 3 | 3 | 0 | 1 | 2 | 0 |" in rendered
    assert "| pager | 2 | 1 | 1 | 2 | 0 | 0 |" in rendered
    assert "Identical diff hashes" in rendered


def test_missing_diffs_not_grouped_into_same_patch():
    rows = [
        make_record("csv", 1, ""),
        make_record("csv", 2, None),
        make_record("csv", 3, "-before\n+after"),
    ]
    run = summarize_audit(rows)[0]
    assert run["missing_diffs"] == 2
    assert run["unique_patches"] == 1
    assert run["repeated_patches"] == 0


def test_feedback_model_call_count_and_combined_diff():
    rows = [
        make_record("csv", 1, "-first\n+next\n-second\n+final",
                    strategy="feedback", calls=2),
        make_record("csv", 2, "-first\n+next\n-second\n+final",
                    strategy="feedback", calls=2),
    ]
    run = summarize_audit(rows)[0]
    assert run["model_calls"] == 4
    assert run["unique_patches"] == 1
    assert run["repeated_patches"] == 1
    assert "feedback trials" in render_audit([run])


def test_conditions_are_not_pooled():
    rows = [
        make_record("csv", 1, "+source", model="coder:3b"),
        make_record("csv", 1, "+source", model="coder:7b"),
        make_record("csv", 1, "+source", model="coder:7b", strategy="feedback"),
    ]
    runs = summarize_audit(rows)
    assert len(runs) == 3
    assert all(run["trials"] == 1 for run in runs)


def test_legacy_v1_public_success_fallback():
    rows = [make_record("csv", 1, "+fix", repaired=True, version=1)]
    rows[0].pop("visible_improved")
    run = summarize_audit(rows)[0]
    assert run["public_repairs"] == 1
    assert run["repairs"] == 1
    assert "Verified repairs" not in render_audit([run])


def test_duplicate_trial_numbers_flagged():
    rows = [
        make_record("csv", 1, "+first"),
        make_record("csv", 1, "+second"),
    ]
    run = summarize_audit(rows)[0]
    assert run["duplicate_trial_ids"] == 1
    assert "appended experiments" in render_audit([run])


def test_cli_audit(tmp_path, capsys):
    rows = [make_record("csv", 1, "+fix", public=True)]
    source = save(tmp_path, "data.jsonl", rows)
    output = tmp_path / "reports" / "audit.md"
    assert main(["benchmark", "audit", str(source), "--output", str(output)]) == 0
    assert '"unique_patches": 1' in capsys.readouterr().out
    assert output.exists()


def test_refuses_result_overwrite(tmp_path):
    source = save(tmp_path, "results.jsonl", [make_record("csv", 1, "+fix")])
    with pytest.raises(ValueError, match="must differ"):
        audit_results(source, source)
    assert source.read_text().startswith("{")


def test_rejects_nontext_diff():
    with pytest.raises(TypeError, match="diff must be text"):
        summarize_audit([make_record("csv", 1, {"unexpected": "object"})])


@pytest.mark.parametrize("calls", [0, -1, "two", True])
def test_invalid_model_calls(calls):
    with pytest.raises(ValueError, match="model-call"):
        summarize_audit([make_record("csv", 1, "+fix", calls=calls)])


def test_invalid_version():
    with pytest.raises(ValueError, match="version"):
        summarize_audit([make_record("csv", 1, "+fix", version=3)])


def test_group_runs_with_different_model_digests():
    rows = [
        make_record("csv", 1, "+fix"),
        make_record("csv", 2, "+fix"),
    ]
    rows[0]["benchmark"]["model_digest"] = "a" * 64
    rows[1]["benchmark"]["model_digest"] = "b" * 64
    assert len(summarize_audit(rows)) == 2
