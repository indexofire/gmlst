"""CLI exit-code semantics for AI-agent branching.

* ``scheme list --name <bad-regex>`` must fail with click's usage-error
  exit code 2 (``click.UsageError``), not exit 0 after printing an error.
* ``scheme update`` with no scheme and no ``--all`` must exit 1 when any
  provider catalog refresh fails, after printing the summary line.
* ``typing tgmlst --stats`` must keep stdout a single parseable JSON
  document by emitting stats JSON to stderr.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gmlst.cli import main
from gmlst.database.cache import DatabaseCache


def _fake_empty_catalog(self, provider: str):
    return []


def test_scheme_list_invalid_regex_reports_usage_error(monkeypatch) -> None:
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_empty_catalog)

    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "list", "-p", "pubmlst", "-n", "["])

    assert result.exit_code == 2
    assert "Error: Invalid regex pattern" in result.stderr
    assert "Traceback" not in result.output


def test_scheme_list_valid_regex_still_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_empty_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *a, **k: False)

    runner = CliRunner()
    result = runner.invoke(
        main, ["scheme", "list", "-p", "pubmlst", "-n", "^E\\. coli$", "-f", "json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {"schema_version": "gmlst-scheme-list-v1", "data": []}


def test_scheme_update_catalogs_all_providers_fail_exits_nonzero(
    monkeypatch, tmp_path: Path
) -> None:
    def _boom(self, provider: str, scheme_type: str = "all", token: str | None = None):
        raise RuntimeError(f"{provider} unreachable")

    monkeypatch.setattr(DatabaseCache, "update_catalog", _boom)

    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "update", "--cache-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "Done." in result.stdout
    assert "Total: 0 schemes" in result.stdout


def test_scheme_update_catalogs_partial_failure_exits_nonzero(
    monkeypatch, tmp_path: Path
) -> None:
    def _flaky(self, provider: str, scheme_type: str = "all", token: str | None = None):
        if provider == "pubmlst":
            raise RuntimeError("pubmlst unreachable")
        return [{"scheme_name": "demo_1"}]

    monkeypatch.setattr(DatabaseCache, "update_catalog", _flaky)

    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "update", "--cache-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "Done." in result.stdout


def test_scheme_update_catalogs_success_exits_zero(monkeypatch, tmp_path: Path) -> None:
    refreshed: list[str] = []

    def _ok(self, provider: str, scheme_type: str = "all", token: str | None = None):
        refreshed.append(provider)
        return [{"scheme_name": "demo_1"}]

    monkeypatch.setattr(DatabaseCache, "update_catalog", _ok)

    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "update", "--cache-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert refreshed
    assert "Done." in result.stdout
    assert "Total: 0 schemes" not in result.stdout


def test_typing_tgmlst_stats_goes_to_stderr_not_stdout(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    class _FakeTyper:
        def __init__(self, config):
            self.last_run_errors = []
            self.last_run_stats = {"samples_total": 1, "samples_succeeded": 1}

        def load_scheme(self, _path):
            return None

        def type_sample_files(self, _samples):
            return []

        def export_scheme(self, _path):
            return None

    monkeypatch.setattr("gmlst.commands.typing.SchemeFreeTyper", _FakeTyper)
    monkeypatch.setattr("gmlst.commands.typing.profiles_to_json", lambda _p: "[]")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["typing", "tgmlst", str(sample), "--format", "json", "--stats"],
    )

    assert result.exit_code == 0
    stdout_payload = json.loads(result.stdout)
    assert stdout_payload == {"schema_version": "gmlst-tgmlst-profiles-v1", "data": []}
    stats = json.loads(result.stderr[result.stderr.index("{") :])
    assert stats["schema_version"] == "gmlst-tgmlst-stats-v1"
    assert stats["data"]["samples_total"] == 1
