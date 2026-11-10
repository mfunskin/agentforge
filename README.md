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
- Markdown reports of measured model and task performance.
- Side-by-side comparisons of saved benchmark experiments.
- Duplicate-patch and trial-identity audits from recorded JSONL results.
- Individual proposal diffs and SHA256 fingerprints for each new benchmark attempt.
- Version 2 suites with separate post-edit verification and run provenance.
- Failure diagnostics for unsuccessful benchmark attempts.
- Optional test-guided correction attempts with model-call tracking.
- Read-only repository test context for coding models.
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

For the extended suite and Markdown report:

```bash
agentforge benchmark run benchmarks/suites/python_repairs_extended.json \
  --model qwen2.5-coder:3b --repeats 3 \
  --output runs/extended_benchmarks.jsonl

agentforge benchmark report runs/extended_benchmarks.jsonl \
  --output runs/extended_benchmarks.md

agentforge benchmark diagnose runs/extended_benchmarks.jsonl \
  --output runs/extended_failures.md

agentforge benchmark run benchmarks/suites/python_repairs_extended.json \
  --model qwen2.5-coder:3b --repeats 3 \
  --strategy feedback --max-attempts 2 \
  --output runs/feedback_benchmarks.jsonl

agentforge benchmark report runs/feedback_benchmarks.jsonl \
  --output runs/feedback_benchmarks.md

agentforge benchmark diagnose runs/feedback_benchmarks.jsonl \
  --output runs/feedback_failures.md

agentforge benchmark run benchmarks/suites/python_repairs_extended.json \
  --model qwen2.5-coder:3b --repeats 3 \
  --strategy feedback --max-attempts 2 --context tests \
  --output runs/test_context_benchmarks.jsonl

```

## Compare benchmark runs

Compare independently saved results without rerunning models:

```bash
agentforge benchmark compare \
  runs/extended_benchmarks.jsonl \
  runs/feedback_benchmarks.jsonl \
  runs/test_context_benchmarks.jsonl \
  --output runs/experiment_comparison.md

cat runs/experiment_comparison.md
```

The comparison uses the first file as the reference. It requires matching task IDs and trial numbers, and reports repair rates, percentage-point differences, model calls, errors and median trial duration. For v2 runs, it reports public-test repairs and independently verified repairs separately, including changes by task. V2 comparisons also require matching suite, task, repository and verification fingerprints. Legacy single-attempt runs count as one model call per trial.

## Audit repeated benchmark patches

Inspect saved JSONL results without executing the model again:

```bash
agentforge benchmark audit runs/v2_qwen7b_single.jsonl \
  --output runs/v2_qwen7b_single_audit.md

agentforge benchmark audit runs/v2_qwen7b_feedback.jsonl \
  --output runs/v2_qwen7b_feedback_audit.md
```

The audit reports public versus verified repairs, model-call counts, duplicate task/iteration IDs, and distinct patch diffs within each task. SHA256 fingerprints compare recorded diff text; feedback diffs may combine multiple edits. Identical patches repeated at temperature zero are not independent solutions.

For new runs, audit output also includes separate per-attempt patch statistics. See
[Per-attempt patch tracking](docs/attempt_tracking.md).

## Benchmark v2

The six-case [Benchmark v2](docs/benchmark_v2.md) suite uses independent post-edit verification and records model and repository provenance. It is separate from the original four-task benchmark. Run it with `benchmarks/suites/python_repairs_v2.json`.

## Expanded twelve-task benchmark

The [twelve-task Benchmark v2 suite](docs/benchmark_v2_twelve.md) retains the
original six cases and adds six new repair problems, including two multi-file
tasks. It uses a separate suite manifest and preserves the historical scores.
Run it with `benchmarks/suites/python_repairs_v2_twelve.json`.

## Test-guided correction

With `--strategy feedback`, a failed model proposal can be revised using the previous error or test output. Each trial starts from the same original task repository. The result records individual attempts, model-call counts and whether the first proposal passed. The default `single` strategy makes one proposal per trial.

Use `--context tests` to include readable `tests/test_*.py` files in the model prompt without allowing the model to edit them. The default `source` context includes only the selected source files. Tests included in the prompt are visible to the model, so these are white-box evaluations rather than held-out assessments.

Use separate JSONL files when comparing the strategies. Checks run locally against trusted code.

## Candidate evaluation

The `task compare` command copies the task repository into a temporary workspace, runs the baseline check, applies the proposed file replacements, and runs the check again. It records the before and after results, changed files, and a unified diff. Original repository files are unchanged.

Only existing files can be replaced by proposals. The checks execute locally with the same user permissions as the CLI, so evaluate code from trusted repositories.

## Data and credentials

Competition datasets are stored locally and used according to their licensing terms. API keys and other credentials are kept out of version control.

## Contributing

Changes are developed in focused branches, tested locally, and reviewed through pull requests. Pull requests summarize what changed and how it was tested.
