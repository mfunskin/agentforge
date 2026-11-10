# AgentForge

AgentForge is a local-first Python toolkit for reproducible software-engineering agent evaluation. The long-term goal is to compare coding-agent strategies on repository tasks, including permitted Kaggle benchmarks, with reliable execution logs and tests.

## Current features

- Repository file inventory and language counts (avoids common generated directories and symlinks).
- Allowlisted `pytest` and `compile` checks with timeouts and subprocess output.
- Structured evaluation runs saved to JSONL.
- Versioned JSON coding tasks with validation and repeatable checks.
- Candidate patch comparisons against baseline checks, including diffs and action records.
- Local Ollama model integration for generating and testing code changes.
- Repeated benchmark suites with functional tests and per-model repair rates.
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
agentforge task validate benchmarks/sample_cases/compile.json
agentforge task run benchmarks/sample_cases/compile.json --output runs/tasks.jsonl
agentforge task compare benchmarks/sample_cases/syntax_fix.json \
  --proposal benchmarks/proposals/syntax_fix.json \
  --output runs/comparisons.jsonl
```

Exit code 0 means inspection/check succeeded; 1 means check failed; 2 means invalid arguments or local file access error.

## Planned engineering milestones

1. Define a versioned coding-task schema and benchmark adapter interface.
2. Capture tool-use trajectories, patch diffs, and test outcomes.
3. Add isolated execution for untrusted code.
4. Implement a basic coding-agent interface with pluggable model backends.
5. Integrate Kaggle benchmarks subject to each competition's rules.
6. Publish reproducible baseline-vs-improvement experiments.

## Local model

See [Local model integration](docs/local_model.md) to generate and evaluate a coding proposal.

## Benchmark suites

Validate and run the included Python repair suite with an installed Ollama model:

```bash
agentforge benchmark validate benchmarks/suites/python_repairs.json
agentforge benchmark run benchmarks/suites/python_repairs.json \
  --model qwen2.5-coder:3b --repeats 3 \
  --output runs/benchmarks.jsonl
```

To compare installed models, supply `--model` again with another model name. The summary reports attempts, repaired tasks and repair rates. Each trial is also written to JSONL.

## Candidate evaluation

The `task compare` command copies the task repository into a temporary workspace, runs the baseline check, applies the proposed file replacements, and runs the check again. It records the before and after results, changed files, and a unified diff. Original repository files are unchanged.

Only existing files can be replaced by proposals. The checks execute locally with the same user permissions as the CLI, so evaluate code from trusted repositories.

## Data and credentials

Competition datasets are stored locally and used according to their licensing terms. API keys and other credentials are kept out of version control.

## Contributing

Changes are developed in focused branches, tested locally, and reviewed through pull requests. Pull requests summarize what changed and how it was tested.
