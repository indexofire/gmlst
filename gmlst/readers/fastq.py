"""FASTQ reader utilities."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

from gmlst.utils import open_text


@dataclass
class FastqRecord:
    """One FASTQ read."""

    header: str
    sequence: str
    quality: str

    @property
    def read_id(self) -> str:
        return self.header.split()[0].lstrip("@")

    @property
    def length(self) -> int:
        return len(self.sequence)


class FastqReader:
    """Streaming FASTQ parser (supports plain and gzip-compressed files).

    Reads standard 4-line FASTQ format only (no multi-line sequences).
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def records(self) -> Generator[FastqRecord, None, None]:
        """Yield :class:`FastqRecord` objects one at a time."""
        with open_text(self.path) as fh:
            while True:
                header = fh.readline().rstrip()
                if not header:
                    break
                sequence = fh.readline().rstrip().upper()
                fh.readline()  # '+' separator line
                quality = fh.readline().rstrip()
                if not sequence:
                    break
                yield FastqRecord(header, sequence, quality)

    def estimate_coverage(self, genome_size: int) -> float:
        """Estimate sequencing depth as total_bases / genome_size.

        Parameters
        ----------
        genome_size:
            Expected genome size in base pairs.
        """
        if genome_size <= 0:
            return 0.0
        total_bases = sum(r.length for r in self.records())
        return total_bases / genome_size

    def read_count(self) -> int:
        """Count total reads (requires full file scan)."""
        return sum(1 for _ in self.records())
