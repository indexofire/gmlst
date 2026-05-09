from __future__ import annotations

from pathlib import Path

import gmlst.commands.typing as typing_cmd
from gmlst.readers.sample import SampleInput


def test_contains_fastq_samples_detects_path_extensions() -> None:
    samples = [Path("sample1.fasta"), Path("reads_R1.FASTQ.GZ")]
    assert typing_cmd._contains_fastq_samples(samples) is True


def test_contains_fastq_samples_detects_sampleinput_type() -> None:
    samples = [
        SampleInput(sample_id="s1", path=Path("x.fna"), input_type="fasta"),
        SampleInput(sample_id="s2", path=Path("x.fq"), input_type="fastq"),
    ]
    assert typing_cmd._contains_fastq_samples(samples) is True


def test_contains_fastq_samples_returns_false_for_non_fastq_inputs() -> None:
    samples = [
        Path("sample1.fasta"),
        SampleInput(sample_id="s1", path=Path("x.fna"), input_type="fasta"),
    ]
    assert typing_cmd._contains_fastq_samples(samples) is False


def test_temp_root_from_output_sets_and_restores_env(monkeypatch) -> None:
    monkeypatch.delenv("GMLST_TMPDIR", raising=False)
    output = Path("/tmp/result.tsv")

    with typing_cmd._temp_root_from_output(output):
        assert typing_cmd.os.environ["GMLST_TMPDIR"] == str(output.parent)

    assert "GMLST_TMPDIR" not in typing_cmd.os.environ


def test_temp_root_from_output_restores_previous_env(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_TMPDIR", "/tmp/original")
    output = Path("/tmp/new/result.tsv")

    with typing_cmd._temp_root_from_output(output):
        assert typing_cmd.os.environ["GMLST_TMPDIR"] == str(output.parent)

    assert typing_cmd.os.environ["GMLST_TMPDIR"] == "/tmp/original"
