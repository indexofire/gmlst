"""FASTA reader utilities."""

from __future__ import annotations

import gzip
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FastaRecord:
    """One FASTA sequence record."""

    header: str
    sequence: str

    @property
    def seq_id(self) -> str:
        """First whitespace-delimited token of the header."""
        return self.header.split()[0]

    @property
    def length(self) -> int:
        return len(self.sequence)


class FastaReader:
    """Streaming FASTA parser (supports plain and gzip-compressed files)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def records(self) -> Generator[FastaRecord, None, None]:
        """Yield :class:`FastaRecord` objects one at a time."""
        opener = gzip.open if self.path.suffix.lower() == ".gz" else open
        current_header: str | None = None
        seq_parts: list[str] = []

        def _emit() -> FastaRecord | None:
            if current_header is not None:
                return FastaRecord(current_header, "".join(seq_parts))
            return None

        with opener(self.path, "rt") as fh:  # type: ignore[call-overload]
            for line in fh:
                line = line.rstrip()
                if not line:
                    continue
                if line.startswith(">"):
                    record = _emit()
                    if record is not None:
                        yield record
                    current_header = line[1:]
                    seq_parts = []
                else:
                    seq_parts.append(line.upper())

        record = _emit()
        if record is not None:
            yield record

    def to_dict(self) -> dict[str, str]:
        """Return all sequences as ``{seq_id: sequence}``."""
        return {r.seq_id: r.sequence for r in self.records()}

    def total_length(self) -> int:
        """Sum of all sequence lengths (useful for genome size estimate)."""
        return sum(r.length for r in self.records())
