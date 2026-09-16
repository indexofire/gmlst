from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from rich.console import Console

from gmlst.cli import main
from gmlst.commands.scheme import _build_scheme_list_table
from gmlst.database.cache import DatabaseCache
from gmlst.database.providers.base import SchemeInfo
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
    assert result.output.index("  cgmlst") < result.output.index("  mlst")
    assert result.output.index("  mlst") < result.output.index("  tgmlst")


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
            "balanced",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["cgmlst_mode"] == "balanced"


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
        ["scheme", "update", "-a", "-y", "--download-tool", "aria2c", "-x", "10"],
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
    assert payload["schema_version"] == "gmlst-scheme-list-v1"
    data = payload["data"]
    assert isinstance(data, list)
    assert data[0]["scheme_name"] == "ecoli_1"
    assert data[0]["downloaded"] is True


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
    scheme_names = [row["scheme_name"] for row in payload["data"]]
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


def _sample_scheme_info() -> list[SchemeInfo]:
    return [
        SchemeInfo(
            scheme_name="very_long_ecoli_scheme_name_123",
            organism="Escherichia coli with a deliberately long label",
            scheme_type="mlst",
            n_loci=7,
            provider="pubmlst",
            display_name="Achtman scheme with detailed description",
            extra={"auth_required": True},
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
    assert payload["schema_version"] == "gmlst-scheme-show-v1"
    data = payload["data"]
    assert data["scheme_name"] == "ecoli_1"
    assert data["downloaded"] is True
    assert data["n_profiles"] == 3
    # JSON strips machine-specific / time-varying fields for determinism.
    assert "scheme_dir" not in data
    assert "downloaded_at" not in data
    assert "updated_at" not in data


def test_scheme_show_json_output_is_deterministic(monkeypatch, tmp_path: Path) -> None:
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

    profile_file = tmp_path / "ecoli_1.txt"
    profile_file.write_text("ST\tarcC\n1\t1\n2\t2\n3\t3\n")

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        DatabaseCache,
        "scheme_dir",
        lambda *args, **kwargs: "/tmp/pubmlst/ecoli_1",
    )
    monkeypatch.setattr(
        DatabaseCache,
        "get_scheme_metadata",
        lambda *args, **kwargs: {
            "downloaded_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        },
    )
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

    first = runner.invoke(main, ["scheme", "show", "-s", "ecoli_1", "-f", "json"])
    second = runner.invoke(main, ["scheme", "show", "-s", "ecoli_1", "-f", "json"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert first.output == second.output


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


def _parse_trailing_json(output: str) -> dict:
    """Parse the JSON document at the end of mixed prose + JSON output."""
    return json.loads(output[output.index("{") :])


def _search_catalog(self, provider: str):
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
            },
            {
                "scheme_name": "ecoli_2",
                "organism": "Escherichia coli #2",
                "scheme_type": "cgmlst",
                "n_loci": 2512,
                "provider": "pubmlst",
                "display_name": "EcOH2",
                "extra": {},
            },
            {
                "scheme_name": "saureus_1",
                "organism": "Staphylococcus aureus",
                "scheme_type": "mlst",
                "n_loci": 7,
                "provider": "pubmlst",
                "display_name": "Ridom",
                "extra": {},
            },
        ]
    return []


def test_scheme_search_json_output(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(DatabaseCache, "load_catalog", _search_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: True)

    result = runner.invoke(main, ["scheme", "search", "ecoli", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "gmlst-scheme-list-v1"
    data = payload["data"]
    assert isinstance(data, list)
    assert [row["scheme_name"] for row in data] == ["ecoli_1", "ecoli_2"]
    first = data[0]
    assert set(first) == {
        "scheme_name",
        "organism",
        "scheme_type",
        "n_loci",
        "provider",
        "display_name",
        "extra",
        "downloaded",
    }
    assert first["organism"] == "Escherichia coli"
    assert first["scheme_type"] == "mlst"
    assert first["n_loci"] == 7
    assert first["provider"] == "pubmlst"
    assert first["downloaded"] is True


def test_scheme_search_tsv_output(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(DatabaseCache, "load_catalog", _search_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(main, ["scheme", "search", "ecoli", "-f", "tsv"])

    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    expected_header = (
        "downloaded\tscheme_name\torganism\tscheme_type\tn_loci\tprovider\tdisplay_name"
    )
    assert lines[0] == expected_header
    assert lines[1] == "0\tecoli_1\tEscherichia coli\tmlst\t7\tpubmlst\tAchtman"
    assert lines[2] == "0\tecoli_2\tEscherichia coli #2\tcgmlst\t2512\tpubmlst\tEcOH2"


def test_scheme_search_json_no_matches(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(DatabaseCache, "load_catalog", _search_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(main, ["scheme", "search", "shigella", "-f", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "gmlst-scheme-list-v1"
    assert payload["data"] == []


def test_scheme_list_limit_truncates_json(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(DatabaseCache, "load_catalog", _search_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(
        main, ["scheme", "list", "-p", "pubmlst", "-f", "json", "--limit", "2"]
    )

    assert result.exit_code == 0
    payload = _parse_trailing_json(result.output)
    scheme_names = [row["scheme_name"] for row in payload["data"]]
    assert scheme_names == ["ecoli_1", "ecoli_2"]
    assert "Showing 2 of 3 matching schemes." in result.output


def test_scheme_list_limit_truncates_tsv_before_rendering(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(DatabaseCache, "load_catalog", _search_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(
        main, ["scheme", "list", "-p", "pubmlst", "-f", "tsv", "-l", "1"]
    )

    assert result.exit_code == 0
    lines = [
        line
        for line in result.output.strip().splitlines()
        if not line.startswith("Showing ")
    ]
    # One header + exactly one data row: truncation happens before rendering.
    assert len(lines) == 2
    assert lines[1].split("\t")[1] == "ecoli_1"
    assert "Showing 1 of 3 matching schemes." in result.output


def test_scheme_list_limit_default_is_unlimited(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(DatabaseCache, "load_catalog", _search_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(main, ["scheme", "list", "-p", "pubmlst", "-f", "json"])

    assert result.exit_code == 0
    payload = _parse_trailing_json(result.output)
    assert len(payload["data"]) == 3
    assert "matching schemes." not in result.output


def test_scheme_search_limit_truncates_json(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(DatabaseCache, "load_catalog", _search_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(
        main, ["scheme", "search", "ecoli", "-f", "json", "--limit", "1"]
    )

    assert result.exit_code == 0
    payload = _parse_trailing_json(result.output)
    assert [row["scheme_name"] for row in payload["data"]] == ["ecoli_1"]
    assert "Showing 1 of 2 matching schemes." in result.output


def test_scheme_search_table_default_output(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(DatabaseCache, "load_catalog", _search_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(main, ["scheme", "search", "ecoli"])

    assert result.exit_code == 0
    assert "Search: 'ecoli' (2 matches)" in result.output
    assert "scheme download" in result.output
    assert "{" not in result.output


def test_scheme_search_table_no_matches_message(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(DatabaseCache, "load_catalog", _search_catalog)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)

    result = runner.invoke(main, ["scheme", "search", "shigella"])

    assert result.exit_code == 0
    assert "No schemes matching 'shigella'." in result.output


def test_scheme_download_json_summary(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "ecoli_1", "scheme_type": "mlst", "n_loci": 7}]
        return []

    def _fake_ensure_scheme(self, name: str, **kwargs):
        return Scheme(
            name=name,
            loci=["arcC", "aroE", "glpF", "gmk", "pta", "tpi", "yqiL"],
            allele_files={},
        )

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "ensure_scheme", _fake_ensure_scheme)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        DatabaseCache,
        "scheme_dir",
        lambda self, name, provider="pubmlst": Path(f"/tmp/{provider}/{name}"),
    )

    result = runner.invoke(main, ["scheme", "download", "ecoli_1", "--format", "json"])

    assert result.exit_code == 0
    payload = _parse_trailing_json(result.output)
    assert payload == {
        "schema_version": "gmlst-scheme-op-v1",
        "data": {
            "scheme": "ecoli_1",
            "provider": "pubmlst",
            "scheme_type": "mlst",
            "path": "/tmp/pubmlst/ecoli_1",
            "n_loci": 7,
        },
    }
    # Human status messages remain as-is before the JSON summary.
    assert "Downloading" in result.output
    assert "Done." in result.output


def test_scheme_download_default_text_output(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "ecoli_1", "scheme_type": "mlst", "n_loci": 7}]
        return []

    def _fake_ensure_scheme(self, name: str, **kwargs):
        return Scheme(name=name, loci=["arcC", "aroE"], allele_files={})

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "ensure_scheme", _fake_ensure_scheme)
    monkeypatch.setattr(DatabaseCache, "is_downloaded", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        DatabaseCache,
        "scheme_dir",
        lambda self, name, provider="pubmlst": Path(f"/tmp/{provider}/{name}"),
    )

    result = runner.invoke(main, ["scheme", "download", "ecoli_1"])

    assert result.exit_code == 0
    assert "Done." in result.output
    assert "Cached at" in result.output
    assert "{" not in result.output


def test_scheme_update_single_json_summary(monkeypatch) -> None:
    runner = CliRunner()
    toggle = {"changed": True}

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "ecoli_1", "scheme_type": "mlst"}]
        return []

    def _fake_update_scheme(self, name: str, **kwargs):
        return (object(), toggle["changed"])

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(DatabaseCache, "update_scheme", _fake_update_scheme)
    monkeypatch.setattr(
        DatabaseCache,
        "scheme_dir",
        lambda self, name, provider="pubmlst": Path(f"/tmp/{provider}/{name}"),
    )

    result = runner.invoke(
        main, ["scheme", "update", "-s", "ecoli_1", "--format", "json"]
    )

    assert result.exit_code == 0
    payload = _parse_trailing_json(result.output)
    assert payload == {
        "schema_version": "gmlst-scheme-op-v1",
        "data": {"scheme": "ecoli_1", "provider": "pubmlst", "changed": True},
    }
    assert "Updated." in result.output

    toggle["changed"] = False
    result = runner.invoke(
        main, ["scheme", "update", "-s", "ecoli_1", "--format", "json"]
    )

    assert result.exit_code == 0
    payload = _parse_trailing_json(result.output)
    assert payload == {
        "schema_version": "gmlst-scheme-op-v1",
        "data": {"scheme": "ecoli_1", "provider": "pubmlst", "changed": False},
    }
    assert "Up to date." in result.output


def test_scheme_update_all_json_summary(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_list_cached(self):
        return [
            {"scheme": "ecoli_1", "provider": "pubmlst", "scheme_type": "mlst"},
            {"scheme": "senterica", "provider": "cgmlst", "scheme_type": "cgmlst"},
            {"scheme": "broken_1", "provider": "pubmlst", "scheme_type": "mlst"},
        ]

    def _fake_update_scheme(self, name: str, **kwargs):
        if name == "broken_1":
            raise RuntimeError("network down")
        return (object(), name == "ecoli_1")

    monkeypatch.setattr(DatabaseCache, "list_cached", _fake_list_cached)
    monkeypatch.setattr(DatabaseCache, "update_scheme", _fake_update_scheme)

    result = runner.invoke(main, ["scheme", "update", "-a", "-y", "--format", "json"])

    assert result.exit_code == 1
    payload = _parse_trailing_json(result.output)
    assert payload["schema_version"] == "gmlst-scheme-op-v1"
    data = payload["data"]
    assert data["total"] == 3
    assert data["updated"] == 1
    assert data["unchanged"] == 1
    assert data["failed"] == 1
    assert [row["status"] for row in data["results"]] == [
        "updated",
        "unchanged",
        "failed",
    ]
    failed_row = data["results"][2]
    assert failed_row["scheme"] == "broken_1"
    assert failed_row["provider"] == "pubmlst"
    assert failed_row["error"] == "network down"
    assert data["results"][0] == {
        "scheme": "ecoli_1",
        "provider": "pubmlst",
        "status": "updated",
        "error": None,
    }
    # Per-scheme progress lines still go to the progress console.
    assert "✗ broken_1" in result.output


def test_scheme_update_all_json_confirmation_still_prompts(monkeypatch) -> None:
    runner = CliRunner()
    called: list[str] = []

    def _fake_list_cached(self):
        return [{"scheme": "ecoli_1", "provider": "pubmlst", "scheme_type": "mlst"}]

    def _fake_update_scheme(self, name: str, **kwargs):
        called.append(name)
        return (object(), False)

    monkeypatch.setattr(DatabaseCache, "list_cached", _fake_list_cached)
    monkeypatch.setattr(DatabaseCache, "update_scheme", _fake_update_scheme)

    result = runner.invoke(
        main, ["scheme", "update", "-a", "--format", "json"], input="n\n"
    )

    assert result.exit_code == 0
    assert called == []
    assert "Proceed with updating all cached schemes?" in result.output
    assert "Aborted." in result.output
    assert "{" not in result.output


def test_scheme_update_all_text_default_failed_exit_code(monkeypatch) -> None:
    runner = CliRunner()

    def _fake_list_cached(self):
        return [{"scheme": "broken_1", "provider": "pubmlst", "scheme_type": "mlst"}]

    def _fake_update_scheme(self, name: str, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(DatabaseCache, "list_cached", _fake_list_cached)
    monkeypatch.setattr(DatabaseCache, "update_scheme", _fake_update_scheme)

    result = runner.invoke(main, ["scheme", "update", "-a", "-y"])

    assert result.exit_code == 1
    assert "Updated: 0; unchanged: 0; failed: 1" in result.output
    assert "{" not in result.output


def test_scheme_create_json_summary(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    source_scheme = Scheme(
        name="ecoli_1",
        loci=["arcC", "aroE"],
        allele_files={},
        profile_file=None,
    )

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "ecoli_1", "scheme_type": "mlst"}]
        return []

    data_dir = tmp_path / "novel"
    data_dir.mkdir()
    (data_dir / "arcC_novel.fasta").write_text(">arcC_n1 sample=isolate_A\nACGT\n")
    (data_dir / "profiles_novel.txt").write_text(
        "ST\tsample\tarcC\taroE\nN1\tisolate_A\tn1\t1\n"
    )

    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_load_catalog)
    monkeypatch.setattr(
        DatabaseCache,
        "ensure_scheme",
        lambda self, name, **kwargs: source_scheme,
    )

    result = runner.invoke(
        main,
        [
            "scheme",
            "create",
            "-t",
            "mlst",
            "-s",
            "ecoli_1",
            "--data-dir",
            str(data_dir),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = _parse_trailing_json(result.output)
    assert payload["schema_version"] == "gmlst-scheme-op-v1"
    data = payload["data"]
    assert data["scheme"] == "custom_1"
    assert data["n_loci"] == 2
    assert data["source"] == "ecoli_1"
    assert data["source_provider"] == "pubmlst"
    assert data["novel_alleles_added"] == 1
    assert data["novel_profiles_added"] == 1
    assert data["path"].endswith("custom_1")
    assert Path(data["path"]).is_dir()
    # Human summary remains alongside the JSON document.
    assert "Created custom scheme:" in result.output


def test_scheme_update_custom_json_summary(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    scheme_dir = tmp_path / "custom_1"
    scheme_dir.mkdir()
    (scheme_dir / "arcC.tfa").write_text(">arcC_1\nACGT\n")
    (scheme_dir / "custom_1.txt").write_text("ST\tarcC\taroE\n1\t1\t1\n")

    data_dir = tmp_path / "novel"
    data_dir.mkdir()
    (data_dir / "arcC_novel.fasta").write_text(">arcC_n1 sample=isolate_A\nACGTT\n")

    monkeypatch.setattr(
        DatabaseCache,
        "scheme_dir",
        lambda self, name, provider="pubmlst": scheme_dir,
    )
    monkeypatch.setattr(
        DatabaseCache,
        "get_scheme_metadata",
        lambda self, name, provider: {
            "loci": ["arcC", "aroE"],
            "last_allele_number": {"arcC": 1},
            "novel_profiles": ["N1"],
        },
    )
    monkeypatch.setattr(
        DatabaseCache, "write_scheme_metadata", lambda self, *args, **kwargs: None
    )

    result = runner.invoke(
        main,
        [
            "scheme",
            "update-custom",
            "custom_1",
            "--data-dir",
            str(data_dir),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = _parse_trailing_json(result.output)
    assert payload == {
        "schema_version": "gmlst-scheme-op-v1",
        "data": {"scheme": "custom_1", "new_alleles_added": 1},
    }
    assert "New alleles added: 1" in result.output
