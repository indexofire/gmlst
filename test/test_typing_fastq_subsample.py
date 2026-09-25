"""Tests for FASTQ depth subsampling (typing_fastq.maybe_subsample_fastq)."""

from __future__ import annotations

import gzip
from pathlib import Path

from gmlst.commands.typing_fastq import maybe_subsample_fastq
from gmlst.readers.sample import SampleInput


def _write_fastq(path: Path, reads: int, read_len: int = 150) -> Path:
    # Plain (uncompressed) FASTA bytes keep the depth estimate deterministic:
    # ~330 bytes/read -> 1000 reads ≈ 0.038x with the 250 B/read model.
    seq = "ACGTACGTAC" * (read_len // 10)
    with path.open("w") as handle:
        for i in range(reads):
            handle.write(f"@r{i}\n{seq}\n+\n{'I' * read_len}\n")
    return path


def _count_reads(path: Path) -> int:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as handle:
        return sum(1 for i, _ in enumerate(handle) if i % 4 == 0)


def test_under_depth_sample_passes_through(tmp_path: Path) -> None:
    fq = _write_fastq(tmp_path / "shallow.fastq.gz", reads=10)

    out = maybe_subsample_fastq([fq], max_depth=100)

    assert out == [fq]


def test_subsample_output_survives_the_call(tmp_path: Path) -> None:
    fq = _write_fastq(tmp_path / "deep.fastq", reads=1000)

    out = maybe_subsample_fastq([fq], max_depth=0.01)

    assert out != [fq]
    subsampled = out[0]
    # The returned path must still exist once the function has returned —
    # the typing run consumes it later.
    assert isinstance(subsampled, Path)
    assert subsampled.exists(), "subsampled FASTQ deleted before use"
    assert _count_reads(subsampled) > 0


def test_subsample_truncates_to_target_reads(tmp_path: Path) -> None:
    fq = _write_fastq(tmp_path / "deep.fastq", reads=1000)

    out = maybe_subsample_fastq([fq], max_depth=0.01)

    subsampled = out[0]
    assert isinstance(subsampled, Path)
    # target = 0.01 * 5 Mb / 150 ≈ 333 reads
    assert 300 <= _count_reads(subsampled) <= 340


def test_subsample_paired_sample_input_keeps_metadata(tmp_path: Path) -> None:
    r1 = _write_fastq(tmp_path / "deep_R1.fastq", reads=1000)
    r2 = _write_fastq(tmp_path / "deep_R2.fastq", reads=1000)
    sample = SampleInput(sample_id="deep", path=r1, mate_path=r2, input_type="fastq")

    out = maybe_subsample_fastq([sample], max_depth=0.01)

    assert len(out) == 1
    result = out[0]
    assert isinstance(result, SampleInput)
    assert result.sample_id == "deep"
    assert result.path.exists()
    assert result.mate_path is not None
    assert result.mate_path.exists()
