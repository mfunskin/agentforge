"""Independent verification checks for version 2 benchmark suites."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from agentforge.runner import run_check

MAX_VERIFICATION_FILES = 12
MAX_VERIFICATION_BYTES = 64 * 1024


def verification_files(folder: Path) -> list[Path]:
    """Accept a flat directory containing only ordinary Python test files."""
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Verification path must be a regular directory")
    files = sorted(folder.iterdir())
    if not 1 <= len(files) <= MAX_VERIFICATION_FILES:
        raise ValueError("Verification requires between 1 and 12 test files")
    total = 0
    for item in files:
        if (item.is_symlink() or not item.is_file()
                or not item.name.startswith("test_") or item.suffix != ".py"):
            raise ValueError("Verification directory must contain only test_*.py files")
        total += item.stat().st_size
        if total > MAX_VERIFICATION_BYTES:
            raise ValueError("Verification files exceed 64 KiB")
    return files


def file_digest(path: Path) -> str:
    """Hash one benchmark definition or task JSON file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def directory_digest(folder: Path) -> str:
    """Hash benchmark files with their relative paths in stable order."""
    digest = hashlib.sha256()
    for file in verification_files(folder):
        digest.update(file.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def repository_digest(repository: Path) -> str:
    """Fingerprint the original task source and public tests."""
    digest = hashlib.sha256()
    files = sorted(repository.rglob("*"))
    count = 0
    byte_count = 0
    for item in files:
        relative = item.relative_to(repository)
        if any(part in {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
               for part in relative.parts):
            continue
        if item.is_symlink():
            raise ValueError("Version 2 task repositories cannot contain symlinks")
        if not item.is_file():
            continue
        count += 1
        content = item.read_bytes()
        byte_count += len(content)
        if count > 3000 or byte_count > 32 * 1024 * 1024:
            raise ValueError("Task repository exceeds fingerprint limits")
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def git_commit(directory: Path) -> str | None:
    """Return the checked-out commit if the benchmark belongs to a Git repository."""
    try:
        command = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "HEAD"],
            capture_output=True, check=False, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = command.stdout.strip()
    return value if command.returncode == 0 and len(value) == 40 else None


def run_verification(workspace: Path, tests: Path, timeout: int) -> dict:
    """Temporarily add verification tests after all agent edits are complete."""
    originals = verification_files(tests)
    target = workspace / ".agentforge_verification"
    if target.exists() or target.is_symlink():
        raise ValueError("Verification target already exists in the workspace")
    target.mkdir()
    try:
        for file in originals:
            shutil.copy2(file, target / file.name)
        return run_check(workspace, "pytest", timeout, verification=True)
    finally:
        shutil.rmtree(target)
