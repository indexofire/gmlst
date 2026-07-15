"""Tests for gmlst config init command."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from gmlst.commands.config import _build_source_line, _detect_shell_rc, config_group


class TestDetectShellRc:
    def test_bash_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/bin/bash")
        monkeypatch.setattr(Path, "home", lambda: Path("/fake/home"))
        name, rc = _detect_shell_rc()
        assert name == "bash"
        assert rc == Path("/fake/home/.bashrc")

    def test_zsh_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/usr/bin/zsh")
        monkeypatch.setattr(Path, "home", lambda: Path("/fake/home"))
        name, rc = _detect_shell_rc()
        assert name == "zsh"
        assert rc == Path("/fake/home/.zshrc")

    def test_fish_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/usr/local/bin/fish")
        monkeypatch.setattr(Path, "home", lambda: Path("/fake/home"))
        name, rc = _detect_shell_rc()
        assert name == "fish"
        assert rc == Path("/fake/home/.config/fish/config.fish")

    def test_unknown_shell_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/usr/bin/nologin")
        name, rc = _detect_shell_rc()
        assert name == "nologin"
        assert rc is None

    def test_empty_shell_defaults_to_bash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SHELL", raising=False)
        monkeypatch.setattr(Path, "home", lambda: Path("/fake/home"))
        name, rc = _detect_shell_rc()
        assert name == "bash"
        assert rc == Path("/fake/home/.bashrc")


class TestBuildSourceLine:
    def test_bash_uses_and_operator(self) -> None:
        line = _build_source_line("bash")
        assert "&&" in line
        assert "source" in line
        assert "$HOME/.config/gmlst/env.sh" in line

    def test_fish_uses_semicolon_and(self) -> None:
        line = _build_source_line("fish")
        assert "; and" in line
        assert "test -f" in line


class TestCmdInit:
    def test_appends_source_line_to_bashrc(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.setenv("SHELL", "/bin/bash")

        runner = CliRunner()
        result = runner.invoke(config_group, ["init"])

        assert result.exit_code == 0
        bashrc = home / ".bashrc"
        assert bashrc.exists()
        content = bashrc.read_text()
        assert "gmlst config" in content
        assert "source" in content
        assert "$HOME/.config/gmlst/env.sh" in content

    def test_idempotent_does_not_duplicate(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.setenv("SHELL", "/bin/bash")

        runner = CliRunner()

        result1 = runner.invoke(config_group, ["init"])
        assert result1.exit_code == 0

        result2 = runner.invoke(config_group, ["init"])
        assert result2.exit_code == 0
        assert "Already configured" in result2.output

        bashrc = home / ".bashrc"
        content = bashrc.read_text()
        assert content.count("source") == 1

    def test_creates_rc_file_if_not_exists(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.setenv("SHELL", "/bin/zsh")

        runner = CliRunner()
        result = runner.invoke(config_group, ["init"])

        assert result.exit_code == 0
        zshrc = home / ".zshrc"
        assert zshrc.exists()

    def test_fish_rc_gets_fish_syntax(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.setenv("SHELL", "/usr/bin/fish")

        runner = CliRunner()
        result = runner.invoke(config_group, ["init"])

        assert result.exit_code == 0
        fish_rc = home / ".config" / "fish" / "config.fish"
        assert fish_rc.exists()
        content = fish_rc.read_text()
        assert "; and" in content

    def test_unknown_shell_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        monkeypatch.setenv("SHELL", "/usr/bin/nologin")

        runner = CliRunner()
        result = runner.invoke(config_group, ["init"])

        assert result.exit_code == 1
        assert "Could not detect" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
