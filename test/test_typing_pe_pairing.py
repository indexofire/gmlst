from __future__ import annotations

from pathlib import Path

from gmlst.commands.typing import (
    _extract_fastq_pair_info,
    _prepare_sample_paths_for_pairing,
)
from gmlst.readers.sample import SampleInput


def test_extract_fastq_pair_info_patterns() -> None:
    assert _extract_fastq_pair_info(Path("sample_R1.fastq")) == ("sample", "1")
    assert _extract_fastq_pair_info(Path("sample_R2.fastq.gz")) == ("sample", "2")
    assert _extract_fastq_pair_info(Path("sample_R1_001.fastq.gz")) == ("sample", "1")
    assert _extract_fastq_pair_info(Path("sample_R2_001.fastq.gz")) == ("sample", "2")
    assert _extract_fastq_pair_info(Path("sample_R1_010.fastq.gz")) == ("sample", "1")
    assert _extract_fastq_pair_info(Path("sample_r2_010.fastq.gz")) == ("sample", "2")
    assert _extract_fastq_pair_info(Path("sample.1.fq")) == ("sample", "1")
    assert _extract_fastq_pair_info(Path("sample_2.fq.gz")) == ("sample", "2")
    assert _extract_fastq_pair_info(Path("sample.fasta")) is None


def test_prepare_sample_paths_for_pairing_groups_detected_pairs(tmp_path: Path) -> None:
    r1 = tmp_path / "abc_R1.fastq"
    r2 = tmp_path / "abc_R2.fastq"
    single = tmp_path / "single.fastq"

    r1.write_text("@r1\nAAAA\n+\n####\n")
    r2.write_text("@r2\nTTTT\n+\n####\n")
    single.write_text("@s\nCCCC\n+\n####\n")

    prepared = _prepare_sample_paths_for_pairing((r1, r2, single))
    assert len(prepared) == 2
    pair = prepared[0]
    assert isinstance(pair, SampleInput)
    assert pair.path == r1
    assert pair.mate_path == r2
    assert pair.sample_id == "abc"
    assert prepared[1] == single
