"""CLI failure paths must emit clean one-line errors, never raw tracebacks.

Covers the audit's remaining traceback paths:

* ``utils extract --novel-allele`` with a corrupted typing-result JSON
  (``click.UsageError`` → exit 2).
* ``utils extract`` allele/TSV-retyping modes when scheme resolution or the
  typing run fails at runtime (``err_console`` + ``sys.exit(1)``).
* ``utils benchmark`` when scheme resolution or the cgMLST gate run fails
  (``err_console`` + ``sys.exit(1)``).
* ``typing tgmlst --load-scheme`` with a corrupted scheme JSON
  (``err_console`` + ``sys.exit(1)``).
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from gmlst.cli import main
from gmlst.database.schema import Scheme


def _write_sample(tmp_path: Path) -> Path:
    sample = tmp_path / "sample.fna"
    sample.write_text(">contig1\nATGCATGCATGC\n")
    return sample


def _make_scheme(tmp_path: Path) -> Scheme:
    dna_path = tmp_path / "dnaN.tfa"
    dna_path.write_text(">dnaN_1\nATGCATGC\n")
    return Scheme(
        name="ecoli_1",
        loci=["dnaN"],
        allele_files={"dnaN": dna_path},
        profile_file=None,
    )


def test_utils_extract_novel_invalid_json_reports_usage_error(
    tmp_path: Path,
) -> None:
    bad_json = tmp_path / "result.json"
    bad_json.write_text("{not-valid-json")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "extract",
            "-i",
            str(bad_json),
            "--novel-allele",
            "--data-dir",
            str(tmp_path / "novel"),
        ],
    )

    assert result.exit_code == 2
    assert "Invalid JSON in input file" in result.output
    assert "Traceback" not in result.output


def test_utils_extract_allele_mode_scheme_failure_exits_clean(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_sample(tmp_path)

    def _boom(self, name: str, **_kwargs):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr("gmlst.commands.utils.DatabaseCache.ensure_scheme", _boom)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["utils", "extract", "-i", str(sample), "-s", "ecoli_1"],
    )

    assert result.exit_code == 1
    assert "network unreachable" in result.output
    assert "Traceback" not in result.output


def test_utils_extract_allele_mode_typing_failure_exits_clean(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_sample(tmp_path)
    scheme = _make_scheme(tmp_path)

    monkeypatch.setattr(
        "gmlst.commands.utils.DatabaseCache.ensure_scheme",
        lambda self, name, **_kwargs: scheme,
    )

    def _fake_run_typing(**_kwargs):
        raise RuntimeError("blastn binary not found")

    monkeypatch.setattr("gmlst.core.run_typing", _fake_run_typing)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["utils", "extract", "-i", str(sample), "-s", "ecoli_1"],
    )

    assert result.exit_code == 1
    assert "blastn binary not found" in result.output
    assert "Traceback" not in result.output


def test_utils_extract_tsv_retyping_scheme_failure_exits_clean(
    monkeypatch, tmp_path: Path
) -> None:
    tsv = tmp_path / "results.tsv"
    tsv.write_text("sample\tST\tdnaN\nsample_A\t-\t~101\n")
    (tmp_path / "sample_A.fasta").write_text(">s\nATGC\n")

    def _boom(self, name: str, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("gmlst.commands.utils.DatabaseCache.ensure_scheme", _boom)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "extract",
            "-i",
            str(tsv),
            "-s",
            "ecoli_1",
            "--novel-allele",
            "--samples-dir",
            str(tmp_path),
            "--data-dir",
            str(tmp_path / "novel"),
        ],
    )

    assert result.exit_code == 1
    assert "provider unavailable" in result.output
    assert "Traceback" not in result.output


def test_utils_benchmark_scheme_resolution_failure_exits_clean(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_sample(tmp_path)

    def _boom(self, name: str, **_kwargs):
        raise RuntimeError("scheme download failed")

    monkeypatch.setattr("gmlst.commands.utils.DatabaseCache.ensure_scheme", _boom)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "benchmark",
            "-s",
            "ecoli_1",
            "-b",
            "kma",
            "--cache-dir",
            str(tmp_path / "cache"),
            str(sample),
        ],
    )

    assert result.exit_code == 1
    assert "scheme download failed" in result.output
    assert "Traceback" not in result.output


def test_utils_benchmark_gate_run_failure_exits_clean(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_sample(tmp_path)

    def _boom(**_kwargs):
        raise RuntimeError("aligner index build failed")

    monkeypatch.setattr("gmlst.commands.utils.run_cgmlst_gate", _boom)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "benchmark",
            "-s",
            "ecoli_1",
            "-b",
            "minimap2",
            "--cgmlst-gate",
            "--cache-dir",
            str(tmp_path / "cache"),
            str(sample),
        ],
    )

    assert result.exit_code == 1
    assert "aligner index build failed" in result.output
    assert "Traceback" not in result.output


def test_tgmlst_load_scheme_corrupt_json_exits_clean(tmp_path: Path) -> None:
    sample = _write_sample(tmp_path)
    scheme_file = tmp_path / "scheme.json"
    scheme_file.write_text("{corrupt json")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["typing", "tgmlst", str(sample), "--load-scheme", str(scheme_file)],
    )

    assert result.exit_code == 1
    assert "Failed to load scheme" in result.output
    assert "Traceback" not in result.output


def test_tgmlst_load_scheme_wrong_shape_exits_clean(tmp_path: Path) -> None:
    sample = _write_sample(tmp_path)
    scheme_file = tmp_path / "scheme.json"
    scheme_file.write_text("[1, 2, 3]")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["typing", "tgmlst", str(sample), "--load-scheme", str(scheme_file)],
    )

    assert result.exit_code == 1
    assert "Failed to load scheme" in result.output
    assert "Traceback" not in result.output
