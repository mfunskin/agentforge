# Benchmark v2

The original four-task `python_repairs_extended.json` suite remains unchanged. Its Qwen2.5-Coder 7B single-attempt reference result is 9/12 (75%) with a 300-second model timeout. That score is not comparable to v2 as a combined score.

## Design

`benchmarks/suites/python_repairs_v2.json` contains six independent, synthetic but service-oriented repair cases: HTTP retries, nested configuration merging, outbox idempotency, token bucket rate limiting, sensitive header redaction, and checkpoint persistence. Each case provides a broken source file, public tests, and separate verification tests.

V2 verification files are stored under `benchmarks/v2/verification/`, outside each task repository. The agent can read the selected source and optionally the task's public tests, but it never receives verification code in its prompt. Verification runs only after all candidate edits and retries. Scores require the public and verification checks to pass, with both starting checks failing. No verification feedback is sent to the agent.

These verification tests are **held out from the model prompt, not secret**: they are available in the public GitHub repository. This benchmark is not designed to resist a malicious agent that can access the filesystem or to substitute for truly private external evaluation.

## Reproducible commands

Validate:

```bash
agentforge benchmark validate benchmarks/suites/python_repairs_v2.json
python -m pytest -q
```

Run the six cases using the stronger previously tested local model:

```bash
agentforge benchmark run benchmarks/suites/python_repairs_v2.json \
  --model qwen2.5-coder:7b \
  --repeats 3 \
  --strategy single \
  --context source \
  --model-timeout 300 \
  --output runs/v2_qwen7b_single.jsonl

agentforge benchmark report runs/v2_qwen7b_single.jsonl \
  --output runs/v2_qwen7b_single.md

agentforge benchmark diagnose runs/v2_qwen7b_single.jsonl \
  --output runs/v2_qwen7b_failures.md
```

Do not append a second experiment to the same JSONL file. Run feedback experiments under a different output filename.

## Results and provenance

- `improved`: authoritative v2 repair outcome, including independent verification.
- `visible_improved`: whether the public task tests passed after the patch.
- `verification_baseline` and `verification`: checks before and after the patch.
- `patch_metrics`: numbers of inserted and deleted diff lines, plus the number of edited files. These are descriptive, not a measure of code quality.
- `benchmark.suite_sha256`, `task_sha256`, `repository_sha256`, `verification_sha256`: content fingerprints for reproducibility.
- `benchmark.git_commit`: checked-out source revision if Git is installed.
- `benchmark.model_digest`: locally reported Ollama model digest when available; otherwise null.
- Strategy, context, model timeout, repeat index and task ID are also saved.

V2 does not offer execution isolation: running a task or verification test executes Python with the user's own permissions. Only evaluate trusted files.
