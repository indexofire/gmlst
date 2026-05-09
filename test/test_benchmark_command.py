from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from gmlst.cli import main
from gmlst.commands.utils import BackendMetrics, BenchmarkResult


def _fake_result(sample_path: Path) -> BenchmarkResult:
    return BenchmarkResult(
        scheme="saureus_1",
        samples=[sample_path],
        metrics={
            "kma": BackendMetrics(
                backend="kma",
                n_samples=1,
                total_wall_time=0.1,
                peak_memory_mb=10.0,
                n_exact_sts=1,
                n_novel_sts=0,
                n_failed=0,
            )
        },
    )


def test_utils_benchmark_table_invokes_runner_and_report(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    captured: dict[str, object] = {}

    def _fake_run_benchmark(**kwargs):
        captured.update(kwargs)
        return _fake_result(sample)

    def _fake_print_report(result: BenchmarkResult) -> None:
        captured["reported"] = result.scheme

    monkeypatch.setattr("gmlst.commands.utils.run_benchmark", _fake_run_benchmark)
    monkeypatch.setattr("gmlst.commands.utils.print_report", _fake_print_report)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "benchmark",
            "-s",
            "saureus_1",
            "-b",
            "kma,minimap2",
            "-r",
            "3",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["scheme_name"] == "saureus_1"
    assert captured["backends"] == ["kma", "minimap2"]
    assert captured["repeat"] == 3
    assert captured["reported"] == "saureus_1"


def test_utils_benchmark_tsv_writes_output_file(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")
    output = tmp_path / "bench.tsv"

    monkeypatch.setattr(
        "gmlst.commands.utils.run_benchmark", lambda **_: _fake_result(sample)
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "benchmark",
            "-s",
            "saureus_1",
            "-b",
            "kma",
            "-f",
            "tsv",
            "-o",
            str(output),
            str(sample),
        ],
    )

    assert result.exit_code == 0
    text = output.read_text()
    assert text.startswith("backend\ttotal_time_s")
    assert "\nkma\t" in text


def test_utils_benchmark_default_table_writes_output_file(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")
    output = tmp_path / "bench.txt"

    monkeypatch.setattr(
        "gmlst.commands.utils.run_benchmark", lambda **_: _fake_result(sample)
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "benchmark",
            "-s",
            "saureus_1",
            "-b",
            "kma",
            "-o",
            str(output),
            str(sample),
        ],
    )

    assert result.exit_code == 0
    text = output.read_text()
    assert "Benchmark results — scheme: saureus_1" in text
    assert "Backend" in text


def test_utils_benchmark_rejects_unknown_backend(tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["utils", "benchmark", "-s", "saureus_1", "-b", "foo", str(sample)],
    )

    assert result.exit_code != 0
    assert "Unknown backend(s): foo" in result.output


def test_utils_benchmark_help_shows_cgmlst_gate_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["utils", "benchmark", "--help"])
    assert result.exit_code == 0
    assert "--cgmlst-gate" in result.output
    assert "--gate-details-output" in result.output


def test_utils_benchmark_cgmlst_gate_uses_gate_runner(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")
    captured: dict[str, object] = {}

    def _fake_gate(**kwargs):
        captured.update(kwargs)
        return {
            "mode": "cgmlst-gate",
            "scheme": kwargs["scheme_name"],
            "backend": kwargs["backend"],
            "n_samples": len(kwargs["sample_paths"]),
            "mismatch_count": 0,
            "mismatches": [],
        }

    monkeypatch.setattr("gmlst.commands.utils.run_cgmlst_gate", _fake_gate)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "benchmark",
            "-s",
            "vparahaemolyticus_3",
            "-b",
            "minimap2",
            "--cgmlst-gate",
            "-f",
            "json",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    assert captured["scheme_name"] == "vparahaemolyticus_3"
    assert captured["backend"] == "minimap2"
    payload = json.loads(result.output)
    assert payload["mode"] == "cgmlst-gate"
    assert payload["scheme"] == "vparahaemolyticus_3"
    assert payload["backend"] == "minimap2"
    assert payload["n_samples"] == 1
    assert payload["mismatch_count"] == 0
    assert payload["mismatches"] == []


def test_utils_benchmark_cgmlst_gate_enforces_mismatch_threshold(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    monkeypatch.setattr(
        "gmlst.commands.utils.run_cgmlst_gate",
        lambda **_: {
            "mode": "cgmlst-gate",
            "scheme": "vparahaemolyticus_3",
            "backend": "minimap2",
            "n_samples": 1,
            "mismatch_count": 2,
            "mismatches": ["s1", "s2"],
            "mismatch_details": [],
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "benchmark",
            "-s",
            "vparahaemolyticus_3",
            "-b",
            "minimap2",
            "--cgmlst-gate",
            "--gate-max-mismatches",
            "1",
            str(sample),
        ],
    )

    assert result.exit_code != 0
    assert "exceeds allowed" in result.output


def test_run_cgmlst_gate_emits_detailed_diff(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")

    def _mk_result(sample_id: str, st: str, loci: dict[str, str]):
        calls = {
            locus: SimpleNamespace(allele_id=allele_id)
            for locus, allele_id in loci.items()
        }
        return SimpleNamespace(sample_id=sample_id, st=st, locus_calls=calls)

    sequence = [
        [_mk_result("s1", "10", {"abc": "1", "def": "2"})],
        [_mk_result("s1", "11", {"abc": "1", "def": "9"})],
    ]

    def _fake_run_typing(**_kwargs):
        return sequence.pop(0)

    monkeypatch.setattr("gmlst.commands.utils.run_typing", _fake_run_typing)

    from gmlst.commands.utils import run_cgmlst_gate

    gate = run_cgmlst_gate(
        scheme_name="vparahaemolyticus_3",
        sample_paths=[sample],
        backend="minimap2",
    )

    assert gate["mismatch_count"] == 1
    assert gate["mismatches"] == ["s1"]
    assert gate["mismatch_details"][0]["sample_id"] == "s1"
    assert gate["mismatch_details"][0]["st_on"] == "10"
    assert gate["mismatch_details"][0]["st_off"] == "11"
    assert gate["mismatch_details"][0]["differing_loci"][0]["locus"] == "def"


def test_utils_benchmark_cgmlst_gate_writes_details_jsonl(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")
    details_output = tmp_path / "gate_details.jsonl"

    monkeypatch.setattr(
        "gmlst.commands.utils.run_cgmlst_gate",
        lambda **_: {
            "mode": "cgmlst-gate",
            "scheme": "vparahaemolyticus_3",
            "backend": "minimap2",
            "n_samples": 1,
            "mismatch_count": 1,
            "mismatches": ["s1"],
            "mismatch_details": [
                {
                    "sample_id": "s1",
                    "st_on": "10",
                    "st_off": "11",
                    "differing_loci": [{"locus": "abc", "on": "1", "off": "9"}],
                }
            ],
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "benchmark",
            "-s",
            "vparahaemolyticus_3",
            "-b",
            "minimap2",
            "--cgmlst-gate",
            "--gate-max-mismatches",
            "1",
            "--gate-details-output",
            str(details_output),
            str(sample),
        ],
    )

    assert result.exit_code == 0
    lines = details_output.read_text().strip().splitlines()
    assert len(lines) == 1
    assert '"sample_id": "s1"' in lines[0]


def test_utils_benchmark_cgmlst_gate_writes_details_tsv(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGC\n")
    details_output = tmp_path / "gate_details.tsv"

    monkeypatch.setattr(
        "gmlst.commands.utils.run_cgmlst_gate",
        lambda **_: {
            "mode": "cgmlst-gate",
            "scheme": "vparahaemolyticus_3",
            "backend": "minimap2",
            "n_samples": 1,
            "mismatch_count": 1,
            "mismatches": ["s1"],
            "mismatch_details": [
                {
                    "sample_id": "s1",
                    "st_on": "10",
                    "st_off": "11",
                    "differing_loci": [{"locus": "abc", "on": "1", "off": "9"}],
                }
            ],
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "benchmark",
            "-s",
            "vparahaemolyticus_3",
            "-b",
            "minimap2",
            "--cgmlst-gate",
            "--gate-max-mismatches",
            "1",
            "--gate-details-output",
            str(details_output),
            "--gate-details-format",
            "tsv",
            str(sample),
        ],
    )

    assert result.exit_code == 0
    text = details_output.read_text()
    assert text.startswith("sample_id\tst_on\tst_off\tdiffering_loci\n")
    assert "s1\t10\t11\t" in text
