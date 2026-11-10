# Architecture v0.1

CLI (`cli.py`) routes inputs to:

- `inspector.py`: bounded filesystem inventory.
- `runner.py`: allowlisted local subprocess checks.
- `evaluation.py`: composes inspection and execution, appends JSONL records.

**Trust boundary:** This prototype only accepts known check names but is not sandboxed. Local checks can execute arbitrary code defined by the target repo. Do not run on unknown/untrusted code.

**Design decision:** Standard library only for runtime to minimize setup complexity; pytest and Ruff are optional development dependencies. JSONL allows append-only small experiment logs, but lacks concurrency coordination or a schema version. Both should be addressed as evaluation workloads scale.
