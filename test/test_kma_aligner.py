from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gmlst.aligners.kma import KmaAligner
from gmlst.readers.sample import SampleInput


def test_kma_dependency_message_when_missing(monkeypatch) -> None:
    monkeypatch.setattr("gmlst.aligners.kma.shutil.which", lambda _bin: None)
    aligner = KmaAligner()
    with pytest.raises(RuntimeError) as exc:
        aligner.check_dependencies()
    assert "git clone https://github.com/genomicepidemiology/kma.git" in str(exc.value)


def test_kma_index_runs_build_command(monkeypatch, tmp_path: Path) -> None:
    allele = tmp_path / "abc.tfa"
    allele.write_text(">abc_1\nATGCATGC\n")

    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["kma", "index"]:
            prefix = Path(cmd[cmd.index("-o") + 1])
            (prefix.with_suffix(".name")).write_text("abc_1\n")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("gmlst.aligners.kma.subprocess.run", _fake_run)

    aligner = KmaAligner()
    idx_path = aligner.index([allele], tmp_path / "idx")

    assert idx_path == tmp_path / "idx"
    assert calls
    assert calls[0][:2] == ["kma", "index"]


def test_kma_align_parses_res(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fq"
    sample.write_text("@r1\nATGC\n+\n####\n")
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "kma_db.name").write_text("abc_1\n")

    called_cmd: list[str] = []

    def _fake_run(cmd, **kwargs):
        called_cmd[:] = cmd
        out_prefix = Path(cmd[cmd.index("-o") + 1])
        out_prefix.with_suffix(".res").write_text(
            "#Template\tScore\tExpected\tTemplate_length\tTemplate_Identity\tTemplate_Coverage\tQuery_Identity\tQuery_Coverage\tDepth\tq_value\tp_value\n"
            "abc_12\t350\t1\t450\t99.8\t100.0\t99.8\t100.0\t42.0\t0.99\t0.0\n"
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("gmlst.aligners.kma.subprocess.run", _fake_run)

    aligner = KmaAligner(threads=4)
    result = aligner.align(sample, index_dir, ["abc", "def"], "fastq")

    assert result.backend == "kma"
    assert result.sample_id == "sample"
    assert len(result.matches) == 1
    hit = result.matches[0]
    assert hit.locus == "abc"
    assert hit.allele_id == "12"
    assert hit.identity == 99.8
    assert hit.coverage == 1.0
    assert hit.depth == 42.0
    assert "def" in result.failed_loci
    assert "-1t1" not in called_cmd
    assert "-ill" in called_cmd
    assert "-asm" not in called_cmd


def test_kma_align_fasta_ignores_depth_threshold_field(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">s\nATGCATGC\n")
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "kma_db.name").write_text("abc_1\n")

    called_cmd: list[str] = []

    def _fake_run(cmd, **kwargs):
        called_cmd[:] = cmd
        out_prefix = Path(cmd[cmd.index("-o") + 1])
        out_prefix.with_suffix(".res").write_text(
            "#Template\tScore\tExpected\tTemplate_length\tTemplate_Identity\tTemplate_Coverage\tQuery_Identity\tQuery_Coverage\tDepth\tq_value\tp_value\n"
            "abc_12\t350\t1\t450\t100.0\t100.0\t100.0\t100.0\t1.0\t0.99\t0.0\n"
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("gmlst.aligners.kma.subprocess.run", _fake_run)

    aligner = KmaAligner(threads=2)
    result = aligner.align(sample, index_dir, ["abc"], "fasta")

    assert len(result.matches) == 1
    hit = result.matches[0]
    assert hit.locus == "abc"
    assert hit.allele_id == "12"
    assert hit.depth is None
    assert "-asm" in called_cmd
    assert "-ill" not in called_cmd


def test_kma_align_fastq_mem_mode_adds_flag(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fq"
    sample.write_text("@r1\nATGC\n+\n####\n")
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "kma_db.name").write_text("abc_1\n")

    called_cmd: list[str] = []

    def _fake_run(cmd, **kwargs):
        called_cmd[:] = cmd
        out_prefix = Path(cmd[cmd.index("-o") + 1])
        out_prefix.with_suffix(".res").write_text(
            "#Template\tScore\tExpected\tTemplate_length\tTemplate_Identity\tTemplate_Coverage\tQuery_Identity\tQuery_Coverage\tDepth\tq_value\tp_value\n"
            "abc_1\t350\t1\t450\t99.8\t100.0\t99.8\t100.0\t42.0\t0.99\t0.0\n"
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("gmlst.aligners.kma.subprocess.run", _fake_run)

    aligner = KmaAligner(threads=1, fastq_mem_mode=True)
    _ = aligner.align(sample, index_dir, ["abc"], "fastq")

    assert "-ill" in called_cmd
    assert "-mem_mode" in called_cmd


def test_kma_align_fastq_pair_preserves_normalized_sample_id(
    monkeypatch, tmp_path: Path
) -> None:
    r1 = tmp_path / "sample_R1.fastq.gz"
    r2 = tmp_path / "sample_R2.fastq.gz"
    r1.write_text("@r1\nATGC\n+\n####\n")
    r2.write_text("@r2\nATGC\n+\n####\n")
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "kma_db.name").write_text("abc_1\n")

    def _fake_run(cmd, **kwargs):
        out_prefix = Path(cmd[cmd.index("-o") + 1])
        out_prefix.with_suffix(".res").write_text(
            "#Template\tScore\tExpected\tTemplate_length\tTemplate_Identity\tTemplate_Coverage\tQuery_Identity\tQuery_Coverage\tDepth\tq_value\tp_value\n"
            "abc_1\t350\t1\t450\t99.8\t100.0\t99.8\t100.0\t42.0\t0.99\t0.0\n"
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("gmlst.aligners.kma.subprocess.run", _fake_run)

    sample = SampleInput.from_fastq_pair(r1, r2, "sample")
    aligner = KmaAligner(threads=1)
    result = aligner.align((sample.path, sample.mate_path), index_dir, ["abc"], "fastq")

    assert result.sample_id == "sample"
