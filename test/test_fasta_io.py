from __future__ import annotations

import gzip
from io import StringIO
from pathlib import Path

from gmlst.fasta_io import iter_fasta_records, iter_fasta_sequences, write_wrapped_fasta


def test_iter_fasta_sequences_reads_plain_and_uppercases(tmp_path: Path) -> None:
    fasta = tmp_path / "alleles.fasta"
    fasta.write_text(">abc_1\natgc\n>abc_2\nTTaa\n")

    assert list(iter_fasta_sequences(fasta)) == ["ATGC", "TTAA"]


def test_iter_fasta_records_reads_gzip_and_preserves_headers(tmp_path: Path) -> None:
    fasta = tmp_path / "alleles.fasta.gz"
    with gzip.open(fasta, "wt") as handle:
        handle.write(">abc_1 description\natgc\n>abc-2 other\nTTaa\n")

    assert list(iter_fasta_records(fasta)) == [
        ("abc_1", "ATGC"),
        ("abc-2", "TTAA"),
    ]


def test_write_wrapped_fasta_wraps_to_width() -> None:
    handle = StringIO()

    write_wrapped_fasta(handle, "abc_1", "A" * 65, width=60)

    assert handle.getvalue() == f">abc_1\n{'A' * 60}\n{'A' * 5}\n"
