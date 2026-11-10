# Benchmark v2 expanded suite

The twelve-case suite adds six new, synthetic coding tasks to the original
six-case v2 benchmark. The historical six-case suite and its results are not
changed. The expanded suite has its own name and SHA256 fingerprint, so it
cannot be mixed with the existing results.

The additional tasks cover audit serialization and recursive redaction,
authorization across policy and guard modules, environment-variable parsing,
periodic schedule alignment, idempotent request processing, and UTF-8-aware
batching. Audit serialization and authorization require two coordinated
source-file changes. The remaining tasks require one source-file change each.

Each task has public checks in its fixture repository and separate verification
checks outside that repository. The public tests are available with
`--context tests`, but the independent checks are never included in the
model prompt. Checks are run with the current user's permissions. This is not
a sandbox, and the checks are prompt-held-out rather than secret.

## Run the expanded suite

First activate the AgentForge environment, then validate:

```bash
source .venv/bin/activate
python -m pytest -q
agentforge benchmark validate benchmarks/suites/python_repairs_v2_twelve.json
```

For a local two-model comparison, use one trial per task and the same correction
settings for both models. This evaluates twelve distinct tasks per model rather
than repeating six tasks at temperature zero:

```bash
agentforge benchmark run benchmarks/suites/python_repairs_v2_twelve.json \
  --model qwen2.5-coder:3b \
  --model qwen2.5-coder:7b \
  --repeats 1 \
  --strategy feedback \
  --max-attempts 2 \
  --context source \
  --model-timeout 300 \
  --output runs/v2_twelve_models.jsonl

agentforge benchmark report runs/v2_twelve_models.jsonl \
  --output runs/v2_twelve_models.md

agentforge benchmark audit runs/v2_twelve_models.jsonl \
  --output runs/v2_twelve_audit.md
```

The combined JSONL report supports both models. For a comparison report between
two separate runs, use different output filenames and the existing
`agentforge benchmark compare` command.

### Interpretation

The six original cases appear again in the twelve-case suite. They should not
be counted as six new observations when combining results from separate suites.
One trial per task is an initial engineering smoke test, not a statistical
confidence interval. These are synthetic repairs, not production incidents.

## Diagnose verification gaps

After the evaluation, generate a per-model summary of the public and independent
checks using `agentforge benchmark gaps runs/v2_twelve_models.jsonl --output
runs/v2_twelve_gaps.md`. See [verification gap reports](verification_gaps.md).
