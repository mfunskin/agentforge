import json

import pytest

from agentforge.cli import main
from agentforge.reports import generate_report, load_results, render_report


def make_record(suite="python-repairs", model="coder:3b", task="syntax", passed=True,
                duration=1.2, error=None):
    return {
        "benchmark": {
            "suite": suite, "model": model, "task_id": task,
            "iteration": 1, "duration_seconds": duration,
        },
        "improved": passed,
        "error": error,
    }


def write_records(tmp_path, records):
    path = tmp_path / "benchmark.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def test_report_summarizes_models_and_tasks(tmp_path):
    data = [
        make_record(),
        make_record(task="clamp", passed=False, duration=2.4),
        make_record(model="other", passed=False, error="invalid response", duration=0.2),
    ]
    report = render_report(load_results(write_records(tmp_path, data)))
    assert "| coder:3b | 2 | 1 | 50.0% | 0 | 1.800 |" in report
    assert "| other | 1 | 0 | 0.0% | 1 | 0.200 |" in report
    assert "| coder:3b | clamp | 1 | 0 | 0.0% |" in report


def test_report_separates_different_suites(tmp_path):
    records = [
        make_record(suite="suite-a"),
        make_record(suite="suite-b", passed=False),
    ]
    report = render_report(load_results(write_records(tmp_path, records)))
    assert "## suite-a" in report
    assert "## suite-b" in report
    assert report.count("| coder:3b | 1 |") == 2


def test_generate_report_creates_file(tmp_path):
    path = write_records(tmp_path, [make_record()])
    output = tmp_path / "reports" / "result.md"
    summary = generate_report(path, output)
    assert summary["attempts"] == 1
    assert summary["models"] == ["coder:3b"]
    assert "100.0%" in output.read_text()


def test_cli_report_command(tmp_path, capsys):
    path = write_records(tmp_path, [make_record()])
    output = tmp_path / "result.md"
    assert main(["benchmark", "report", str(path), "--output", str(output)]) == 0
    assert '"attempts": 1' in capsys.readouterr().out
    assert output.exists()


@pytest.mark.parametrize("content,exception", [
    ("", ValueError),
    ("{broken\n", ValueError),
    ('[]\n', TypeError),
    ('{"improved":true}\n', TypeError),
    (json.dumps(make_record(duration=-1)) + "\n", ValueError),
    (json.dumps(make_record(passed="true")) + "\n", ValueError),
])
def test_invalid_result_documents(tmp_path, content, exception):
    path = tmp_path / "broken.jsonl"
    path.write_text(content)
    with pytest.raises(exception):
        load_results(path)


def test_report_cannot_replace_results(tmp_path):
    path = write_records(tmp_path, [make_record()])
    with pytest.raises(ValueError, match="must differ"):
        generate_report(path, path)
    assert path.read_text().startswith("{")


def test_report_escapes_table_cells():
    content = render_report([make_record(model="a|b", task="line\nbreak")])
    assert r"a\|b" in content
    assert "line break" in content
