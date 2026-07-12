from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from rich.console import Console

from gmlst.cli import main
from gmlst.commands.common import _DictSchemeInfo
from gmlst.commands.scheme import _build_scheme_list_table
from gmlst.database.cache import DatabaseCache
from gmlst.database.schema import Scheme


def test_help_shows_quiet_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "--quiet" in result.output


def test_short_help_alias_root() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["-h"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_typing_help_shows_quiet_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["typing", "--help"])
    assert result.exit_code == 0
    assert "--quiet" not in result.output
    assert "--count-same-copy" not in result.output
    assert "--data-dir" not in result.output


def test_typing_help_shows_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["typing", "--help"])
    assert result.exit_code == 0
    assert "mlst" in result.output
    assert "cgmlst" in result.output
    assert "tgmlst" in result.output
    assert result.output.index("  mlst") < result.output.index("  cgmlst")
    assert result.output.index("  cgmlst") < result.output.index("  tgmlst")


def test_typing_subcommand_specific_options() -> None:
    runner = CliRunner()
    mlst_help = runner.invoke(main, ["typing", "mlst", "--help"])
    cgmlst_help = runner.invoke(main, ["typing", "cgmlst", "--help"])
    tgmlst_help = runner.invoke(main, ["typing", "tgmlst", "--help"])
    assert mlst_help.exit_code == 0
    assert cgmlst_help.exit_code == 0
    assert tgmlst_help.exit_code == 0
    assert "--stats" not in mlst_help.output
    assert "--stats" in tgmlst_help.output
    assert "--threads" in tgmlst_help.output
    assert "--provider" not in mlst_help.output
    assert "--provider" not in cgmlst_help.output
    assert "--max-workers" in mlst_help.output
    assert "--max-workers" in cgmlst_help.output
    assert "--prefilter-k" in cgmlst_help.output
    assert "--prefilter-top-n" in cgmlst_help.output
    assert "--prefilter-min-loci-fraction" in cgmlst_help.output
    assert "--no-prefilter" in cgmlst_help.output
    assert "--cds-coordinates-out" in cgmlst_help.output
    assert "--call-policy" in cgmlst_help.output
    assert "--chew-cds-gate" in cgmlst_help.output
    assert "--cgmlst-mode" in cgmlst_help.output
    assert "--prefilter-k" not in mlst_help.output
    assert "--no-prefilter" not in mlst_help.output
    assert "--schemefree-stats" not in tgmlst_help.output


def test_typing_cgmlst_prefilter_options_forwarded(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        fake_run_mlst_like_typing,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "typing",
            "cgmlst",
            "-s",
            "vparahaemolyticus_3",
            "--prefilter-k",
            "27",
            "--prefilter-top-n",
            "9",
            "--prefilter-min-loci-fraction",
            "0.6",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["prefilter_k"] == 27
    assert captured["prefilter_top_n"] == 9
    assert captured["prefilter_min_loci_fraction"] == 0.6


def test_typing_cgmlst_no_prefilter_option_forwarded(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        fake_run_mlst_like_typing,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "typing",
            "cgmlst",
            "-s",
            "vparahaemolyticus_3",
            "--no-prefilter",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["prefilter_enabled"] is False


def test_typing_cgmlst_cds_coordinates_out_forwarded(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")
    cds_out = tmp_path / "cds.tsv"

    captured: dict[str, object] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        fake_run_mlst_like_typing,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "typing",
            "cgmlst",
            "-s",
            "vparahaemolyticus_3",
            "--cds-coordinates-out",
            str(cds_out),
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["cds_coordinates_out"] == cds_out


def test_typing_cgmlst_call_policy_forwarded(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        fake_run_mlst_like_typing,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "typing",
            "cgmlst",
            "-s",
            "vparahaemolyticus_3",
            "--call-policy",
            "chewbbaca",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["call_policy"] == "chewbbaca"


def test_typing_cgmlst_chew_cds_gate_forwarded(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        fake_run_mlst_like_typing,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "typing",
            "cgmlst",
            "-s",
            "vparahaemolyticus_3",
            "--call-policy",
            "chewbbaca",
            "--no-chew-cds-gate",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["chew_cds_gate"] is False


def test_typing_cgmlst_chew_call_policy_rejects_fastq(tmp_path: Path) -> None:
    fastq = tmp_path / "sample_R1.fastq"
    fastq.write_text("@r1\nACGT\n+\n####\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "typing",
            "cgmlst",
            "-s",
            "vparahaemolyticus_3",
            "--call-policy",
            "chewbbaca",
            str(fastq),
        ],
    )

    assert result.exit_code != 0
    assert "requires FASTA assemblies" in result.output


def test_typing_cgmlst_default_backend_is_minimap2(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        fake_run_mlst_like_typing,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "typing",
            "cgmlst",
            "-s",
            "vparahaemolyticus_3",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["backend"] == "minimap2"


def test_typing_cgmlst_max_workers_option_forwarded(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        fake_run_mlst_like_typing,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "typing",
            "cgmlst",
            "-s",
            "vparahaemolyticus_3",
            "--max-workers",
            "4",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["max_workers"] == 4


def test_typing_cgmlst_mode_option_forwarded(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        fake_run_mlst_like_typing,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "typing",
            "cgmlst",
            "-s",
            "vparahaemolyticus_3",
            "--cgmlst-mode",
            "chew-balanced",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["cgmlst_mode"] == "chew-balanced"


def test_typing_backend_list_excludes_kmerhash() -> None:
    runner = CliRunner()
    mlst_help = runner.invoke(main, ["typing", "mlst", "--help"])

    assert mlst_help.exit_code == 0
    assert "kma" in mlst_help.output
    assert "kmerhash" not in mlst_help.output


def test_typing_mlst_rejects_cgmlst_scheme(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    def _fake_ensure_scheme(self, name: str, **_kwargs):
        assert name == "vp_3"
        return Scheme(
            name="vp_3", loci=["a"], allele_files={"a": sample}, profile_file=None
        )

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "vp_3", "scheme_type": "cgmlst"}]
        return []

    monkeypatch.setattr(DatabaseCache, "ensure_scheme", _fake_ensure_scheme)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)

    runner = CliRunner()
    result = runner.invoke(main, ["typing", "mlst", "-s", "vp_3", str(sample)])
    assert result.exit_code != 0
    assert "Use gmlst typing cgmlst" in result.output


def test_legacy_typing_schemefree_still_routes(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    called = {"value": False}

    def _fake_schemefree(**_kwargs):
        called["value"] = True
        return 0

    monkeypatch.setattr(
        "gmlst.commands.typing._run_schemefree_typing", _fake_schemefree
    )

    runner = CliRunner()
    result = runner.invoke(main, ["typing", "-s", "schemefree", str(sample)])
    assert result.exit_code == 0
    assert called["value"] is True


def test_typing_tgmlst_threads_option_passes_to_schemefree(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    def _fake_schemefree(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(
        "gmlst.commands.typing._run_schemefree_typing", _fake_schemefree
    )

    runner = CliRunner()
    result = runner.invoke(main, ["typing", "tgmlst", "--threads", "4", str(sample)])

    assert result.exit_code == 0
    assert captured["threads"] == 4


def test_run_schemefree_typing_threads_drive_default_max_workers(
    monkeypatch, tmp_path: Path
) -> None:
    from gmlst.commands import typing as typing_cmd

    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    class _FakeTyper:
        def __init__(self, config):
            captured["config"] = config
            self.last_run_errors = []
            self.last_run_stats = {}

        def load_scheme(self, _path):
            return None

        def type_sample_files(self, _samples):
            return []

        def export_scheme(self, _path):
            return None

    monkeypatch.setattr(typing_cmd, "SchemeFreeTyper", _FakeTyper)
    monkeypatch.setattr(typing_cmd, "profiles_to_tsv", lambda *_args, **_kwargs: "")

    exit_code = typing_cmd._run_schemefree_typing(
        samples=[sample],
        hash_strategy="safe",
        fmt="tsv",
        output=None,
        no_header=False,
        save_scheme_path=None,
        load_scheme_path=None,
        show_stats=False,
        max_workers=None,
        threads=16,
        assemble_timeout=None,
        error_report_path=None,
        fail_on_error=False,
        summary_report_path=None,
    )

    assert exit_code == 0
    config = captured["config"]
    assert isinstance(config, typing_cmd.SchemaFreeConfig)
    assert config.assembly.max_parallel_samples == 16
    assert config.clustering.threads == "16"


def test_run_schemefree_typing_max_workers_overrides_threads_worker_count(
    monkeypatch, tmp_path: Path
) -> None:
    from gmlst.commands import typing as typing_cmd

    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    class _FakeTyper:
        def __init__(self, config):
            captured["config"] = config
            self.last_run_errors = []
            self.last_run_stats = {}

        def load_scheme(self, _path):
            return None

        def type_sample_files(self, _samples):
            return []

        def export_scheme(self, _path):
            return None

    monkeypatch.setattr(typing_cmd, "SchemeFreeTyper", _FakeTyper)
    monkeypatch.setattr(typing_cmd, "profiles_to_tsv", lambda *_args, **_kwargs: "")

    exit_code = typing_cmd._run_schemefree_typing(
        samples=[sample],
        hash_strategy="safe",
        fmt="tsv",
        output=None,
        no_header=False,
        save_scheme_path=None,
        load_scheme_path=None,
        show_stats=False,
        max_workers=2,
        threads=16,
        assemble_timeout=None,
        error_report_path=None,
        fail_on_error=False,
        summary_report_path=None,
    )

    assert exit_code == 0
    config = captured["config"]
    assert isinstance(config, typing_cmd.SchemaFreeConfig)
    assert config.assembly.max_parallel_samples == 2
    assert config.clustering.threads == "16"


def test_short_help_alias_typing() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["typing", "-h"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_scheme_download_help_shows_quiet_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "download", "--help"])
    assert result.exit_code == 0
    assert "--quiet" in result.output
    assert "--download-tool" in result.output
    assert "--connections" in result.output


def test_scheme_download_forwards_download_tool(monkeypatch) -> None:
    runner = CliRunner()
    captured: dict[str, object] = {}

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "ecoli_1", "scheme_type": "mlst"}]
        return []

    def _fake_ensure_scheme(self, name: str, **kwargs):
        captured["name"] = name
        captured.update(kwargs)
        return None

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "ensure_scheme", _fake_ensure_scheme)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        DatabaseCache,
        "scheme_dir",
        lambda *args, **kwargs: Path("/tmp/pubmlst/ecoli_1"),
    )

    result = runner.invoke(
        main,
        ["scheme", "download", "-s", "ecoli_1", "--download-tool", "wget"],
    )

    assert result.exit_code == 0
    assert captured["name"] == "ecoli_1"
    assert captured["provider"] == "pubmlst"
    assert captured["scheme_type"] == "mlst"
    assert captured["download_tool"] == "wget"
    assert captured["max_connections"] == 4


def test_scheme_download_forwards_connections(monkeypatch) -> None:
    runner = CliRunner()
    captured: dict[str, object] = {}

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "ecoli_1", "scheme_type": "mlst"}]
        return []

    def _fake_ensure_scheme(self, name: str, **kwargs):
        captured["name"] = name
        captured.update(kwargs)
        return None

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "ensure_scheme", _fake_ensure_scheme)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        DatabaseCache,
        "scheme_dir",
        lambda *args, **kwargs: Path("/tmp/pubmlst/ecoli_1"),
    )

    result = runner.invoke(
        main,
        [
            "scheme",
            "download",
            "-s",
            "ecoli_1",
            "--download-tool",
            "aria2c",
            "-x",
            "12",
        ],
    )

    assert result.exit_code == 0
    assert captured["name"] == "ecoli_1"
    assert captured["download_tool"] == "aria2c"
    assert captured["max_connections"] == 12


def test_scheme_download_rejects_blocked_scheme(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "salmonella_1", "scheme_type": "cgmlst"}]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)

    result = runner.invoke(main, ["scheme", "download", "-s", "salmonella_1"])

    assert result.exit_code != 0
    assert "is blocked for provider 'pubmlst'" in result.output


def test_scheme_download_rejects_senterica_5_blocked_scheme(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "senterica_5", "scheme_type": "cgmlst"}]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)

    result = runner.invoke(main, ["scheme", "download", "-s", "senterica_5"])

    assert result.exit_code != 0
    assert "is blocked for provider 'pubmlst'" in result.output


def test_scheme_show_rejects_blocked_scheme(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "salmonella_1", "scheme_type": "cgmlst"}]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)

    result = runner.invoke(main, ["scheme", "show", "-s", "salmonella_1"])

    assert result.exit_code != 0
    assert "is blocked for provider 'pubmlst'" in result.output


def test_scheme_update_rejects_blocked_scheme(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "salmonella_1", "scheme_type": "cgmlst"}]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)

    result = runner.invoke(main, ["scheme", "update", "-s", "salmonella_1"])

    assert result.exit_code != 0
    assert "is blocked for provider 'pubmlst'" in result.output


def test_scheme_list_help_shows_format_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "list", "--help"])
    assert result.exit_code == 0
    assert "--format" in result.output
    assert "text|table|csv|tsv|json" in result.output


def test_scheme_show_help_shows_format_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "show", "--help"])
    assert result.exit_code == 0
    assert "--format" in result.output
    assert "text|table|csv|tsv|json" in result.output


def test_scheme_update_help_shows_force_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "update", "--help"])
    assert result.exit_code == 0
    assert "--force" in result.output
    assert "--download-tool" in result.output
    assert "--connections" in result.output


def test_short_help_alias_scheme_group() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "-h"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "cgMLST" in result.output
    assert "wgMLST" in result.output


def test_short_help_alias_utils_group() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["utils", "-h"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_benchmark_moved_under_utils() -> None:
    runner = CliRunner()
    root_help = runner.invoke(main, ["--help"])
    utils_help = runner.invoke(main, ["utils", "--help"])
    benchmark_help = runner.invoke(main, ["utils", "benchmark", "--help"])

    assert root_help.exit_code == 0
    assert utils_help.exit_code == 0
    assert benchmark_help.exit_code == 0
    assert "  benchmark" not in root_help.output
    assert "benchmark" in utils_help.output
    assert "Benchmark multiple alignment backends" in benchmark_help.output


def test_scheme_create_help_shows_data_dir() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "create", "--help"])
    assert result.exit_code == 0
    assert "--data-dir" in result.output


def test_no_args_shows_root_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code in (0, 2)
    assert "Usage:" in result.output
    assert "Missing" not in result.output


def test_no_args_shows_subcommand_help() -> None:
    runner = CliRunner()
    result_scheme = runner.invoke(main, ["scheme"])
    result_utils = runner.invoke(main, ["utils"])
    result_typing = runner.invoke(main, ["typing"])
    assert result_scheme.exit_code in (0, 2)
    assert result_utils.exit_code in (0, 2)
    assert result_typing.exit_code in (0, 2)
    assert "Usage:" in result_scheme.output
    assert "Usage:" in result_utils.output
    assert "Usage:" in result_typing.output
    assert "Missing" not in result_scheme.output
    assert "Missing" not in result_utils.output
    assert "Missing" not in result_typing.output


def test_verbose_and_quiet_are_mutually_exclusive() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--verbose", "--quiet", "scheme", "--help"])
    assert result.exit_code != 0
    assert "cannot be used together" in result.output


def test_scheme_update_uses_catalog_scheme_type(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "vparahaemolyticus_3",
                    "scheme_type": "cgmlst",
                }
            ]
        return []

    def _fake_update_scheme(
        self,
        name: str,
        *,
        provider: str = "pubmlst",
        scheme_type: str = "mlst",
        token: str | None = None,
        download_tool: str = "auto",
        max_connections: int | None = None,
    ):
        captured["name"] = name
        captured["provider"] = provider
        captured["scheme_type"] = scheme_type
        captured["download_tool"] = download_tool
        captured["max_connections"] = max_connections
        return (object(), False)

    def _fake_scheme_dir(self, name: str, provider: str = "pubmlst"):
        return f"/tmp/{provider}/{name}"

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "update_scheme", _fake_update_scheme)
    monkeypatch.setattr(DatabaseCache, "scheme_dir", _fake_scheme_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "update", "-s", "vparahaemolyticus_3"])

    assert result.exit_code == 0
    assert captured["name"] == "vparahaemolyticus_3"
    assert captured["provider"] == "pubmlst"
    assert captured["scheme_type"] == "cgmlst"
    assert captured["download_tool"] == "auto"
    assert captured["max_connections"] == 4


def test_scheme_update_forwards_download_tool(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "ecoli_1", "scheme_type": "mlst"}]
        return []

    def _fake_update_scheme(
        self,
        name: str,
        *,
        provider: str = "pubmlst",
        scheme_type: str = "mlst",
        token: str | None = None,
        download_tool: str = "auto",
        max_connections: int | None = None,
    ):
        captured["name"] = name
        captured["download_tool"] = download_tool
        captured["max_connections"] = max_connections
        return (object(), True)

    def _fake_scheme_dir(self, name: str, provider: str = "pubmlst"):
        return f"/tmp/{provider}/{name}"

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "update_scheme", _fake_update_scheme)
    monkeypatch.setattr(DatabaseCache, "scheme_dir", _fake_scheme_dir)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["scheme", "update", "-s", "ecoli_1", "--download-tool", "aria2c"],
    )

    assert result.exit_code == 0
    assert captured["name"] == "ecoli_1"
    assert captured["download_tool"] == "aria2c"
    assert captured["max_connections"] == 4


def test_scheme_update_forwards_connections(monkeypatch) -> None:
    captured: dict[str, str | int | None] = {}

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "ecoli_1", "scheme_type": "mlst"}]
        return []

    def _fake_update_scheme(
        self,
        name: str,
        *,
        provider: str = "pubmlst",
        scheme_type: str = "mlst",
        token: str | None = None,
        download_tool: str = "auto",
        max_connections: int | None = None,
    ):
        captured["name"] = name
        captured["download_tool"] = download_tool
        captured["max_connections"] = max_connections
        return (object(), True)

    def _fake_scheme_dir(self, name: str, provider: str = "pubmlst"):
        return f"/tmp/{provider}/{name}"

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "update_scheme", _fake_update_scheme)
    monkeypatch.setattr(DatabaseCache, "scheme_dir", _fake_scheme_dir)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "scheme",
            "update",
            "-s",
            "ecoli_1",
            "--download-tool",
            "aria2c",
            "-x",
            "10",
        ],
    )

    assert result.exit_code == 0
    assert captured["name"] == "ecoli_1"
    assert captured["download_tool"] == "aria2c"
    assert captured["max_connections"] == 10


def test_scheme_update_all_updates_cached_schemes(monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    def _fake_list_cached(self):
        return [
            {"scheme": "ecoli_1", "provider": "pubmlst", "scheme_type": "mlst"},
            {"scheme": "senterica", "provider": "cgmlst", "scheme_type": "cgmlst"},
        ]

    def _fake_update_scheme(
        self,
        name: str,
        *,
        provider: str = "pubmlst",
        scheme_type: str = "mlst",
        token: str | None = None,
        download_tool: str = "auto",
        max_connections: int | None = None,
    ):
        captured.append(
            {
                "name": name,
                "provider": provider,
                "scheme_type": scheme_type,
                "download_tool": download_tool,
                "max_connections": max_connections,
            }
        )
        return (object(), name == "ecoli_1")

    monkeypatch.setattr(DatabaseCache, "list_cached", _fake_list_cached)
    monkeypatch.setattr(DatabaseCache, "update_scheme", _fake_update_scheme)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["scheme", "update", "-a", "--download-tool", "aria2c", "-x", "10"],
    )

    assert result.exit_code == 0
    assert captured == [
        {
            "name": "ecoli_1",
            "provider": "pubmlst",
            "scheme_type": "mlst",
            "download_tool": "aria2c",
            "max_connections": 10,
        },
        {
            "name": "senterica",
            "provider": "cgmlst",
            "scheme_type": "cgmlst",
            "download_tool": "aria2c",
            "max_connections": 10,
        },
    ]
    assert "Updating 2 cached scheme database" in result.output
    assert "Updated: 1; unchanged: 1; failed: 0" in result.output


def test_scheme_update_all_reports_empty_cache(monkeypatch) -> None:
    monkeypatch.setattr(DatabaseCache, "list_cached", lambda self: [])

    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "update", "-a"])

    assert result.exit_code == 0
    assert "No cached schemes found" in result.output


def test_scheme_update_rejects_scheme_with_all() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scheme", "update", "-s", "ecoli_1", "-a"])

    assert result.exit_code == 1
    assert "Use either --scheme or --all" in result.output


def test_scheme_list_json_output(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                    "display_name": "Achtman",
                    "extra": {},
                }
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: True)

    result = runner.invoke(main, ["scheme", "list", "-p", "pubmlst", "-f", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert payload[0]["scheme_name"] == "ecoli_1"
    assert payload[0]["downloaded"] is True


def test_scheme_list_filters_default_blocked_schemes(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "salmonella_1",
                    "organism": "Salmonella spp.",
                    "scheme_type": "cgmlst",
                    "n_loci": 3002,
                    "provider": "pubmlst",
                    "display_name": "Salmonella spp. cgMLST v2 (Enterobase)",
                    "extra": {},
                },
                {
                    "scheme_name": "senterica_5",
                    "organism": "Salmonella enterica",
                    "scheme_type": "cgmlst",
                    "n_loci": 3002,
                    "provider": "pubmlst",
                    "display_name": "Salmonella enterica cgMLST v2 (Enterobase)",
                    "extra": {},
                },
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                    "display_name": "Achtman",
                    "extra": {},
                },
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(main, ["scheme", "list", "-p", "pubmlst", "-f", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    scheme_names = [row["scheme_name"] for row in payload]
    assert "salmonella_1" not in scheme_names
    assert "senterica_5" not in scheme_names
    assert "ecoli_1" in scheme_names


def test_scheme_list_tsv_output(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                    "display_name": "Achtman",
                    "extra": {},
                }
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: True)

    result = runner.invoke(main, ["scheme", "list", "-p", "pubmlst", "-f", "tsv"])

    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    expected_header = (
        "downloaded\tscheme_name\torganism\tscheme_type\tn_loci\tprovider\tdisplay_name"
    )
    assert lines[0] == expected_header
    assert lines[1] == "1\tecoli_1\tEscherichia coli\tmlst\t7\tpubmlst\tAchtman"


def test_scheme_list_csv_output(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                    "display_name": "Achtman",
                    "extra": {},
                }
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(main, ["scheme", "list", "-p", "pubmlst", "-f", "csv"])

    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert (
        lines[0]
        == "downloaded,scheme_name,organism,scheme_type,n_loci,provider,display_name"
    )
    assert lines[1] == "0,ecoli_1,Escherichia coli,mlst,7,pubmlst,Achtman"


def test_scheme_list_text_output(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                    "display_name": "Achtman",
                    "extra": {},
                }
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: True)

    result = runner.invoke(main, ["scheme", "list", "-p", "pubmlst", "-f", "text"])

    assert result.exit_code == 0
    assert (
        "ecoli_1 | Escherichia coli | mlst | loci=7 | pubmlst | downloaded"
        in result.output
    )


def _sample_scheme_info() -> list[_DictSchemeInfo]:
    return [
        _DictSchemeInfo(
            {
                "scheme_name": "very_long_ecoli_scheme_name_123",
                "organism": "Escherichia coli with a deliberately long label",
                "scheme_type": "mlst",
                "n_loci": 7,
                "provider": "pubmlst",
                "display_name": "Achtman scheme with detailed description",
                "extra": {"auth_required": True},
            }
        )
    ]


def _scheme_list_headers(terminal_width: int, cache_dir: Path) -> list[str]:
    table = _build_scheme_list_table(
        _sample_scheme_info(),
        DatabaseCache(cache_dir),
        "Available Schemes",
        terminal_width,
    )
    return [str(column.header) for column in table.columns]


def test_scheme_list_table_uses_compact_columns_for_narrow_terminals(
    tmp_path: Path,
) -> None:
    assert _scheme_list_headers(79, tmp_path) == [
        "Status",
        "Scheme",
        "Type",
        "Loci",
        "Provider",
    ]


def test_scheme_list_table_adds_description_at_medium_width(tmp_path: Path) -> None:
    assert _scheme_list_headers(80, tmp_path) == [
        "Status",
        "Scheme",
        "Type",
        "Loci",
        "Provider",
        "Description",
    ]


def test_scheme_list_table_adds_organism_at_wide_width(tmp_path: Path) -> None:
    assert _scheme_list_headers(100, tmp_path) == [
        "Status",
        "Scheme",
        "Organism",
        "Type",
        "Loci",
        "Provider",
        "Description",
    ]


def test_scheme_list_table_renders_within_narrow_terminal_width(
    tmp_path: Path,
) -> None:
    terminal_width = 60
    table = _build_scheme_list_table(
        _sample_scheme_info(),
        DatabaseCache(tmp_path),
        "Available Schemes",
        terminal_width,
    )
    render_console = Console(width=terminal_width, record=True)

    render_console.print(table)

    rendered = render_console.export_text()
    assert rendered
    assert all(len(line) <= terminal_width for line in rendered.splitlines())


def test_scheme_show_no_scheme_guides_and_lists(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                    "display_name": "Achtman",
                    "extra": {},
                }
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(main, ["scheme", "show"])
    assert result.exit_code == 0
    assert "No scheme specified" in result.output
    assert "Available Schemes" in result.output


def test_scheme_show_json_output(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                    "display_name": "Achtman",
                    "extra": {},
                }
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        DatabaseCache, "scheme_dir", lambda *args, **kwargs: "/tmp/pubmlst/ecoli_1"
    )
    monkeypatch.setattr(
        DatabaseCache,
        "get_scheme_metadata",
        lambda *args, **kwargs: {
            "downloaded_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        },
    )
    profile_file = tmp_path / "ecoli_1.txt"
    profile_file.write_text("ST\tarcC\n1\t1\n2\t2\n3\t3\n")
    monkeypatch.setattr(
        DatabaseCache,
        "load_scheme",
        lambda *args, **kwargs: Scheme(
            name="ecoli_1",
            loci=["arcC"],
            allele_files={"arcC": tmp_path / "arcC.tfa"},
            profile_file=profile_file,
        ),
    )

    result = runner.invoke(main, ["scheme", "show", "-s", "ecoli_1", "-f", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["scheme_name"] == "ecoli_1"
    assert payload["downloaded"] is True
    assert payload["scheme_dir"] == "/tmp/pubmlst/ecoli_1"
    assert payload["downloaded_at"] == "2026-01-01T00:00:00Z"
    assert payload["updated_at"] == "2026-01-02T00:00:00Z"
    assert payload["n_profiles"] == 3


def test_scheme_show_tsv_output(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                    "display_name": "Achtman",
                    "extra": {},
                }
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        DatabaseCache, "scheme_dir", lambda *args, **kwargs: "/tmp/pubmlst/ecoli_1"
    )
    monkeypatch.setattr(
        DatabaseCache,
        "get_scheme_metadata",
        lambda *args, **kwargs: {
            "downloaded_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        },
    )
    profile_file = tmp_path / "ecoli_1.txt"
    profile_file.write_text("ST\tarcC\n1\t1\n2\t2\n3\t3\n")
    monkeypatch.setattr(
        DatabaseCache,
        "load_scheme",
        lambda *args, **kwargs: Scheme(
            name="ecoli_1",
            loci=["arcC"],
            allele_files={"arcC": tmp_path / "arcC.tfa"},
            profile_file=profile_file,
        ),
    )

    result = runner.invoke(main, ["scheme", "show", "-s", "ecoli_1", "-f", "tsv"])

    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    expected_header = (
        "scheme_name\torganism\tscheme_type\tn_loci\tn_profiles\tprovider\t"
        "display_name\tdownloaded\tscheme_dir\tdownloaded_at\tupdated_at"
    )
    assert lines[0] == expected_header
    expected_row = (
        "ecoli_1\tEscherichia coli\tmlst\t7\t3\tpubmlst\tAchtman\t1\t"
        "/tmp/pubmlst/ecoli_1\t2026-01-01T00:00:00Z\t2026-01-02T00:00:00Z"
    )
    assert lines[1] == expected_row


def test_scheme_show_text_output(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                    "display_name": "Achtman",
                    "extra": {},
                }
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        DatabaseCache, "get_scheme_metadata", lambda *args, **kwargs: {}
    )

    result = runner.invoke(main, ["scheme", "show", "-s", "ecoli_1", "-f", "text"])

    assert result.exit_code == 0
    assert "Achtman" in result.output
    assert "Name: ecoli_1" in result.output
    assert "Status: Not downloaded" in result.output
