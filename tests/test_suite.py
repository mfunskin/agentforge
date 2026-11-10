import json

import pytest

from agentforge.cli import main
from agentforge.suite import load_suite, run_suite


def create_suite(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "calculator.py").write_text(
        "def clamp(value, low, high):\n"
        "    return min(low, max(value, high))\n"
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_calculator.py").write_text(
        "from src.calculator import clamp\n\n"
        "def test_inside():\n    assert clamp(5, 0, 10) == 5\n\n"
        "def test_below():\n    assert clamp(-5, 0, 10) == 0\n\n"
        "def test_above():\n    assert clamp(15, 0, 10) == 10\n"
    )
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "schema_version": 1, "task_id": "clamp-1",
        "title": "Clamp values to the lower and upper bounds",
        "repository": "repo", "check": "pytest", "timeout": 30,
    }))
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({
        "schema_version": 1,
        "name": "repair-suite",
        "cases": [{"task": "task.json", "files": ["src/calculator.py"]}],
    }))
    return suite, repo


class FakeGenerator:
    def __init__(self, model):
        self.model = model

    def generate(self, prompt):
        if self.model == "broken":
            return "invalid response"
        return json.dumps({
            "schema_version": 1,
            "edits": [{
                "path": "src/calculator.py",
                "content": (
                    "def clamp(value, low, high):\n"
                    "    return max(low, min(value, high))\n"
                ),
            }],
        })


def test_suite_validation(tmp_path):
    suite, _ = create_suite(tmp_path)
    parsed = load_suite(suite)
    assert parsed.name == "repair-suite"
    assert parsed.cases[0].task_id == "clamp-1"


def test_functional_repair_over_multiple_runs(tmp_path):
    suite, repo = create_suite(tmp_path)
    original = (repo / "src" / "calculator.py").read_text()
    output = tmp_path / "runs" / "benchmark.jsonl"
    summary = run_suite(
        suite, ["correct"], repeats=2, output=output,
        client_factory=FakeGenerator,
    )
    assert summary["total_attempts"] == 2
    assert summary["models"]["correct"]["repaired"] == 2
    assert summary["models"]["correct"]["repair_rate"] == 1.0
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(records) == 2
    assert all(record["baseline"]["passed"] is False for record in records)
    assert all(record["candidate"]["passed"] is True for record in records)
    assert (repo / "src" / "calculator.py").read_text() == original


def test_failed_model_is_counted(tmp_path):
    suite, _ = create_suite(tmp_path)
    summary = run_suite(
        suite, ["correct", "broken"], repeats=1, client_factory=FakeGenerator,
    )
    assert summary["models"]["correct"]["repair_rate"] == 1
    assert summary["models"]["broken"]["repair_rate"] == 0
    assert summary["models"]["broken"]["errors"] == 1
    assert summary["total_attempts"] == 2


def test_cli_suite_validate(tmp_path, capsys):
    suite, _ = create_suite(tmp_path)
    assert main(["benchmark", "validate", str(suite)]) == 0
    assert "clamp-1" in capsys.readouterr().out


def test_cli_suite_run(tmp_path, capsys, monkeypatch):
    suite, _ = create_suite(tmp_path)
    monkeypatch.setattr("agentforge.suite.OllamaClient", FakeGenerator)
    assert main([
        "benchmark", "run", str(suite),
        "--model", "correct", "--repeats", "1",
    ]) == 0
    assert '"repair_rate": 1.0' in capsys.readouterr().out


@pytest.mark.parametrize("change", [
    {"schema_version": 2},
    {"name": ""},
    {"cases": []},
    {"cases": [{"task": "/etc/passwd", "files": ["src/calculator.py"]}]},
    {"cases": [{"task": "missing.json", "files": ["src/calculator.py"]}]},
    {"cases": [{"task": "task.json", "files": ["../unsafe.py"]}]},
])
def test_invalid_suites(tmp_path, change):
    suite, _ = create_suite(tmp_path)
    data = json.loads(suite.read_text())
    data.update(change)
    suite.write_text(json.dumps(data))
    with pytest.raises((OSError, ValueError, TypeError)):
        load_suite(suite)


@pytest.mark.parametrize("repeats", [0, 11, True, "two"])
def test_invalid_repeat_count(tmp_path, repeats):
    suite, _ = create_suite(tmp_path)
    with pytest.raises(ValueError, match="repeats"):
        run_suite(suite, ["correct"], repeats=repeats, client_factory=FakeGenerator)


def test_duplicate_models(tmp_path):
    suite, _ = create_suite(tmp_path)
    with pytest.raises(ValueError, match="distinct"):
        run_suite(suite, ["same", "same"], client_factory=FakeGenerator)
