"""Benchmark v2 fixture integrity and independent verification tests."""
import json
from pathlib import Path

import pytest

from agentforge.comparison import copy_workspace
from agentforge.model_agent import ModelCodingAgent
from agentforge.runner import run_check
from agentforge.suite import load_suite, run_suite
from agentforge.tasks import load_task
from agentforge.verification import (
    directory_digest,
    repository_digest,
    run_verification,
    verification_files,
)

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "benchmarks" / "suites" / "python_repairs_v2.json"
REFERENCE = ROOT / "benchmarks" / "v2" / "reference"


class ReferenceModel:
    model = "reference-model"

    def __init__(self):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        for item in REFERENCE.glob("*.py"):
            source = f"src/{item.name}"
            if f'"path": "{source}"' in prompt:
                return json.dumps({
                    "schema_version": 1,
                    "edits": [{"path": source, "content": item.read_text()}],
                })
        raise AssertionError("Unknown benchmark case")


class PartialHeaderModel:
    model = "partial-model"

    def generate(self, prompt):
        return json.dumps({
            "schema_version": 1,
            "edits": [{
                "path": "src/header_redaction.py",
                "content": (
                    "def redact_headers(headers):\n"
                    "    return {key: '***' if key.lower() == 'authorization' "
                    "else value for key, value in headers.items()}\n"
                ),
            }],
        })


def test_v2_suite_has_separate_verification():
    suite = load_suite(SUITE)
    assert suite.schema_version == 2
    assert len(suite.cases) == 6
    assert len({case.task_id for case in suite.cases}) == 6
    for case in suite.cases:
        task = load_task(case.task_file)
        assert not case.verification.is_relative_to(task.repository)
        assert verification_files(case.verification)
        assert len(directory_digest(case.verification)) == 64
        assert len(repository_digest(task.repository)) == 64


@pytest.mark.parametrize("index", range(6))
def test_reference_solution_fixes_public_and_independent_checks(tmp_path, index):
    case = load_suite(SUITE).cases[index]
    task = load_task(case.task_file)
    workspace = tmp_path / "workspace"
    copy_workspace(task.repository, workspace)
    assert not run_check(workspace, "pytest", timeout=30)["passed"]
    assert not run_verification(workspace, case.verification, timeout=30)["passed"]
    assert not (workspace / ".agentforge_verification").exists()

    source = case.files[0]
    reference = REFERENCE / Path(source).name
    (workspace / source).write_text(reference.read_text())
    assert run_check(workspace, "pytest", timeout=30)["passed"]
    assert run_verification(workspace, case.verification, timeout=30)["passed"]
    assert not (workspace / ".agentforge_verification").exists()


def test_v2_run_records_provenance_and_verified_repairs(tmp_path):
    output = tmp_path / "v2.jsonl"
    result = run_suite(
        SUITE, ["reference"], repeats=1, output=output,
        client_factory=lambda name: ReferenceModel(),
    )
    assert result["schema_version"] == 2
    assert result["total_attempts"] == 6
    assert result["models"]["reference"]["repaired"] == 6
    assert result["models"]["reference"]["visible_repairs"] == 6
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(records) == 6
    for record in records:
        assert record["visible_improved"] is True
        assert record["improved"] is True
        assert record["verification_baseline"]["passed"] is False
        assert record["verification"]["passed"] is True
        info = record["benchmark"]
        assert info["suite_version"] == 2
        assert info["model_digest"] is None
        assert info["model_timeout_seconds"] == 120
        for digest in ("suite_sha256", "task_sha256", "repository_sha256",
                       "verification_sha256"):
            assert len(info[digest]) == 64
        assert record["patch_metrics"]["added_lines"] > 0


def test_public_pass_does_not_count_without_independent_verification(tmp_path):
    # Place a valid one-case suite under an independent temporary benchmark root.
    data = {
        "schema_version": 2,
        "name": "partial-check",
        "cases": [{
            "task": "../v2/tasks/header_redaction.json",
            "files": ["src/header_redaction.py"],
            "verification": "../v2/verification/header_redaction",
        }],
    }
    # Copy the benchmark definition under an independent temporary root.
    fixture_root = tmp_path / "benchmarks"
    (fixture_root / "suites").mkdir(parents=True)
    source_root = ROOT / "benchmarks" / "v2"
    import shutil
    shutil.copytree(source_root, fixture_root / "v2")
    single = fixture_root / "suites" / "partial.json"
    single.write_text(json.dumps(data))

    result_file = tmp_path / "partial.jsonl"
    summary = run_suite(
        single, ["partial"], repeats=1, output=result_file,
        client_factory=lambda name: PartialHeaderModel(),
    )
    record = json.loads(result_file.read_text().splitlines()[0])
    assert record["candidate"]["passed"]
    assert record["visible_improved"]
    assert not record["verification"]["passed"]
    assert not record["improved"]
    assert summary["models"]["partial"]["repaired"] == 0


def test_tests_context_does_not_expose_verification():
    case = load_suite(SUITE).cases[4]
    model = ReferenceModel()
    agent = ModelCodingAgent(model, list(case.files), context="tests")
    agent.propose(load_task(case.task_file))
    assert "test_lowercase_authorization" in model.prompts[0]
    assert "test_cookie_and_proxy_authorization" not in model.prompts[0]


def test_version_one_suite_is_unchanged():
    prior = load_suite(ROOT / "benchmarks" / "suites" / "python_repairs_extended.json")
    assert prior.schema_version == 1
    assert all(case.verification is None for case in prior.cases)


def test_rejects_verification_inside_task_repo(tmp_path):
    root = tmp_path / "benchmarks"
    (root / "suites").mkdir(parents=True)
    (root / "sample_cases" / "repo" / "src").mkdir(parents=True)
    (root / "sample_cases" / "repo" / "tests").mkdir()
    (root / "sample_cases" / "repo" / "src" / "app.py").write_text("pass\n")
    (root / "sample_cases" / "repo" / "tests" / "test_app.py").write_text(
        "def test_ok(): assert True\n"
    )
    task = {
        "schema_version": 1, "task_id": "test-1", "title": "Test",
        "repository": "repo", "check": "pytest", "timeout": 30,
    }
    (root / "sample_cases" / "task.json").write_text(json.dumps(task))
    suite = {
        "schema_version": 2, "name": "no-leak",
        "cases": [{
            "task": "../sample_cases/task.json",
            "files": ["src/app.py"],
            "verification": "../sample_cases/repo/tests",
        }],
    }
    file = root / "suites" / "suite.json"
    file.write_text(json.dumps(suite))
    with pytest.raises(ValueError, match="outside"):
        load_suite(file)


def test_rejects_verification_symlink(tmp_path):
    folder = tmp_path / "verify"
    folder.mkdir()
    external = tmp_path / "external.py"
    external.write_text("def test_ok(): assert True\n")
    (folder / "test_link.py").symlink_to(external)
    with pytest.raises(ValueError, match="test_"):
        verification_files(folder)


def test_verification_does_not_overwrite_workspace(tmp_path):
    folder = tmp_path / "verify"
    folder.mkdir()
    (folder / "test_success.py").write_text("def test_success(): assert True\n")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".agentforge_verification").mkdir()
    with pytest.raises(ValueError, match="already exists"):
        run_verification(workspace, folder, 30)
