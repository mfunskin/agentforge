import json

import pytest

from agentforge.cli import main
from agentforge.comparison import compare_proposal, copy_workspace, evaluate_agent
from agentforge.proposals import FileEdit, load_proposal


def prepare(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    broken = "def greet(:\n    return 'hello'\n"
    (root / "src" / "example.py").write_text(broken)
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "schema_version": 1, "task_id": "example-1", "title": "Fix syntax",
        "repository": "repo", "check": "compile", "timeout": 30,
    }))
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps({
        "schema_version": 1,
        "edits": [{"path": "src/example.py", "content": "def greet():\n    return 'hello'\n"}],
    }))
    return task, proposal, root, broken


def test_proposal_improves_baseline_without_mutating_repo(tmp_path):
    task, proposal, repo, original = prepare(tmp_path)
    output = tmp_path / "runs" / "comparison.jsonl"
    record = compare_proposal(task, proposal, output)
    assert record["baseline"]["passed"] is False
    assert record["candidate"]["passed"] is True
    assert record["improved"] is True
    assert "-def greet(:" in record["diff"]
    assert len(record["trajectory"]) == 3
    assert len(record["attempt_details"]) == 1
    attempt = record["attempt_details"][0]
    assert attempt["public_check_improved"] is True
    assert attempt["status"] == "candidate_checked"
    assert attempt["patch_sha256"] is not None
    assert attempt["diff"] == record["diff"]
    assert json.loads(output.read_text())["run_id"] == record["run_id"]
    assert (repo / "src" / "example.py").read_text() == original


def test_cli_comparison(tmp_path, capsys):
    task, proposal, _, _ = prepare(tmp_path)
    assert main(["task", "compare", str(task), "--proposal", str(proposal)]) == 0
    assert '"improved": true' in capsys.readouterr().out


def test_candidate_fails_when_fix_does_not_compile(tmp_path):
    task, proposal, _, _ = prepare(tmp_path)
    data = json.loads(proposal.read_text())
    data["edits"][0]["content"] = "bad python (\n"
    proposal.write_text(json.dumps(data))
    record = compare_proposal(task, proposal)
    assert record["candidate"]["passed"] is False
    assert record["improved"] is False


@pytest.mark.parametrize("bad_path", [
    "../other.py", "/tmp/file.py", "src//example.py", "src/./example.py",
    "src/../example.py", "C:/tmp/file.py", "src\\example.py",
])
def test_proposal_rejects_unsafe_paths(tmp_path, bad_path):
    _, proposal, _, _ = prepare(tmp_path)
    data = json.loads(proposal.read_text())
    data["edits"][0]["path"] = bad_path
    proposal.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Invalid relative"):
        load_proposal(proposal)


def test_proposal_rejects_duplicate_edits(tmp_path):
    _, proposal, _, _ = prepare(tmp_path)
    data = json.loads(proposal.read_text())
    data["edits"].append(data["edits"][0])
    proposal.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Duplicate"):
        load_proposal(proposal)


def test_proposal_rejects_non_object(tmp_path):
    _, proposal, _, _ = prepare(tmp_path)
    proposal.write_text("[]")
    with pytest.raises(TypeError):
        load_proposal(proposal)


def test_rejects_nonexistent_edit_target(tmp_path):
    task, proposal, _, _ = prepare(tmp_path)
    data = json.loads(proposal.read_text())
    data["edits"][0]["path"] = "src/missing.py"
    proposal.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="existing regular file"):
        compare_proposal(task, proposal)


def test_workspace_copy_skips_symlinks(tmp_path):
    _, _, repo, _ = prepare(tmp_path)
    (repo / "src" / "linked.py").symlink_to(repo / "src" / "example.py")
    copy_workspace(repo, tmp_path / "copied")
    assert not (tmp_path / "copied" / "src" / "linked.py").exists()


def test_workspace_respects_file_limit(tmp_path, monkeypatch):
    _, _, repo, _ = prepare(tmp_path)
    monkeypatch.setattr("agentforge.comparison.MAX_FILES", 0)
    with pytest.raises(ValueError, match="limit"):
        copy_workspace(repo, tmp_path / "copied")


def test_agent_interface_accepts_custom_implementation(tmp_path):
    task, _, _, _ = prepare(tmp_path)

    class TestAgent:
        def propose(self, task):
            assert task.task_id == "example-1"
            return (FileEdit("src/example.py", "def greet():\n    return 'hello'\n"),)

    result = evaluate_agent(task, TestAgent())
    assert result["improved"] is True
    assert result["agent"] == "TestAgent"


def test_custom_agent_cannot_escape_workspace(tmp_path):
    task, _, _, _ = prepare(tmp_path)

    class BadAgent:
        def propose(self, task):
            return (FileEdit("../../outside.py", "broken"),)

    with pytest.raises(ValueError, match="Invalid relative"):
        evaluate_agent(task, BadAgent())
