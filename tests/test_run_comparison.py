import json

import pytest

from agentforge.cli import main
from agentforge.run_comparison import compare_results


def write_run(tmp_path, name, *, strategy="single", context="source",
              outcomes=(True, False), repeats=2, suite="same-suite",
              model="example:3b", missing=None, attempt_counts=None):
    path = tmp_path / f"{name}.jsonl"
    records = []
    for task, success in zip(("syntax", "csv"), outcomes):
        for iteration in range(1, repeats + 1):
            if missing == (task, iteration):
                continue
            info = {
                "suite": suite,
                "model": model,
                "task_id": task,
                "iteration": iteration,
                "duration_seconds": 2.0 if strategy == "single" else 6.0,
            }
            if strategy != "single":
                info["strategy"] = strategy
            if context != "source":
                info["context"] = context
            row = {"benchmark": info, "improved": success, "error": None}
            if strategy == "feedback":
                row["max_attempts"] = 2
                row["attempts_used"] = (attempt_counts or {}).get(task, 2)
            records.append(row)
    path.write_text("\n".join(json.dumps(row) for row in records) + "\n")
    return path


def test_compare_three_conditions(tmp_path):
    original = write_run(tmp_path, "single")
    feedback = write_run(tmp_path, "feedback", strategy="feedback")
    tests = write_run(tmp_path, "test_context", strategy="feedback", context="tests")
    output = tmp_path / "reports" / "comparison.md"
    result = compare_results([original, feedback, tests], output)
    content = output.read_text()
    assert len(result["runs"]) == 3
    assert "| single | example:3b | single | source | 1 | 2/4 | 50.0% | +0.0 pp | 0 | 4 | 2.000 |" in content
    assert "| feedback | example:3b | feedback | source | 2 | 2/4 | 50.0% | +0.0 pp | 0 | 8 | 6.000 |" in content
    assert "| test_context | example:3b | feedback | tests | 2 | 2/4 | 50.0% | +0.0 pp | 0 | 8 | 6.000 |" in content
    assert "| csv | 0/2 (0.0%) | 0/2 (0.0%) | 0/2 (0.0%) |" in content


def test_comparison_reports_percentage_point_change(tmp_path):
    original = write_run(tmp_path, "single", outcomes=(True, False))
    improved = write_run(tmp_path, "better", outcomes=(True, True))
    result = compare_results([original, improved], tmp_path / "comparison.md")
    assert result["runs"][1]["repair_rate"] == 1
    assert "+50.0 pp" in (tmp_path / "comparison.md").read_text()


def test_cli_benchmark_compare(tmp_path, capsys):
    a = write_run(tmp_path, "one")
    b = write_run(tmp_path, "two", strategy="feedback")
    target = tmp_path / "report.md"
    assert main(["benchmark", "compare", str(a), str(b), "--output", str(target)]) == 0
    assert '"suite": "same-suite"' in capsys.readouterr().out
    assert target.exists()


def test_rejects_mismatched_suites(tmp_path):
    a = write_run(tmp_path, "a")
    b = write_run(tmp_path, "b", suite="different")
    with pytest.raises(ValueError, match="different benchmark suites"):
        compare_results([a, b], tmp_path / "report.md")


def test_rejects_missing_trial(tmp_path):
    a = write_run(tmp_path, "a")
    b = write_run(tmp_path, "b", missing=("csv", 2))
    with pytest.raises(ValueError, match="same task IDs"):
        compare_results([a, b], tmp_path / "report.md")


def test_rejects_duplicate_trial(tmp_path):
    a = write_run(tmp_path, "a")
    b = write_run(tmp_path, "b")
    with a.open("a") as stream:
        stream.write(a.read_text().splitlines()[0] + "\n")
    with pytest.raises(ValueError, match="Duplicate task"):
        compare_results([a, b], tmp_path / "report.md")


def test_rejects_mixed_condition(tmp_path):
    a = write_run(tmp_path, "a")
    b = write_run(tmp_path, "b")
    rows = [json.loads(line) for line in b.read_text().splitlines()]
    rows[0]["benchmark"]["context"] = "tests"
    b.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(ValueError, match="one benchmark condition"):
        compare_results([a, b], tmp_path / "report.md")


@pytest.mark.parametrize("count", [0, 1, 7])
def test_rejects_invalid_file_count(tmp_path, count):
    files = [tmp_path / f"missing_{i}.jsonl" for i in range(count)]
    with pytest.raises(ValueError, match="between two and six"):
        compare_results(files, tmp_path / "report.md")


def test_refuses_overwrite_of_results(tmp_path):
    a = write_run(tmp_path, "a")
    b = write_run(tmp_path, "b")
    with pytest.raises(ValueError, match="must differ"):
        compare_results([a, b], a)
    assert a.read_text().startswith("{")


def test_rejects_duplicate_inputs(tmp_path):
    a = write_run(tmp_path, "a")
    with pytest.raises(ValueError, match="distinct files"):
        compare_results([a, a], tmp_path / "report.md")


def test_rejects_duplicated_names(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    a = write_run(first, "results")
    b = write_run(second, "results")
    with pytest.raises(ValueError, match="distinct stems"):
        compare_results([a, b], tmp_path / "report.md")


def test_v2_rejects_changed_verification_fingerprint(tmp_path):
    first = write_run(tmp_path, "first")
    second = write_run(tmp_path, "second")
    for file in (first, second):
        records = [json.loads(line) for line in file.read_text().splitlines()]
        for record in records:
            info = record["benchmark"]
            info.update({
                "suite_version": 2,
                "suite_sha256": "a" * 64,
                "task_sha256": "b" * 64,
                "repository_sha256": "c" * 64,
                "verification_sha256": "d" * 64,
            })
        file.write_text("\n".join(json.dumps(item) for item in records) + "\n")

    rows = [json.loads(line) for line in second.read_text().splitlines()]
    rows[0]["benchmark"]["verification_sha256"] = "e" * 64
    rows[1]["benchmark"]["verification_sha256"] = "e" * 64
    second.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(ValueError, match="fingerprints"):
        compare_results([first, second], tmp_path / "comparison.md")


def test_v2_rejects_inconsistent_fingerprints_in_one_run(tmp_path):
    first = write_run(tmp_path, "first")
    second = write_run(tmp_path, "second")
    for file in (first, second):
        rows = [json.loads(line) for line in file.read_text().splitlines()]
        for row in rows:
            row["benchmark"].update({
                "suite_version": 2,
                "suite_sha256": "a" * 64,
                "task_sha256": "b" * 64,
                "repository_sha256": "c" * 64,
                "verification_sha256": "d" * 64,
            })
        if file == first:
            rows[1]["benchmark"]["repository_sha256"] = "z" * 64
        file.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(ValueError, match="Inconsistent"):
        compare_results([first, second], tmp_path / "comparison.md")


def test_v2_comparison_shows_public_and_verified_outcomes(tmp_path):
    source = write_run(tmp_path, "source", outcomes=(False, False))
    tests = write_run(
        tmp_path, "test_context", strategy="feedback", context="tests",
        outcomes=(False, False),
    )

    for file, passed in ((source, ("syntax",)), (tests, ("syntax", "csv"))):
        records = [json.loads(line) for line in file.read_text().splitlines()]
        for record in records:
            info = record["benchmark"]
            info.update({
                "suite_version": 2,
                "suite_sha256": "a" * 64,
                "task_sha256": ("b" if info["task_id"] == "syntax" else "c") * 64,
                "repository_sha256": "d" * 64,
                "verification_sha256": "e" * 64,
            })
            record["visible_improved"] = info["task_id"] in passed
            record["candidate"] = {"passed": record["visible_improved"]}
            record["verification"] = {"passed": False}
        file.write_text("\n".join(json.dumps(row) for row in records) + "\n")

    report = tmp_path / "comparison.md"
    result = compare_results([source, tests], report)
    rows = result["runs"]
    assert rows[0]["public_repairs"] == 2
    assert rows[1]["public_repairs"] == 4
    assert rows[1]["public_repair_rate"] == 1.0
    assert rows[0]["repair_rate"] == rows[1]["repair_rate"] == 0

    content = report.read_text()
    assert "Public repairs | Public rate | Public change | Verified repairs" in content
    assert "| source | example:3b | single | source | 1 | 2/4 | 50.0% | +0.0 pp | 0/4 | 0.0% | +0.0 pp |" in content
    assert "| test_context | example:3b | feedback | tests | 2 | 4/4 | 100.0% | +50.0 pp | 0/4 | 0.0% | +0.0 pp |" in content
    assert "| csv | Public 0/2, verified 0/2 | Public 2/2, verified 0/2 |" in content


def test_v2_missing_visible_improved_not_counted_as_public_repair(tmp_path):
    source = write_run(tmp_path, "source", outcomes=(False, False))
    tests = write_run(tmp_path, "other", outcomes=(False, False))

    for file in (source, tests):
        rows = [json.loads(line) for line in file.read_text().splitlines()]
        for record in rows:
            record["benchmark"].update({
                "suite_version": 2,
                "suite_sha256": "a" * 64,
                "task_sha256": "b" * 64,
                "repository_sha256": "c" * 64,
                "verification_sha256": "d" * 64,
            })
        file.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    result = compare_results([source, tests], tmp_path / "result.md")
    assert all(row["public_repairs"] == 0 for row in result["runs"])
    assert all(row["public_repair_rate"] == 0 for row in result["runs"])
