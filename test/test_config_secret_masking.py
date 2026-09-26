"""Tests for secret masking in config get/set (layers 1-2 of leak prevention)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

import gmlst.commands.config as config_mod
from gmlst.cli import main

_SECRET = "test-key-1234567890abcdef"


@pytest.fixture
def secret_in_env(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("GMLST_PUBMLST_API_KEY", _SECRET)
    return _SECRET


def _masked(value: str) -> str:
    return f"{value[:4]}****{value[-4:]}"


# ---------------------------------------------------------------------------
# layer 1: config get masks by default, --reveal opts in
# ---------------------------------------------------------------------------


def test_get_text_masks_secret_by_default(secret_in_env: str) -> None:
    result = CliRunner().invoke(main, ["config", "get", "GMLST_PUBMLST_API_KEY"])

    assert result.exit_code == 0
    assert _masked(_SECRET) in result.output
    assert _SECRET not in result.output


def test_get_text_reveal_outputs_plaintext(secret_in_env: str) -> None:
    result = CliRunner().invoke(
        main, ["config", "get", "GMLST_PUBMLST_API_KEY", "--reveal"]
    )

    assert result.exit_code == 0
    assert _SECRET in result.output


def test_get_json_masks_secret_by_default(secret_in_env: str) -> None:
    result = CliRunner().invoke(
        main, ["config", "get", "GMLST_PUBMLST_API_KEY", "--format", "json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)["data"]
    assert payload["value"] == _masked(_SECRET)
    assert payload["is_masked"] is True
    assert _SECRET not in result.output


def test_get_json_reveal_outputs_plaintext(secret_in_env: str) -> None:
    result = CliRunner().invoke(
        main,
        [
            "config",
            "get",
            "GMLST_PUBMLST_API_KEY",
            "--format",
            "json",
            "--reveal",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)["data"]
    assert payload["value"] == _SECRET
    assert payload["is_masked"] is False


def test_get_non_secret_stays_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMLST_TMPDIR", "/data/tmp")

    result = CliRunner().invoke(main, ["config", "get", "GMLST_TMPDIR"])

    assert result.exit_code == 0
    assert "/data/tmp" in result.output


# ---------------------------------------------------------------------------
# layer 2: config set never echoes secret plaintext, hidden input prompt
# ---------------------------------------------------------------------------


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "env.sh"
    monkeypatch.setattr(config_mod, "_ENV_FILE_CANDIDATES", [path])
    return path


def test_set_cli_arg_echoes_mask_not_plaintext(env_file: Path) -> None:
    result = CliRunner().invoke(
        main, ["config", "set", "GMLST_PUBMLST_API_KEY", _SECRET]
    )

    assert result.exit_code == 0, result.output
    assert _SECRET not in result.output
    assert _masked(_SECRET) in result.output
    written = env_file.read_text()
    assert _SECRET in written  # file itself still holds the real value


def test_set_without_value_prompts_hidden_and_confirms(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GMLST_PUBMLST_API_KEY", raising=False)

    result = CliRunner().invoke(
        main,
        ["config", "set", "GMLST_PUBMLST_API_KEY"],
        input=f"{_SECRET}\n{_SECRET}\n",
    )

    assert result.exit_code == 0, result.output
    assert _SECRET not in result.output  # hidden input + masked echo
    assert _masked(_SECRET) in result.output
    assert f"export GMLST_PUBMLST_API_KEY={_SECRET}" in env_file.read_text()


def test_set_non_secret_prompts_visibly(env_file: Path) -> None:
    result = CliRunner().invoke(
        main, ["config", "set", "GMLST_TMPDIR"], input="/data/scratch\n"
    )

    assert result.exit_code == 0, result.output
    assert "export GMLST_TMPDIR=/data/scratch" in env_file.read_text()
    assert "/data/scratch" in result.output
