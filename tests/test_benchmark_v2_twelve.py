"""Validate the six additional Benchmark v2 fixtures and their multi-file repairs."""
import json
from pathlib import Path

import pytest

from agentforge.comparison import copy_workspace, evaluate_agent
from agentforge.model_agent import ModelCodingAgent
from agentforge.runner import run_check
from agentforge.suite import load_suite
from agentforge.tasks import load_task
from agentforge.verification import run_verification

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "benchmarks"
ORIGINAL = BASE / "suites" / "python_repairs_v2.json"
EXPANDED = BASE / "suites" / "python_repairs_v2_twelve.json"
REFERENCE = BASE / "v2" / "reference"


class ReferenceGenerator:
    """Return the checked-in reference implementations for the selected files."""

    def __init__(self, files):
        self.files = files
        self.prompt = None

    def generate(self, prompt):
        self.prompt = prompt
        return json.dumps({
            "schema_version": 1,
            "edits": [
                {
                    "path": file,
                    "content": (REFERENCE / Path(file).name).read_text(),
                }
                for file in self.files
            ],
        })


def added_cases():
    original = load_suite(ORIGINAL)
    expanded = load_suite(EXPANDED)
    return expanded.cases[len(original.cases):]


def test_expansion_keeps_original_six_cases_unchanged():
    original = json.loads(ORIGINAL.read_text())
    expanded = json.loads(EXPANDED.read_text())
    assert original["schema_version"] == expanded["schema_version"] == 2
    assert expanded["name"] != original["name"]
    assert expanded["cases"][:6] == original["cases"]
    assert len(expanded["cases"]) == 12
    assert len({case.task_id for case in load_suite(EXPANDED).cases}) == 12
    assert len(added_cases()) == 6
    assert sum(len(case.files) == 2 for case in added_cases()) == 2


@pytest.mark.parametrize("index", range(6))
def test_new_fixture_is_broken_then_fully_repaired(tmp_path, index):
    case = added_cases()[index]
    task = load_task(case.task_file)
    workspace = tmp_path / "workspace"
    copy_workspace(task.repository, workspace)

    assert not run_check(workspace, task.check, timeout=30)["passed"]
    assert not run_verification(workspace, case.verification, timeout=30)["passed"]
    for selected in case.files:
        reference = REFERENCE / Path(selected).name
        assert reference.is_file()
        (workspace / selected).write_text(reference.read_text())

    assert run_check(workspace, task.check, timeout=30)["passed"]
    assert run_verification(workspace, case.verification, timeout=30)["passed"]
    assert not (workspace / ".agentforge_verification").exists()


@pytest.mark.parametrize("index", [0, 1])
def test_model_proposal_repairs_both_modules_and_passes_verification(index):
    case = added_cases()[index]
    model = ReferenceGenerator(list(case.files))
    agent = ModelCodingAgent(model, list(case.files), context="source")
    record = evaluate_agent(case.task_file, agent, verification=case.verification)
    assert len(record["changed_files"]) == 2
    assert record["visible_improved"] is True
    assert record["improved"] is True
    assert len(record["attempt_details"]) == 1
    assert set(record["attempt_details"][0]["changed_files"]) == set(case.files)
    for source in case.files:
        assert source in model.prompt


@pytest.mark.parametrize("index", [0, 1])
def test_model_tests_context_excludes_independent_verification(index):
    case = added_cases()[index]
    model = ReferenceGenerator(list(case.files))
    agent = ModelCodingAgent(model, list(case.files), context="tests")
    agent.propose(load_task(case.task_file))
    if index == 0:
        assert "test_nested_sensitive_values_are_masked" in model.prompt
        assert "test_list_items_and_mixed_case_keys" not in model.prompt
    else:
        assert "test_reader_cannot_write" in model.prompt
        assert "test_admin_not_allowed_unknown_actions" not in model.prompt
