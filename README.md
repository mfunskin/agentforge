# AgentForge

**Status:** v0.1 prototype — repository inspection, allowlisted checks, and JSONL evaluation recording. **Not yet an autonomous coding agent or Kaggle submission.**

AgentForge is a local-first Python toolkit for reproducible software-engineering agent evaluation. The long-term goal is to compare coding-agent strategies on repository tasks, including permitted Kaggle benchmarks, with reliable execution logs and tests.

## Current features

- Repository file inventory and language counts (avoids common generated directories and symlinks).
- Allowlisted `pytest` and `compile` checks with timeouts and subprocess output.
- Structured evaluation runs saved to JSONL.
- CLI, automated tests, and GitHub Actions CI.

**Security note:** These checks run as subprocesses with your user's privileges. The allowlist prevents arbitrary CLI command strings, but running tests from an untrusted repository can execute untrusted code. Only evaluate repositories you trust. This is **not a sandbox**.

## Installation

Python 3.10+:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e '.[dev]'
pytest -q
```

## Try it

```bash
agentforge inspect .
agentforge check . --name pytest
agentforge check . --name compile
agentforge evaluate . --name pytest --output runs/evaluations.jsonl
```

Exit code 0 means inspection/check succeeded; 1 means check failed; 2 means invalid arguments or local file access error.

## Planned engineering milestones

1. Define a versioned coding-task schema and benchmark adapter interface.
2. Capture tool-use trajectories, patch diffs, and test outcomes.
3. Add isolated execution for untrusted code.
4. Implement a basic coding-agent interface with pluggable model backends.
5. Integrate Kaggle benchmarks subject to each competition's rules.
6. Publish reproducible baseline-vs-improvement experiments.

## Scope and limitations

The current prototype does not generate patches, call LLMs, or submit to Kaggle. It is a small tested foundation for those future capabilities. The file inventory is bounded but is not hardened against hostile filesystems or concurrent filesystem changes.

## Data policy

Do not commit Kaggle competition datasets, API keys, proprietary source code, reviewer records, or unpublished research materials. Review competition licensing and sharing rules before integrating datasets or publishing results.

## Development workflow

Make a GitHub issue for each feature. Implement it in a branch with tests, then open a PR describing problem, design, trade-offs, verification steps and limitations. Keep the commit history authentic.
