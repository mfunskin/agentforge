from agentforge.cli import main


def test_inspect_cli(tmp_path, capsys):
    (tmp_path / "app.py").write_text("x=1\n")
    assert main(["inspect", str(tmp_path)]) == 0
    assert '"Python": 1' in capsys.readouterr().out


def test_cli_bad_path(tmp_path, capsys):
    assert main(["inspect", str(tmp_path / "missing")]) == 2
    assert "agentforge:" in capsys.readouterr().err
