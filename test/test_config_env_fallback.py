"""Tests for env.sh fallback loading (config file values reach the CLI)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

import gmlst.commands.config as config_mod
from gmlst.commands.config import load_env_file_into_environ


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "env.sh"
    monkeypatch.setattr(config_mod, "_ENV_FILE_CANDIDATES", [path])
    return path


def test_file_value_reaches_environment(env_file: Path) -> None:
    env_file.write_text('export GMLST_PUBMLST_API_KEY="test-key-1234567890"\n')
    import os

    monkeypatch_os = pytest.MonkeyPatch()
    monkeypatch_os.delenv("GMLST_PUBMLST_API_KEY", raising=False)
    try:
        injected = load_env_file_into_environ()
        assert injected == {"GMLST_PUBMLST_API_KEY": "test-key-1234567890"}
        assert os.environ["GMLST_PUBMLST_API_KEY"] == "test-key-1234567890"
    finally:
        monkeypatch_os.undo()


def test_existing_environment_wins_over_file(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file.write_text('export GMLST_TMPDIR="/from-file"\n')
    monkeypatch.setenv("GMLST_TMPDIR", "/from-env")

    injected = load_env_file_into_environ()

    assert injected == {}
    import os

    assert os.environ["GMLST_TMPDIR"] == "/from-env"


def test_missing_file_is_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod, "_ENV_FILE_CANDIDATES", [tmp_path / "absent.sh"])

    assert load_env_file_into_environ() == {}


def test_config_get_reports_file_source_after_injection(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file.write_text('export GMLST_PUBMLST_API_KEY="test-key-1234567890"\n')
    monkeypatch.delenv("GMLST_PUBMLST_API_KEY", raising=False)
    load_env_file_into_environ()

    from gmlst.cli import main

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

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["data"]
    assert payload["value"] == "test-key-1234567890"
    assert payload["source"] == "file"
    assert payload["is_default"] is False


def test_provider_auth_uses_file_value(env_file: Path) -> None:
    env_file.write_text('export GMLST_PUBMLST_API_KEY="test-key-1234567890"\n')

    mp = pytest.MonkeyPatch()
    mp.delenv("GMLST_PUBMLST_API_KEY", raising=False)
    try:
        load_env_file_into_environ()
        from gmlst.database.providers.bigsdb import BigSdbProvider

        provider = BigSdbProvider(
            name="pubmlst",
            base_url="https://rest.pubmlst.org/db",
            label="PubMLST",
        )
        assert provider._auth_headers() == {"X-API-Key": "test-key-1234567890"}
    finally:
        mp.undo()
