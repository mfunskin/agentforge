import json

import pytest

from agentforge.benchmark import run_task
from agentforge.cli import main
from agentforge.tasks import load_task


def make_task(tmp_path, *, repository="repo", check="compile", timeout=30):
    (tmp_path / "repo").mkdir(exist_ok=True)
    (tmp_path / "repo" / "src").mkdir(exist_ok=True)
    (tmp_path / "repo" / "src" / "app.py").write_text("answer = 42\n")
    task = {
        "schema_version": 1,
        "task_id": "demo-1",
        "title": "Compile sample code",
        "repository": repository,
        "check": check,
        "timeout": timeout,
    }
    path = tmp_path / "task.json"
    path.write_text(json.dumps(task))
    return path


def test_load_task_resolves_relative_repository(tmp_path):
    path = make_task(tmp_path)
    task = load_task(path)
    assert task.repository == (tmp_path / "repo").resolve()
    assert task.task_id == "demo-1"


def test_task_runner_records_result(tmp_path):
    path = make_task(tmp_path)
    output = tmp_path / "runs" / "records.jsonl"
    record = run_task(path, output)
    assert record["result"]["passed"] is True
    assert record["task"]["schema_version"] == 1
    assert json.loads(output.read_text().strip())["run_id"] == record["run_id"]


def test_task_cli(tmp_path, capsys):
    path = make_task(tmp_path)
    assert main(["task", "validate", str(path)]) == 0
    assert "demo-1" in capsys.readouterr().out
    assert main(["task", "run", str(path)]) == 0
    assert '"passed": true' in capsys.readouterr().out


@pytest.mark.parametrize("change", [
    {"check": "bash"},
    {"timeout": 0},
    {"timeout": True},
    {"repository": "missing"},
    {"task_id": "bad id"},
    {"schema_version": 2},
    {"unknown": "value"},
])
def test_invalid_task(tmp_path, change):
    path = make_task(tmp_path)
    data = json.loads(path.read_text())
    data.update(change)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_task(path)


def test_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{")
    with pytest.raises(ValueError, match="Invalid task JSON"):
        load_task(path)


def test_cli_task_error(tmp_path, capsys):
    assert main(["task", "validate", str(tmp_path / "missing.json")]) == 2
    assert "agentforge:" in capsys.readouterr().err

def test_non_object_json(tmp_path, capsys):
    path = tmp_path / "not_a_task.json"
    path.write_text("[]")
    with pytest.raises(TypeError, match="JSON object"):
        load_task(path)
    assert main(["task", "validate", str(path)]) == 2
    assert "agentforge:" in capsys.readouterr().err
