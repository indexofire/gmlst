"""Minimal GenBank/EMBL flat-file input: record IDs and nucleotide sequences.

Only what MLST typing needs is parsed: the record identifier (``LOCUS``
for GenBank, ``ID`` for EMBL) and the nucleotide sequence block
(``ORIGIN`` / ``SQ``). Features and annotations are ignored. Gzipped
input is handled transparently via :func:`gmlst.utils.open_text`.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from gmlst.fasta_io import write_wrapped_fasta
from gmlst.utils import open_text, temp_dir

_GENBANK_SUFFIXES = {".gbk", ".gb", ".gbff"}
_EMBL_SUFFIXES = {".embl"}


def is_genbank_path(path: Path) -> bool:
    """Return True when *path* looks like a GenBank/EMBL flat file."""
    return _effective_suffix(path) in _GENBANK_SUFFIXES | _EMBL_SUFFIXES


def iter_records(path: Path) -> Iterator[tuple[str, str]]:
    """Yield ``(record_id, sequence)`` pairs from a GenBank or EMBL file.

    Dispatches on the file extension (``.embl`` selects the EMBL parser).
    Sequences are uppercased. Raises ``ValueError`` for malformed input.
    """
    if _effective_suffix(path) in _EMBL_SUFFIXES:
        return _iter_embl(path)
    return _iter_genbank(path)


def convert_to_fasta(path: Path, target: Path) -> Path:
    """Convert a GenBank/EMBL file to FASTA written at *target*."""
    with target.open("w") as handle:
        for record_id, sequence in iter_records(path):
            write_wrapped_fasta(handle, record_id, sequence)
    return target


@contextmanager
def ensure_fasta_samples(
    samples: Sequence[Path],
) -> Generator[tuple[Path, ...], None, None]:
    """Convert GenBank/EMBL samples to temporary FASTA for the context.

    FASTA/FASTQ samples pass through unchanged. Converted files live in a
    temporary directory under ``GMLST_TMPDIR`` and are removed on exit.
    """
    paths = [Path(sample) for sample in samples]
    if not any(is_genbank_path(path) for path in paths):
        yield tuple(paths)
        return
    with temp_dir("gmlst_conv_") as tmp:
        converted: list[Path] = []
        for index, path in enumerate(paths):
            if is_genbank_path(path):
                target = tmp / f"{index}_{path.name}.fna"
                converted.append(convert_to_fasta(path, target))
            else:
                converted.append(path)
        yield tuple(converted)


def _effective_suffix(path: Path) -> str:
    """Return the suffix of *path*, looking beneath an optional ``.gz``."""
    p = path
    if p.suffix.lower() == ".gz":
        p = p.with_suffix("")
    return p.suffix.lower()


def _iter_genbank(path: Path) -> Iterator[tuple[str, str]]:
    """Yield ``(locus_id, sequence)`` pairs from a GenBank flat file."""
    locus: str | None = None
    chunks: list[str] = []
    in_origin = False
    saw_records = False
    with open_text(path) as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line.startswith("LOCUS"):
                if locus is not None:
                    raise ValueError(f"Malformed GenBank file '{path}': nested LOCUS")
                locus = line.split()[1]
                chunks = []
                in_origin = False
            elif line == "//":
                if locus is not None:
                    if not in_origin:
                        raise ValueError(
                            f"Malformed GenBank file '{path}': record "
                            f"'{locus}' has no ORIGIN sequence block"
                        )
                    yield locus, "".join(chunks).upper()
                    saw_records = True
                locus = None
                chunks = []
                in_origin = False
            elif in_origin:
                compact = "".join(line.split())
                chunks.append(compact.lstrip("0123456789"))
            elif line.startswith("ORIGIN"):
                in_origin = True
    if locus is not None:
        raise ValueError(
            f"Malformed GenBank file '{path}': record '{locus}' is not terminated by //"
        )
    if not saw_records:
        raise ValueError(f"No GenBank records found in '{path}'")


def _iter_embl(path: Path) -> Iterator[tuple[str, str]]:
    """Yield ``(entry_id, sequence)`` pairs from an EMBL flat file."""
    entry_id: str | None = None
    chunks: list[str] = []
    in_sequence = False
    saw_records = False
    with open_text(path) as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            tokens = stripped.split()
            if tokens and tokens[0] == "ID" and not in_sequence:
                if entry_id is not None:
                    raise ValueError(f"Malformed EMBL file '{path}': nested ID")
                entry_id = tokens[1].rstrip(";")
                chunks = []
            elif tokens and tokens[0] == "SQ":
                in_sequence = True
            elif stripped == "//":
                if entry_id is not None:
                    if not in_sequence:
                        raise ValueError(
                            f"Malformed EMBL file '{path}': entry "
                            f"'{entry_id}' has no SQ sequence block"
                        )
                    yield entry_id, "".join(chunks).upper()
                    saw_records = True
                entry_id = None
                chunks = []
                in_sequence = False
            elif in_sequence:
                chunks.append("".join(tokens))
    if entry_id is not None:
        raise ValueError(
            f"Malformed EMBL file '{path}': entry '{entry_id}' is not terminated by //"
        )
    if not saw_records:
        raise ValueError(f"No EMBL records found in '{path}'")
