"""Audit repeated coding-agent trials using saved benchmark JSONL records."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from agentforge.reports import load_results


def _cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")


def _condition(record: dict) -> tuple:
    info = record["benchmark"]
    return (
        info["suite"],
        info["model"],
        info.get("strategy", "single"),
        info.get("context", "source"),
        info.get("suite_version", 1),
        info.get("model_timeout_seconds"),
        info.get("model_digest"),
        info.get("suite_sha256"),
    )


def _model_calls(record: dict) -> int:
    calls = record.get("attempts_used", 1)
    if type(calls) is not int or calls < 1:
        raise ValueError("Each trial must have a positive model-call count")
    return calls


def _public_repair(record: dict, version: int) -> bool:
    if version == 2:
        return record.get("visible_improved") is True
    return record["improved"]


def _task_summary(records: list[dict], version: int) -> dict:
    """Count identical nonempty diffs within one task, not across different tasks."""
    patches = []
    for record in records:
        diff = record.get("diff")
        if diff is None or diff == "":
            continue
        if not isinstance(diff, str):
            raise ValueError("Recorded diff must be text")
        patches.append(hashlib.sha256(diff.encode("utf-8")).hexdigest())
    counts = Counter(patches)
    return {
        "task_id": records[0]["benchmark"]["task_id"],
        "trials": len(records),
        "public_repairs": sum(_public_repair(record, version) for record in records),
        "repairs": sum(record["improved"] for record in records),
        "model_calls": sum(_model_calls(record) for record in records),
        "patch_records": len(patches),
        "unique_patches": len(counts),
        "repeated_patches": sum(count - 1 for count in counts.values()),
        "missing_diffs": len(records) - len(patches),
        "patches": [
            {"sha256": digest, "trials": count}
            for digest, count in sorted(counts.items())
        ],
    }


def summarize_audit(records: list[dict]) -> list[dict]:
    """Keep experiment conditions distinct and count duplicate trial identifiers."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for record in records:
        groups[_condition(record)].append(record)
    result = []
    for condition, items in sorted(groups.items(), key=lambda entry: str(entry[0])):
        suite, model, strategy, context, version, timeout, digest, suite_sha = condition
        if version not in {1, 2} or type(version) is not int:
            raise ValueError("Unknown benchmark suite version")
        tasks: dict[str, list[dict]] = defaultdict(list)
        for record in items:
            tasks[record["benchmark"]["task_id"]].append(record)

        summaries = [
            _task_summary(tasks[name], version)
            for name in sorted(tasks)
        ]
        indices = Counter(
            (record["benchmark"]["task_id"], record["benchmark"]["iteration"])
            for record in items
        )
        duplicates = sum(count - 1 for count in indices.values())
        result.append({
            "suite": suite,
            "model": model,
            "strategy": strategy,
            "context": context,
            "suite_version": version,
            "model_timeout_seconds": timeout,
            "model_digest": digest,
            "suite_sha256": suite_sha,
            "trials": len(items),
            "public_repairs": sum(item["public_repairs"] for item in summaries),
            "repairs": sum(item["repairs"] for item in summaries),
            "model_calls": sum(item["model_calls"] for item in summaries),
            "patch_records": sum(item["patch_records"] for item in summaries),
            "unique_patches": sum(item["unique_patches"] for item in summaries),
            "repeated_patches": sum(item["repeated_patches"] for item in summaries),
            "missing_diffs": sum(item["missing_diffs"] for item in summaries),
            "duplicate_trial_ids": duplicates,
            "tasks": summaries,
        })
    return result


def render_audit(audits: list[dict]) -> str:
    """Describe the exact patch-repetition evidence without inferring independence."""
    lines = [
        "# AgentForge benchmark repetition audit",
        "",
        "Patch identity uses SHA256 of each recorded nonempty unified diff.",
        "For feedback trials, a diff can contain changes from multiple attempts.",
        "Identical diff hashes mean identical recorded patch text, not independent solutions.",
        "Empty or absent diffs are not counted as distinct patches.",
        "Distinct hashes do not establish statistical independence.",
        "",
    ]
    for run in audits:
        title = f"{run['suite']} / {run['model']} / {run['strategy']} / {run['context']}"
        lines.extend([
            f"## {_cell(title)}",
            "",
            f"Suite version: {run['suite_version']}",
            "",
            "| Measurement | Count |",
            "| --- | ---: |",
            f"| Recorded trials | {run['trials']} |",
            f"| Public-test repairs | {run['public_repairs']} |",
        ])
        if run["suite_version"] == 2:
            lines.append(f"| Verified repairs | {run['repairs']} |")
        else:
            lines.append(f"| Repairs | {run['repairs']} |")
        lines.extend([
            f"| Model calls | {run['model_calls']} |",
            f"| Nonempty patch records | {run['patch_records']} |",
            f"| Distinct per-task patch diffs | {run['unique_patches']} |",
            f"| Repeated patch records | {run['repeated_patches']} |",
            f"| Missing or empty diffs | {run['missing_diffs']} |",
            f"| Duplicate task/iteration IDs | {run['duplicate_trial_ids']} |",
            "",
            "### Per-task repetition",
            "",
            "| Task | Trials | Public | Verified | Distinct diffs | Repeated diffs | No diff |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for task in run["tasks"]:
            lines.append(
                f"| {_cell(task['task_id'])} | {task['trials']} | "
                f"{task['public_repairs']} | {task['repairs']} | "
                f"{task['unique_patches']} | {task['repeated_patches']} | "
                f"{task['missing_diffs']} |"
            )
        lines.extend(["", "### Patch fingerprints", ""])
        for task in run["tasks"]:
            if not task["patches"]:
                lines.append(f"- {_cell(task['task_id'])}: no recorded diff")
                continue
            values = ", ".join(
                f"\`{entry['sha256'][:12]}\` ({entry['trials']} trials)"
                for entry in task["patches"]
            )
            lines.append(f"- {_cell(task['task_id'])}: {values}")
        lines.append("")
        if run["duplicate_trial_ids"]:
            lines.extend([
                "Warning: task/iteration identifiers repeat. The result file may contain",
                "appended experiments; these trials should not be pooled without review.",
                "",
            ])
    return "\n".join(lines).rstrip() + "\n"


def audit_results(results_file: Path, output: Path) -> dict:
    """Audit an existing JSONL file without executing or changing any benchmark."""
    source = results_file.expanduser().resolve(strict=True)
    destination = output.expanduser().resolve()
    if source == destination:
        raise ValueError("Audit output must differ from input JSONL file")
    records = load_results(source)
    audits = summarize_audit(records)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_audit(audits), encoding="utf-8")
    return {
        "conditions": len(audits),
        "runs": [
            {
                "suite": run["suite"],
                "model": run["model"],
                "strategy": run["strategy"],
                "context": run["context"],
                "trials": run["trials"],
                "public_repairs": run["public_repairs"],
                "repairs": run["repairs"],
                "model_calls": run["model_calls"],
                "unique_patches": run["unique_patches"],
                "repeated_patches": run["repeated_patches"],
                "missing_diffs": run["missing_diffs"],
                "duplicate_trial_ids": run["duplicate_trial_ids"],
            }
            for run in audits
        ],
        "output": str(destination),
    }
