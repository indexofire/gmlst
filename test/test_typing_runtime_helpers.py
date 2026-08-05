from __future__ import annotations

from pathlib import Path

from gmlst.commands.typing_fastq import contains_fastq_samples, temp_root_from_output
from gmlst.readers.sample import SampleInput


def test_contains_fastq_samples_detects_path_extensions() -> None:
    samples = [Path("sample1.fasta"), Path("reads_R1.FASTQ.GZ")]
    assert contains_fastq_samples(samples) is True


def test_contains_fastq_samples_detects_sampleinput_type() -> None:
    samples = [
        SampleInput(sample_id="s1", path=Path("x.fna"), input_type="fasta"),
        SampleInput(sample_id="s2", path=Path("x.fq"), input_type="fastq"),
    ]
    assert contains_fastq_samples(samples) is True


def test_contains_fastq_samples_returns_false_for_non_fastq_inputs() -> None:
    samples = [
        Path("sample1.fasta"),
        SampleInput(sample_id="s1", path=Path("x.fna"), input_type="fasta"),
    ]
    assert contains_fastq_samples(samples) is False


def test_temp_root_from_output_sets_and_restores_env(monkeypatch) -> None:
    import os

    monkeypatch.delenv("GMLST_TMPDIR", raising=False)
    output = Path("/tmp/result.tsv")

    with temp_root_from_output(output):
        assert os.environ["GMLST_TMPDIR"] == str(output.parent)

    assert "GMLST_TMPDIR" not in os.environ


def test_temp_root_from_output_restores_previous_env(monkeypatch) -> None:
    import os

    monkeypatch.setenv("GMLST_TMPDIR", "/tmp/original")
    output = Path("/tmp/new/result.tsv")

    with temp_root_from_output(output):
        assert os.environ["GMLST_TMPDIR"] == str(output.parent)

    assert os.environ["GMLST_TMPDIR"] == "/tmp/original"
