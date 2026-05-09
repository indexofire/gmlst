from __future__ import annotations

import gzip
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO


def _open_text(path: Path):
    return gzip.open(path, "rt") if path.suffix == ".gz" else path.open()


def iter_fasta_records(path: Path) -> Iterator[tuple[str, str]]:
    header: str | None = None
    chunks: list[str] = []
    with _open_text(path) as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield header, "".join(chunks).upper()
                header = line[1:].split()[0]
                chunks = []
                continue
            chunks.append(line)
    if header is not None:
        yield header, "".join(chunks).upper()


def iter_fasta_sequences(path: Path) -> Iterator[str]:
    for _header, sequence in iter_fasta_records(path):
        yield sequence


def write_wrapped_fasta(
    handle: TextIO,
    header: str,
    sequence: str,
    *,
    width: int = 60,
) -> None:
    handle.write(f">{header}\n")
    write_wrapped_sequence(handle, sequence, width=width)


def write_wrapped_sequence(
    handle: TextIO,
    sequence: str,
    *,
    width: int = 60,
) -> None:
    for index in range(0, len(sequence), width):
        handle.write(sequence[index : index + width] + "\n")
