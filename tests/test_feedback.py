import json

import pytest

from agentforge.cli import main
from agentforge.feedback import evaluate_with_feedback
from agentforge.suite import run_suite


def make_fixture(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    source = repo / "src" / "parser.py"
    source.write_text('def parse(line):\n    return line.split(",")\n')
    (repo / "tests").mkdir()
    (repo / "tests" / "test_parser.py").write_text(
        "from src.parser import parse\n\n"
        "def test_quoted_comma():\n"
        "    assert parse('\"a,b\",c') == ['a,b', 'c']\n"
    )
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "schema_version": 1,
        "task_id": "parser-1",
        "title": "Repair parsing of quoted CSV fields",
        "repository": "repo",
        "check": "pytest",
        "timeout": 30,
    }))
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({
        "schema_version": 1,
        "name": "repair-test",
        "cases": [{"task": "task.json", "files": ["src/parser.py"]}],
    }))
    return task, suite, source


def proposal(content):
    return json.dumps({
        "schema_version": 1,
        "edits": [{"path": "src/parser.py", "content": content}],
    })


UNCHANGED = 'def parse(line):\n    return line.split(",")\n'
FIXED = 'import csv\n\n\ndef parse(line):\n    return next(csv.reader([line]))\n'


class Replies:
    model = "mock-model"

    def __init__(self, replies):
        self.replies = iter(replies)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return next(self.replies)


def test_retry_uses_failing_test_output(tmp_path):
    task, _, source = make_fixture(tmp_path)
    model = Replies([proposal(UNCHANGED), proposal(FIXED)])
    record = evaluate_with_feedback(task, model, ["src/parser.py"])
    assert record["improved"] is True
    assert record["first_attempt_improved"] is False
    assert record["attempts_used"] == 2
    assert record["candidate"]["passed"] is True
    assert "test_quoted_comma" in model.prompts[1]
    assert source.read_text() == UNCHANGED


def test_invalid_empty_edit_gets_retry(tmp_path):
    task, _, _ = make_fixture(tmp_path)
    model = Replies(['{"schema_version":1,"edits":[]}', proposal(FIXED)])
    record = evaluate_with_feedback(task, model, ["src/parser.py"])
    assert record["improved"]
    assert record["attempts_used"] == 2
    assert record["trajectory"][1]["action"] == "proposal_rejected"
    assert "between 1 and 20 edits" in model.prompts[1]


def test_pass_on_first_attempt_stops(tmp_path):
    task, _, _ = make_fixture(tmp_path)
    model = Replies([proposal(FIXED)])
    record = evaluate_with_feedback(task, model, ["src/parser.py"], max_attempts=3)
    assert record["improved"]
    assert record["first_attempt_improved"]
    assert len(model.prompts) == 1


def test_exhausted_retries_keep_error(tmp_path):
    task, _, _ = make_fixture(tmp_path)
    model = Replies(['{"schema_version":1,"edits":[]}', '{"schema_version":1,"edits":[]}'])
    record = evaluate_with_feedback(task, model, ["src/parser.py"])
    assert record["improved"] is False
    assert record["candidate"] is None
    assert "between 1 and 20 edits" in record["error"]
    assert record["attempts_used"] == 2


def test_exhausted_failed_checks(tmp_path):
    task, _, _ = make_fixture(tmp_path)
    model = Replies([proposal(UNCHANGED), proposal(UNCHANGED)])
    record = evaluate_with_feedback(task, model, ["src/parser.py"])
    assert not record["improved"]
    assert record["error"] is None
    assert record["candidate"]["passed"] is False
    assert record["attempts_used"] == 2


@pytest.mark.parametrize("limit", [0, 6, True, "two"])
def test_invalid_attempt_budget(tmp_path, limit):
    task, _, _ = make_fixture(tmp_path)
    with pytest.raises(ValueError, match="max_attempts"):
        evaluate_with_feedback(task, Replies([]), ["src/parser.py"], max_attempts=limit)


def test_suite_feedback_metrics_and_jsonl(tmp_path):
    _, suite, source = make_fixture(tmp_path)
    output = tmp_path / "runs" / "feedback.jsonl"
    instances = []

    def make_model(model):
        instance = Replies([proposal(UNCHANGED), proposal(FIXED)])
        instances.append(instance)
        return instance

    summary = run_suite(
        suite, ["mock"], repeats=2, strategy="feedback", max_attempts=2,
        output=output, client_factory=make_model,
    )
    assert summary["models"]["mock"]["repaired"] == 2
    assert summary["models"]["mock"]["first_attempt_repairs"] == 0
    assert summary["models"]["mock"]["model_calls"] == 4
    assert summary["models"]["mock"]["repair_rate"] == 1
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(records) == 2
    assert all(record["benchmark"]["strategy"] == "feedback" for record in records)
    assert all(record["attempts_used"] == 2 for record in records)
    assert all(len(model.prompts) == 2 for model in instances)
    assert source.read_text() == UNCHANGED


def test_suite_single_strategy_is_unchanged(tmp_path):
    _, suite, _ = make_fixture(tmp_path)
    calls = []

    def model_factory(name):
        instance = Replies([proposal(UNCHANGED)])
        calls.append(instance)
        return instance

    summary = run_suite(suite, ["mock"], repeats=1, client_factory=model_factory)
    assert summary["models"]["mock"]["repaired"] == 0
    assert summary["models"]["mock"]["model_calls"] == 1
    assert len(calls[0].prompts) == 1


def test_cli_accepts_feedback_strategy(tmp_path, capsys, monkeypatch):
    _, suite, _ = make_fixture(tmp_path)
    monkeypatch.setattr(
        "agentforge.suite.OllamaClient",
        lambda model, timeout: Replies([proposal(UNCHANGED), proposal(FIXED)]),
    )
    assert main([
        "benchmark", "run", str(suite),
        "--model", "mock", "--repeats", "1",
        "--strategy", "feedback", "--max-attempts", "2",
        "--output", str(tmp_path / "feedback.jsonl"),
    ]) == 0
    assert '"model_calls": 2' in capsys.readouterr().out


def test_invalid_strategy_rejected(tmp_path):
    _, suite, _ = make_fixture(tmp_path)
    with pytest.raises(ValueError, match="strategy"):
        run_suite(suite, ["mock"], strategy="unknown")


def test_feedback_retries_include_repo_tests(tmp_path):
    task, _, _ = make_fixture(tmp_path)
    model = Replies([proposal(UNCHANGED), proposal(FIXED)])
    record = evaluate_with_feedback(
        task, model, ["src/parser.py"], context="tests",
    )
    assert record["improved"] is True
    assert record["agent_details"]["context"] == "tests"
    assert len(model.prompts) == 2
    assert all("test_quoted_comma" in prompt for prompt in model.prompts)


def test_suite_records_test_context(tmp_path):
    _, suite, _ = make_fixture(tmp_path)
    result_file = tmp_path / "runs" / "tests-context.jsonl"

    def make_model(name):
        return Replies([proposal(FIXED)])

    summary = run_suite(
        suite, ["mock"], repeats=1, context="tests",
        client_factory=make_model, output=result_file,
    )
    assert summary["context"] == "tests"
    records = [json.loads(line) for line in result_file.read_text().splitlines()]
    assert records[0]["benchmark"]["context"] == "tests"
    assert records[0]["agent_details"]["context"] == "tests"


def test_cli_accepts_test_context(tmp_path, capsys, monkeypatch):
    _, suite, _ = make_fixture(tmp_path)
    monkeypatch.setattr(
        "agentforge.suite.OllamaClient",
        lambda model, timeout: Replies([proposal(FIXED)]),
    )
    assert main([
        "benchmark", "run", str(suite),
        "--model", "mock", "--repeats", "1",
        "--context", "tests", "--output", str(tmp_path / "context.jsonl"),
    ]) == 0
    assert '"context": "tests"' in capsys.readouterr().out


def test_suite_rejects_invalid_context(tmp_path):
    _, suite, _ = make_fixture(tmp_path)
    with pytest.raises(ValueError, match="context"):
        run_suite(suite, ["mock"], context="unknown")
