# Per-attempt patch tracking

New benchmark JSONL records contain an `attempt_details` array, in addition to the
existing `diff` and `trajectory` fields. Each accepted attempt records the actual
unified diff against the workspace at that attempt, a SHA256 fingerprint, its changed
files, the public-check pass status, and whether the public check transitioned from
failing to passing. Rejected proposals have no recorded diff or check result.

The public failure category is inferred from available check output and is one of:
`passed`, `timeout`, `syntax_error`, `collection_error`, `test_failure`,
`check_failed`, or `not_run`. It is a diagnostic category, not a verified root cause.
A failed check that passes additional tests but remains unsuccessful is not counted
as an improvement by this pass/fail-only indicator.

The top-level `diff` is preserved for compatibility. For feedback trials, it is
the concatenation of changes from every accepted attempt. The new array preserves
the boundaries between attempts. Historical JSONL records do not contain these new
fields and cannot be retroactively split into individual patches.

Independent verification is still performed only after the final public-check
attempt. No verification test or output is supplied to the model during retries.

## Inspecting a new run

```bash
agentforge benchmark audit runs/example_new.jsonl \
  --output runs/example_new_audit.md

agentforge benchmark diagnose runs/example_new.jsonl \
  --output runs/example_new_failures.md
```

The audit reports distinct per-attempt patches only for trials that contain
`attempt_details`. Historical files retain their earlier combined-diff statistics.

This instrumentation does not change benchmark tasks, model prompts or scoring.
