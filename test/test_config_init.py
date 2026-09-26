"""Tests for gmlst config init, set, show, and get commands."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from gmlst.commands.config import (
    _CONFIG_REGISTRY,
    _build_source_line,
    _detect_shell_rc,
    _is_secret,
    _mask_secret,
    config_group,
)


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


class TestConfigSetFilePermissions:
    def test_env_file_is_owner_only(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "env.sh"
        monkeypatch.setattr("gmlst.commands.config._ENV_FILE_CANDIDATES", [env_file])

        runner = CliRunner()
        result = runner.invoke(
            config_group, ["set", "GMLST_PUBMLST_API_KEY", "secret-key-123"]
        )

        assert result.exit_code == 0
        assert env_file.exists()
        mode = env_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_existing_env_file_permissions_fixed_on_rewrite(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "env.sh"
        env_file.write_text('export GMLST_CACHE_DIR="/old"\n')
        os.chmod(env_file, 0o644)
        assert env_file.stat().st_mode & 0o777 == 0o644

        monkeypatch.setattr("gmlst.commands.config._ENV_FILE_CANDIDATES", [env_file])

        runner = CliRunner()
        runner.invoke(config_group, ["set", "GMLST_TMPDIR", "/scratch"])

        mode = env_file.stat().st_mode & 0o777
        assert mode == 0o600


class TestIsSecret:
    def test_api_key_suffix_is_secret(self) -> None:
        assert _is_secret("GMLST_PUBMLST_API_KEY") is True
        assert _is_secret("GMLST_PASTEUR_API_KEY") is True

    def test_token_in_name_is_secret(self) -> None:
        assert _is_secret("ENTEROBASE_TOKEN") is True

    def test_secret_and_password_markers(self) -> None:
        assert _is_secret("MY_SECRET_VALUE") is True
        assert _is_secret("DB_PASSWORD") is True

    def test_plain_variables_are_not_secret(self) -> None:
        assert _is_secret("GMLST_CACHE_DIR") is False
        assert _is_secret("GMLST_PRIVATE_BIGSDB_URL") is False

    def test_matching_is_case_insensitive(self) -> None:
        assert _is_secret("provider_api_key") is True


class TestMaskSecret:
    def test_short_value_fully_masked(self) -> None:
        assert _mask_secret("abc123") == "********"
        assert _mask_secret("") == "********"

    def test_long_value_partially_masked(self) -> None:
        assert _mask_secret("sk-pubmlst-abcdef1234567890") == "sk-p****7890"


class TestConfigShowMasking:
    def test_secret_value_masked_in_show(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_key = "sk-pubmlst-abcdef1234567890"
        monkeypatch.setenv("GMLST_PUBMLST_API_KEY", fake_key)

        runner = CliRunner()
        result = runner.invoke(config_group, ["show"])

        assert result.exit_code == 0
        assert fake_key not in result.output
        assert "sk-p****7890" in result.output
        assert "Secret values are masked" in result.output

    def test_short_secret_fully_masked_in_show(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENTEROBASE_TOKEN", "tok123")

        runner = CliRunner()
        result = runner.invoke(config_group, ["show"])

        assert result.exit_code == 0
        assert "tok123" not in result.output
        assert "********" in result.output

    def test_non_secret_value_shown_unmasked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GMLST_TMPDIR", "/nvme/scratch")

        runner = CliRunner()
        result = runner.invoke(config_group, ["show"])

        assert result.exit_code == 0
        assert "/nvme/scratch" in result.output

    def test_unset_secret_not_replaced_by_mask(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for entry in _CONFIG_REGISTRY:
            if _is_secret(entry.name):
                monkeypatch.delenv(entry.name, raising=False)

        runner = CliRunner()
        result = runner.invoke(config_group, ["show"])

        assert result.exit_code == 0
        assert "Secret values are masked" not in result.output

    def test_get_masks_secret_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_key = "sk-pubmlst-abcdef1234567890"
        monkeypatch.setenv("GMLST_PUBMLST_API_KEY", fake_key)

        runner = CliRunner()
        result = runner.invoke(config_group, ["get", "GMLST_PUBMLST_API_KEY"])

        assert result.exit_code == 0
        assert "sk-p****7890" in result.output
        assert fake_key not in result.output


class TestConfigGetJson:
    def test_env_set_var_reports_env_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GMLST_TMPDIR", "/scratch/env-value")

        runner = CliRunner()
        result = runner.invoke(
            config_group, ["get", "GMLST_TMPDIR", "--format", "json"]
        )

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert doc["schema_version"] == "gmlst-config-get-v1"
        assert doc["data"] == {
            "name": "GMLST_TMPDIR",
            "value": "/scratch/env-value",
            "source": "env",
            "is_default": False,
            "is_masked": False,
        }

    def test_file_match_reports_file_source(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "env.sh"
        env_file.write_text('export GMLST_TMPDIR="/from/file"\n')
        monkeypatch.setattr("gmlst.commands.config._ENV_FILE_CANDIDATES", [env_file])
        monkeypatch.setenv("GMLST_TMPDIR", "/from/file")

        runner = CliRunner()
        result = runner.invoke(
            config_group, ["get", "GMLST_TMPDIR", "--format", "json"]
        )

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert doc["schema_version"] == "gmlst-config-get-v1"
        assert doc["data"] == {
            "name": "GMLST_TMPDIR",
            "value": "/from/file",
            "source": "file",
            "is_default": False,
            "is_masked": False,
        }

    def test_env_override_of_file_reports_env_source(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "env.sh"
        env_file.write_text("export GMLST_TMPDIR=/from/file\n")
        monkeypatch.setattr("gmlst.commands.config._ENV_FILE_CANDIDATES", [env_file])
        monkeypatch.setenv("GMLST_TMPDIR", "/overridden")

        runner = CliRunner()
        result = runner.invoke(
            config_group, ["get", "GMLST_TMPDIR", "--format", "json"]
        )

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert doc["data"]["source"] == "env"
        assert doc["data"]["value"] == "/overridden"

    def test_unset_var_reports_default_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GMLST_TMPDIR", raising=False)

        runner = CliRunner()
        result = runner.invoke(
            config_group, ["get", "GMLST_TMPDIR", "--format", "json"]
        )

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert doc["schema_version"] == "gmlst-config-get-v1"
        assert doc["data"] == {
            "name": "GMLST_TMPDIR",
            "value": "/tmp",
            "source": "default",
            "is_default": True,
            "is_masked": False,
        }

    def test_secret_value_masked_in_json_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_key = "sk-pubmlst-abcdef1234567890"
        monkeypatch.setenv("GMLST_PUBMLST_API_KEY", fake_key)

        runner = CliRunner()
        result = runner.invoke(
            config_group, ["get", "GMLST_PUBMLST_API_KEY", "--format", "json"]
        )

        assert result.exit_code == 0
        doc = json.loads(result.output)
        assert doc["data"]["value"] == "sk-p****7890"
        assert doc["data"]["is_masked"] is True

    def test_text_mode_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GMLST_TMPDIR", "/scratch/plain")

        runner = CliRunner()
        result = runner.invoke(config_group, ["get", "GMLST_TMPDIR"])

        assert result.exit_code == 0
        assert "/scratch/plain" in result.output
        assert "schema_version" not in result.output

    def test_unknown_variable_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(config_group, ["get", "GMLST_NOT_A_THING"])

        assert result.exit_code == 1
        assert "Unknown variable" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
