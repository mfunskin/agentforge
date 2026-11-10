from pathlib import Path

import pytest

from agentforge.evaluation import evaluate
from agentforge.runner import run_check


def test_compile_success(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "hello.py").write_text("x = 1\n")
    assert run_check(tmp_path, "compile")["passed"]


def test_compile_failure(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "broken.py").write_text("def invalid(:\n")
    assert not run_check(tmp_path, "compile")["passed"]


def test_disallow_arbitrary_command(tmp_path: Path):
    with pytest.raises(ValueError, match="Unsupported check"):
        run_check(tmp_path, "rm -rf /", timeout=10)


def test_timeout_validation(tmp_path: Path):
    with pytest.raises(ValueError, match="Timeout"):
        run_check(tmp_path, "compile", timeout=0)


def test_evaluate_writes_jsonl(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("ok = True\n")
    output = tmp_path / "runs" / "results.jsonl"
    record = evaluate(tmp_path, "compile", output)
    assert record["result"]["passed"]
    assert output.read_text().count("\n") == 1
