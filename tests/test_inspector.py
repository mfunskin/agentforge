from pathlib import Path
import pytest
from agentforge.inspector import inspect_repo


def test_inspect_counts_and_ignores(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('hi')")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "index").write_text("private")
    report = inspect_repo(tmp_path)
    assert report["files"] == 1
    assert report["languages"] == {"Python": 1}


def test_inspect_limits(tmp_path: Path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    with pytest.raises(ValueError, match="File limit"):
        inspect_repo(tmp_path, max_files=1)


def test_inspect_skips_symlink(tmp_path: Path):
    (tmp_path / "a.py").write_text("")
    link = tmp_path / "alias.py"
    try:
        link.symlink_to(tmp_path / "a.py")
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")
    assert inspect_repo(tmp_path)["files"] == 1
