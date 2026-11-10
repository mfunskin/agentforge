# Verification gap reports

A gap report summarizes the recorded final public and independent verification
checks without rerunning a model. It lists per-model outcomes, tasks with
public-test failures and the pytest test identifiers that failed independent
verification.

```bash
agentforge benchmark gaps runs/v2_twelve_models.jsonl \
  --output runs/v2_twelve_gaps.md

cat runs/v2_twelve_gaps.md
```

The report uses the checks already present in JSONL. It does not change a
benchmark result or expose independent verification output to the model.
A recorded failing test identifies an observed assertion failure, not an
independently verified root cause. If pytest did not produce a named failing
test, the report says so.

Original task definitions, scoring rules, source files and existing run
records remain unchanged. Test names are included in the *offline analysis*
report only. In the public repository, these tests are prompt-held-out, not
secret. AgentForge does not sandbox code execution.
