"""Tests for minimap2 aligner (FASTA mode only)."""

from pathlib import Path

import pytest

from gmlst.aligners import minimap2 as minimap2_mod


def test_align_fasta_respects_emit_cigar_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    aligner = minimap2_mod.Minimap2Aligner(threads=1, fasta_emit_cigar=False)
    monkeypatch.setattr(minimap2_mod, "_parse_paf", lambda *_a, **_k: [])

    genome = tmp_path / "genome.fna"
    genome.write_text(">contig1\nATGC\n")
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "alleles.fasta").write_text(">abc_1\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_cmd(cmd: list[str], **_kwargs: object) -> None:
        captured["cmd"] = cmd

    monkeypatch.setattr(minimap2_mod, "run_cmd", fake_run_cmd)
    aligner._align_fasta(genome, index_dir, ["abc"])

    assert "-c" not in captured["cmd"]


def test_align_fasta_applies_fast_speed_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    aligner = minimap2_mod.Minimap2Aligner(threads=1, fasta_speed_profile="fast")
    monkeypatch.setattr(minimap2_mod, "_parse_paf", lambda *_a, **_k: [])

    genome = tmp_path / "genome.fna"
    genome.write_text(">contig1\nATGC\n")
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "alleles.fasta").write_text(">abc_1\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_cmd(cmd: list[str], **_kwargs: object) -> None:
        captured["cmd"] = cmd

    monkeypatch.setattr(minimap2_mod, "run_cmd", fake_run_cmd)
    aligner._align_fasta(genome, index_dir, ["abc"])

    assert "-w" in captured["cmd"]
    assert "15" in captured["cmd"]


def test_align_fasta_applies_ultrafast_speed_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    aligner = minimap2_mod.Minimap2Aligner(threads=1, fasta_speed_profile="ultrafast")
    monkeypatch.setattr(minimap2_mod, "_parse_paf", lambda *_a, **_k: [])

    genome = tmp_path / "genome.fna"
    genome.write_text(">contig1\nATGC\n")
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "alleles.fasta").write_text(">abc_1\nATGC\n")

    captured: dict[str, object] = {}

    def fake_run_cmd(cmd: list[str], **_kwargs: object) -> None:
        captured["cmd"] = cmd

    monkeypatch.setattr(minimap2_mod, "run_cmd", fake_run_cmd)
    aligner._align_fasta(genome, index_dir, ["abc"])

    assert "-f" in captured["cmd"]
    assert "0.001" in captured["cmd"]


def test_supports_fastq_returns_false() -> None:
    aligner = minimap2_mod.Minimap2Aligner(threads=1)
    assert aligner.supports_fastq is False
