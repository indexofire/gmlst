"""Schema-version envelopes on CLI JSON outputs (P1-7).

Every CLI JSON stdout/file output is wrapped as
``{"schema_version": <constant>, "data": <payload>}`` (see
``gmlst/schema_versions.py``) so agents can version-check before parsing.
Includes the typing → utils-extract round trip, the only place gmlst
re-reads its own JSON output.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import gmlst.commands.typing as typing_cmd
from gmlst.aligners.base import AlleleMatch
from gmlst.calling.allele import LocusCall
from gmlst.calling.st_lookup import STResult
from gmlst.cli import main


class _DummyScheme:
    loci = ["dnaN", "gyrB"]


class _DummyCache:
    def __init__(self, _root) -> None:
        pass

    def ensure_scheme(self, _name, provider, scheme_type="mlst"):
        return _DummyScheme()

    def detect_provider(self, _name, prefer_type=None):
        return "pubmlst"

    def load_catalog(self, _provider):
        return [{"scheme_name": "ecoli_1", "scheme_type": "mlst"}]


def _st_result() -> STResult:
    return STResult(
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


def _write_typing_json(monkeypatch, tmp_path: Path, output: Path) -> None:
    sample = tmp_path / "sample_A.fasta"
    sample.write_text(">contig1\nATGCATGCATGC\n")
    monkeypatch.setattr(typing_cmd, "DatabaseCache", _DummyCache)
    monkeypatch.setattr(typing_cmd, "run_typing", lambda **_: [_st_result()])

    typing_cmd._run_mlst_like_typing(
        mode="mlst",
        samples=(sample,),
        scheme="ecoli_1",
        backend="blastn",
        min_id=95.0,
        min_cov=0.95,
        min_depth=10.0,
        fmt="json",
        output=output,
        cache_dir=None,
        force_reindex=False,
        no_header=False,
        threads=1,
        count_same_copy=False,
        provider=None,
        novel_allele=False,
        novel_profile=False,
        output_dir=None,
    )


def test_typing_json_file_is_enveloped(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "results.json"

    _write_typing_json(monkeypatch, tmp_path, output)

    envelope = json.loads(output.read_text())
    assert envelope["schema_version"] == "gmlst-typing-v1"
    data = envelope["data"]
    assert isinstance(data, list)
    assert data[0]["sample_id"] == "sample_A"
    assert isinstance(data[0]["allele_calls"], dict)


def test_typing_json_envelope_round_trips_through_utils_extract(
    monkeypatch, tmp_path: Path
) -> None:
    output = tmp_path / "results.json"
    _write_typing_json(monkeypatch, tmp_path, output)

    out_dir = tmp_path / "novel"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "utils",
            "extract",
            "-i",
            str(output),
            "--novel-allele",
            "--novel-profile",
            "--data-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    allele_file = out_dir / "dnaN_novel.fasta"
    profile_file = out_dir / "profiles_novel.txt"
    assert "dnaN_n1" in allele_file.read_text()
    assert "N1\tsample_A\tn1\t5" in profile_file.read_text()


def test_visual_matrix_json_is_enveloped(tmp_path: Path) -> None:
    input_path = tmp_path / "profiles.tsv"
    input_path.write_text(
        "\n".join(
            [
                "FILE\tSCHEME\tST\tL1\tL2",
                "s1\tvpa\t11\t1\t1",
                "s2\tvpa\t12\t1\t2",
            ]
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["visual", "matrix", "--input", str(input_path)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "gmlst-visual-matrix-v1"
    assert payload["data"]["labels"] == ["s1", "s2"]


def test_visual_heatmap_json_is_enveloped(tmp_path: Path) -> None:
    input_path = tmp_path / "profiles.tsv"
    input_path.write_text(
        "\n".join(
            [
                "FILE\tSCHEME\tST\tL1\tL2",
                "s1\tvpa\t11\t1\t1",
                "s2\tvpa\t12\t1\t2",
            ]
        )
    )

    runner = CliRunner()
    result = runner.invoke(main, ["visual", "heatmap", "--input", str(input_path)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "gmlst-visual-heatmap-v1"
    assert payload["data"]["labels"] == ["s1", "s2"]


def test_visual_locus_diff_json_is_enveloped(tmp_path: Path) -> None:
    input_path = tmp_path / "profiles.tsv"
    input_path.write_text(
        "\n".join(
            [
                "FILE\tSCHEME\tST\tL1\tL2",
                "s1\tvpa\t11\t1\t1",
                "s2\tvpa\t12\t1\t2",
            ]
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "visual",
            "locus-diff",
            "--input",
            str(input_path),
            "--left-label",
            "s1",
            "--right-label",
            "s2",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "gmlst-visual-locus-diff-v1"
    assert payload["data"]["left_label"] == "s1"


def test_visual_compare_json_is_enveloped(tmp_path: Path) -> None:
    left = tmp_path / "left.tsv"
    right = tmp_path / "right.tsv"
    left.write_text(
        "\n".join(["FILE\tSCHEME\tST\tL1", "s1\tvpa\t11\t1", "s2\tvpa\t12\t2"])
    )
    right.write_text(
        "\n".join(["FILE\tSCHEME\tST\tL1", "s1\tvpa\t11\t1", "s2\tvpa\t21\t2"])
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["visual", "compare", "--left", str(left), "--right", str(right)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "gmlst-visual-compare-v1"
    assert payload["data"]["summary"]["different_st"] == 1
