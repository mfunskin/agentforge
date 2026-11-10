"""Bounded repository inventory without following symlinks."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

IGNORED = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".ruff_cache"}
EXTENSIONS = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".rb": "Ruby", ".c": "C", ".cpp": "C++",
}


def inspect_repo(root: Path, max_files: int = 10000) -> dict:
    root = root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Repository path must be a directory")
    if max_files < 1:
        raise ValueError("max_files must be positive")
    counts: Counter[str] = Counter()
    files = 0
    total_bytes = 0
    stack = [root]
    while stack:
        directory = stack.pop()
        for child in sorted(directory.iterdir(), key=lambda x: x.name):
            if child.is_symlink() or child.name in IGNORED:
                continue
            if child.is_dir():
                stack.append(child)
            elif child.is_file():
                files += 1
                if files > max_files:
                    raise ValueError(f"File limit exceeded ({max_files}); use a smaller repository")
                total_bytes += child.stat().st_size
                counts[EXTENSIONS.get(child.suffix.lower(), "Other")] += 1
    return {"path": str(root), "files": files, "bytes": total_bytes,
            "languages": dict(sorted(counts.items()))}
