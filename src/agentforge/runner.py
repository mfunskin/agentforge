"""Explicit, allowlisted checks. No arbitrary shell execution."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ALLOWED_CHECKS = {
    "pytest": [sys.executable, "-B", "-m", "pytest", "-q"],
    "compile": [sys.executable, "-m", "compileall", "-q", "-f", "src"],
}


def run_check(repo: Path, check: str, timeout: int = 30) -> dict:
    if check not in ALLOWED_CHECKS:
        raise ValueError(f"Unsupported check: {check}. Choose from: {', '.join(ALLOWED_CHECKS)}")
    if not 1 <= timeout <= 300:
        raise ValueError("Timeout must be between 1 and 300 seconds")
    repo = repo.expanduser().resolve(strict=True)
    if not repo.is_dir():
        raise ValueError("Repository path must be a directory")
    start = time.monotonic()
    try:
        process = subprocess.run(ALLOWED_CHECKS[check], check=False, cwd=repo, shell=False,
                                 capture_output=True, text=True, timeout=timeout,
                                 encoding="utf-8", errors="replace")
        return {"check": check, "exit_code": process.returncode, "passed": process.returncode == 0,
                "duration_seconds": round(time.monotonic() - start, 3),
                "stdout": process.stdout[-12000:], "stderr": process.stderr[-12000:]}
    except subprocess.TimeoutExpired:
        return {"check": check, "exit_code": None, "passed": False, "timed_out": True,
                "duration_seconds": round(time.monotonic() - start, 3),
                "stdout": "", "stderr": "Timed out"}
