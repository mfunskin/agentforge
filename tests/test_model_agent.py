import io
import json
from urllib.error import URLError

import pytest

from agentforge.cli import main
from agentforge.comparison import evaluate_agent
from agentforge.model_agent import ModelCodingAgent, OllamaClient
from agentforge.tasks import load_task


def make_task(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("def hello(:\n    return 1\n")
    task = tmp_path / "task.json"
    task.write_text(json.dumps({
        "schema_version": 1, "task_id": "fix-1", "title": "Repair syntax",
        "repository": "repo", "check": "compile", "timeout": 30,
    }))
    return task, repo


class FakeModel:
    model = "test-model"

    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.reply


def reply(path="src/app.py", content="def hello():\n    return 1\n"):
    return json.dumps({
        "schema_version": 1,
        "edits": [{"path": path, "content": content}],
    })


def test_model_repairs_code_without_modifying_source(tmp_path):
    task, repo = make_task(tmp_path)
    original = (repo / "src" / "app.py").read_text()
    model = FakeModel(reply())
    record = evaluate_agent(task, ModelCodingAgent(model, ["src/app.py"]))
    assert record["improved"] is True
    assert record["baseline"]["passed"] is False
    assert record["candidate"]["passed"] is True
    assert record["agent_details"]["input_files"] == ["src/app.py"]
    assert "Repair syntax" in model.prompts[0]
    assert (repo / "src" / "app.py").read_text() == original


@pytest.mark.parametrize("invalid", ["not-json", "[]", reply("../bad.py")])
def test_invalid_model_reply(tmp_path, invalid):
    task, _ = make_task(tmp_path)
    agent = ModelCodingAgent(FakeModel(invalid), ["src/app.py"])
    with pytest.raises((ValueError, TypeError)):
        agent.propose(load_task(task))


def test_model_cannot_edit_unselected_file(tmp_path):
    task, _ = make_task(tmp_path)
    agent = ModelCodingAgent(FakeModel(reply("src/else.py")), ["src/app.py"])
    with pytest.raises(ValueError, match="outside the selected"):
        agent.propose(load_task(task))


def test_model_rejects_source_symlink(tmp_path):
    task, repo = make_task(tmp_path)
    (repo / "src" / "link.py").symlink_to(repo / "src" / "app.py")
    agent = ModelCodingAgent(FakeModel(reply()), ["src/link.py"])
    with pytest.raises(ValueError, match="does not exist"):
        agent.propose(load_task(task))


def test_model_rejects_parent_symlink_escape(tmp_path):
    task, repo = make_task(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("token = 'dummy'\n")
    (repo / "linked").symlink_to(outside, target_is_directory=True)
    agent = ModelCodingAgent(FakeModel(reply()), ["linked/secret.py"])
    with pytest.raises(ValueError, match="escapes the repository"):
        agent.propose(load_task(task))


def test_rejects_duplicate_target_files():
    with pytest.raises(ValueError, match="distinct"):
        ModelCodingAgent(FakeModel(reply()), ["src/app.py", "src/app.py"])


def test_context_size_limit(tmp_path, monkeypatch):
    task, _ = make_task(tmp_path)
    monkeypatch.setattr("agentforge.model_agent.MAX_CONTEXT_BYTES", 1)
    agent = ModelCodingAgent(FakeModel(reply()), ["src/app.py"])
    with pytest.raises(ValueError, match="context limit"):
        agent.propose(load_task(task))


def test_ollama_response(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data)
        captured["timeout"] = timeout
        return io.BytesIO(json.dumps({"response": reply()}).encode("utf-8"))

    monkeypatch.setattr("agentforge.model_agent.urlopen", fake_urlopen)
    client = OllamaClient("example:7b", timeout=15)
    assert client.generate("Fix this") == reply()
    assert captured["url"].startswith("http://127.0.0.1:11434/")
    assert captured["body"]["stream"] is False
    assert captured["body"]["format"] == "json"
    assert captured["timeout"] == 15


def test_ollama_connection_error(monkeypatch):
    def unavailable(req, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("agentforge.model_agent.urlopen", unavailable)
    with pytest.raises(ValueError, match="Cannot generate proposal"):
        OllamaClient("example").generate("hello")


def test_ollama_invalid_server_reply(monkeypatch):
    def invalid(req, timeout):
        return io.BytesIO(b"{broken")

    monkeypatch.setattr("agentforge.model_agent.urlopen", invalid)
    with pytest.raises(ValueError, match="invalid JSON"):
        OllamaClient("example").generate("hello")


def test_cli_model_path_with_fake_ollama(tmp_path, capsys, monkeypatch):
    task, repo = make_task(tmp_path)
    monkeypatch.setattr("agentforge.model_agent.OllamaClient.generate",
                        lambda self, prompt: reply())
    assert main([
        "task", "solve", str(task), "--model", "example",
        "--file", "src/app.py",
    ]) == 0
    assert '"improved": true' in capsys.readouterr().out
    assert (repo / "src" / "app.py").read_text().startswith("def hello(:")


def test_tests_context_includes_read_only_assertions(tmp_path):
    task, repo = make_task(tmp_path)
    folder = repo / "tests"
    folder.mkdir()
    (folder / "test_app.py").write_text(
        "from src.app import hello\n\n"
        "def test_hello():\n    assert hello() == 1\n"
    )
    generator = FakeModel(reply())
    agent = ModelCodingAgent(generator, ["src/app.py"], context="tests")
    agent.propose(load_task(task))
    prompt = generator.prompts[0]
    assert "Repository tests (read-only" in prompt
    assert "tests/test_app.py" in prompt
    assert "assert hello() == 1" in prompt
    assert agent.metadata()["context"] == "tests"


def test_source_context_does_not_include_tests(tmp_path):
    task, repo = make_task(tmp_path)
    folder = repo / "tests"
    folder.mkdir()
    (folder / "test_app.py").write_text("SENTINEL_TEST_CONTENT\n")
    generator = FakeModel(reply())
    ModelCodingAgent(generator, ["src/app.py"]).propose(load_task(task))
    assert "SENTINEL_TEST_CONTENT" not in generator.prompts[0]


def test_test_context_skips_symlinked_test_files(tmp_path):
    task, repo = make_task(tmp_path)
    folder = repo / "tests"
    folder.mkdir()
    secret = tmp_path / "private.py"
    secret.write_text("SENTINEL_PRIVATE\n")
    (folder / "test_private.py").symlink_to(secret)
    generator = FakeModel(reply())
    ModelCodingAgent(generator, ["src/app.py"], context="tests").propose(load_task(task))
    assert "SENTINEL_PRIVATE" not in generator.prompts[0]


def test_test_context_limit(tmp_path, monkeypatch):
    task, repo = make_task(tmp_path)
    folder = repo / "tests"
    folder.mkdir()
    (folder / "test_app.py").write_text("X" * 40)
    monkeypatch.setattr("agentforge.model_agent.MAX_TEST_CONTEXT_BYTES", 8)
    agent = ModelCodingAgent(FakeModel(reply()), ["src/app.py"], context="tests")
    with pytest.raises(ValueError, match="test context limit"):
        agent.propose(load_task(task))


def test_invalid_context():
    with pytest.raises(ValueError, match="context"):
        ModelCodingAgent(FakeModel(reply()), ["src/app.py"], context="everything")
