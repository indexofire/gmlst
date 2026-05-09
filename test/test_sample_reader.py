from __future__ import annotations

from pathlib import Path

from gmlst.readers.sample import SampleInput


def test_fastq_sample_id_strips_illumina_tail() -> None:
    sample = SampleInput.from_path(Path("22VPA0001_S1_L001_R1_001.fastq.gz"))
    assert sample.sample_id == "22VPA0001"
    assert sample.input_type == "fastq"


def test_fastq_sample_id_keeps_non_illumina_tail() -> None:
    sample = SampleInput.from_path(Path("alpha_sample_v2.fastq.gz"))
    assert sample.sample_id == "alpha_sample_v2"
    assert sample.input_type == "fastq"


def test_fastq_sample_id_strips_generic_r1_tail() -> None:
    sample = SampleInput.from_path(Path("abc_R1.fastq.gz"))
    assert sample.sample_id == "abc"
    assert sample.input_type == "fastq"


def test_fasta_sample_id_not_normalized_by_illumina_rule() -> None:
    sample = SampleInput.from_path(Path("strain_S1_L001.fasta"))
    assert sample.sample_id == "strain_S1_L001"
    assert sample.input_type == "fasta"
