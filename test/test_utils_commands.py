from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gmlst.aligners.base import AlleleMatch
from gmlst.calling.allele import LocusCall
from gmlst.calling.st_lookup import STResult
from gmlst.cli import main
from gmlst.database.schema import Scheme


def test_utils_group_help_shows_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["utils", "--help"])
    assert result.exit_code == 0
    assert "Utility commands for extraction" in result.output
    assert "extract" in result.output
    assert "concat" in result.output
    assert "check" in result.output


def test_utils_subcommand_help_has_descriptions() -> None:
    runner = CliRunner()
    extract_help = runner.invoke(main, ["utils", "extract", "--help"])
    concat_help = runner.invoke(main, ["utils", "concat", "--help"])
    check_help = runner.invoke(main, ["utils", "check", "--help"])

    assert extract_help.exit_code == 0
    assert concat_help.exit_code == 0
    assert check_help.exit_code == 0
    assert "Extract allele/novel data" in extract_help.output
    assert "Concatenate multi-record FASTA" in concat_help.output
    assert "Backend to check dependency installation" in check_help.output


def test_utils_check_reports_backend_available(monkeypatch) -> None:
    class _DummyAligner:
        def check_dependencies(self) -> None:
            return None

    monkeypatch.setattr(
        "gmlst.commands.utils.get_aligner", lambda _name: _DummyAligner()
    )

    runner = CliRunner()
    result = runner.invoke(main, ["utils", "check", "-b", "blastn"])
    assert result.exit_code == 0
    assert "[OK] backend=blastn is available" in result.output


def test_utils_check_reports_backend_missing(monkeypatch) -> None:
    class _DummyAligner:
        def check_dependencies(self) -> None:
            raise RuntimeError("binary not found")

    monkeypatch.setattr(
        "gmlst.commands.utils.get_aligner", lambda _name: _DummyAligner()
    )

    runner = CliRunner()
    result = runner.invoke(main, ["utils", "check", "-b", "blastn"])
    assert result.exit_code == 1
    assert "[FAIL] backend=blastn" in result.output


def test_utils_extract_allele_mode_outputs_fasta(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fasta"
    sample.write_text(">contig1\nATGCATGCATGC\n")

    dna_path = tmp_path / "dnaN.tfa"
    dna_path.write_text(">dnaN_1\nATGCATGC\n")
    gyr_path = tmp_path / "gyrB.tfa"
    gyr_path.write_text(">gyrB_5\nGCGCGCGC\n")

    scheme = Scheme(
        name="ecoli_1",
        loci=["dnaN", "gyrB"],
        allele_files={"dnaN": dna_path, "gyrB": gyr_path},
        profile_file=None,
    )

    def _fake_ensure_scheme(self, name: str, **_kwargs):
        assert name == "ecoli_1"
        return scheme

    def _fake_run_typing(**_kwargs):
        return [
            STResult(
                sample_id="sample",
                scheme="ecoli_1",
                st=1,
                locus_calls={
                    "dnaN": LocusCall(
                        locus="dnaN",
                        allele_id="1",
                        call_type="exact",
                        confidence=1.0,
                        best_match=AlleleMatch(
                            locus="dnaN",
                            allele_id="1",
                            identity=100.0,
                            coverage=1.0,
                        ),
                    ),
                    "gyrB": LocusCall(
                        locus="gyrB",
                        allele_id="5",
                        call_type="exact",
                        confidence=1.0,
                        best_match=AlleleMatch(
                            locus="gyrB",
                            allele_id="5",
                            identity=100.0,
                            coverage=1.0,
                        ),
                    ),
                },
                backend="blastn",
                runtime_seconds=0.01,
            )
        ]

    monkeypatch.setattr("gmlst.commands.utils.run_typing", _fake_run_typing)
    monkeypatch.setattr(
        "gmlst.commands.utils.DatabaseCache.ensure_scheme",
        _fake_ensure_scheme,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "extract",
            "-i",
            str(sample),
            "-s",
            "ecoli_1",
            "--allele",
            "dnaN",
        ],
    )

    assert result.exit_code == 0
    assert ">sample|dnaN_1" in result.output
    assert "ATGCATGC" in result.output
    assert "gyrB" not in result.output


def test_utils_extract_novel_from_json(tmp_path: Path) -> None:
    payload = [
        {
            "sample_id": "sample_A",
            "scheme": "ecoli_1",
            "st": None,
            "allele_calls": {
                "dnaN": {
                    "allele_id": "101",
                    "call_type": "novel",
                    "novel_sequence": "ATGCATGC",
                },
                "gyrB": {
                    "allele_id": "5",
                    "call_type": "exact",
                    "novel_sequence": None,
                },
            },
        }
    ]
    result_json = tmp_path / "result.json"
    result_json.write_text(json.dumps(payload))

    out_dir = tmp_path / "novel"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "extract",
            "-i",
            str(result_json),
            "--novel-allele",
            "--novel-profile",
            "--data-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0

    allele_file = out_dir / "dnaN_novel.fasta"
    profile_file = out_dir / "profiles_novel.txt"
    assert allele_file.exists()
    assert profile_file.exists()
    assert "dnaN_n1" in allele_file.read_text()
    assert "N1\tsample_A\tn1\t5" in profile_file.read_text()


def test_utils_extract_novel_from_tsv_with_samples_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tsv = tmp_path / "results.tsv"
    tsv.write_text("sample\tST\tdnaN\tgyrB\nsample_A\t-\t~101\t5\n")

    sample_file = tmp_path / "sample_A.fasta"
    sample_file.write_text(">s\nATGC\n")

    dna_path = tmp_path / "dnaN.tfa"
    dna_path.write_text(">dnaN_1\nATGC\n")
    gyr_path = tmp_path / "gyrB.tfa"
    gyr_path.write_text(">gyrB_5\nGCGC\n")
    scheme = Scheme(
        name="ecoli_1",
        loci=["dnaN", "gyrB"],
        allele_files={"dnaN": dna_path, "gyrB": gyr_path},
        profile_file=None,
    )

    def _fake_ensure_scheme(self, name: str, **_kwargs):
        assert name == "ecoli_1"
        return scheme

    def _fake_run_typing(**_kwargs):
        return [
            STResult(
                sample_id="sample_A",
                scheme="ecoli_1",
                st=None,
                locus_calls={
                    "dnaN": LocusCall(
                        locus="dnaN",
                        allele_id="101",
                        call_type="novel",
                        confidence=0.9,
                        novel_sequence="ATGCATGC",
                        best_match=AlleleMatch(
                            locus="dnaN",
                            allele_id="101",
                            identity=97.0,
                            coverage=1.0,
                        ),
                    ),
                    "gyrB": LocusCall(
                        locus="gyrB",
                        allele_id="5",
                        call_type="exact",
                        confidence=1.0,
                        best_match=AlleleMatch(
                            locus="gyrB",
                            allele_id="5",
                            identity=100.0,
                            coverage=1.0,
                        ),
                    ),
                },
                backend="blastn",
                runtime_seconds=0.01,
            )
        ]

    monkeypatch.setattr("gmlst.commands.utils.run_typing", _fake_run_typing)
    monkeypatch.setattr(
        "gmlst.commands.utils.DatabaseCache.ensure_scheme",
        _fake_ensure_scheme,
    )

    out_dir = tmp_path / "novel_out"
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
            "--novel-profile",
            "--samples-dir",
            str(tmp_path),
            "--data-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "dnaN_novel.fasta").exists()
    assert (out_dir / "profiles_novel.txt").exists()


def test_utils_concat_builds_single_sequence(tmp_path: Path) -> None:
    fasta = tmp_path / "alleles.fasta"
    fasta.write_text(">a\nAAAA\n>b\nTTTT\n")

    runner = CliRunner()
    result = runner.invoke(main, ["utils", "concat", "-i", str(fasta)])

    assert result.exit_code == 0
    assert ">alleles_concat" in result.output
    assert "AAAATTTT" in result.output


def test_utils_concat_writes_output_file(tmp_path: Path) -> None:
    fasta = tmp_path / "alleles.fasta"
    fasta.write_text(">a\nAAAA\n>b\nTTTT\n")
    out = tmp_path / "concat.fasta"

    runner = CliRunner()
    result = runner.invoke(main, ["utils", "concat", "-i", str(fasta), "-o", str(out)])

    assert result.exit_code == 0
    assert result.output == ""
    assert out.read_text() == ">alleles_concat\nAAAATTTT\n"
