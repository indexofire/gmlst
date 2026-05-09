"""SampleInput: unified representation of one input file."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

InputType = Literal["fasta", "fastq"]

_FASTA_SUFFIXES = {".fasta", ".fa", ".fna", ".ffn", ".frn"}
_FASTQ_SUFFIXES = {".fastq", ".fq"}
_ILLUMINA_TAIL_RE = re.compile(
    r"^(?P<base>.+)_S\d+(?:_L\d{3})?(?:_R[12])?(?:_\d{3})?$",
    flags=re.IGNORECASE,
)
_FASTQ_MATE_TAIL_RE = re.compile(
    r"^(?P<base>.+?)(?:[_\.]R[12])(?:[_\.]\d{3})?$",
    flags=re.IGNORECASE,
)
_FASTQ_PAIR_R_RE = re.compile(
    r"^(.*?)(?:[_\.]R([12]))(?:[_\.]\d{3})?$",
    flags=re.IGNORECASE,
)
_FASTQ_PAIR_NUM_RE = re.compile(
    r"^(.*?)(?:[_\.])([12])(?:[_\.]\d{3})?$",
    flags=re.IGNORECASE,
)


@dataclass
class SampleInput:
    """Represents one input sample (FASTA or FASTQ, optionally gzipped)."""

    sample_id: str
    path: Path
    input_type: InputType
    mate_path: Path | None = None

    @classmethod
    def from_path(cls, path: Path) -> SampleInput:
        """Auto-detect input type from file extension.

        Strips a trailing ``.gz`` suffix before checking the extension.

        Raises
        ------
        ValueError
            If the extension is not recognised as FASTA or FASTQ.
        """
        p = path
        if p.suffix.lower() == ".gz":
            p = p.with_suffix("")  # strip .gz to inspect real extension

        suffix = p.suffix.lower()
        if suffix in _FASTA_SUFFIXES:
            input_type: InputType = "fasta"
        elif suffix in _FASTQ_SUFFIXES:
            input_type = "fastq"
        else:
            raise ValueError(
                f"Cannot determine input type for '{path}'. "
                f"Expected one of: "
                f"{sorted(_FASTA_SUFFIXES | _FASTQ_SUFFIXES)} (optionally .gz)"
            )

        # Build a clean sample ID: strip known suffixes from the stem
        sample_id = path.name
        for sfx in (".gz", ".fasta", ".fa", ".fna", ".ffn", ".frn", ".fastq", ".fq"):
            if sample_id.lower().endswith(sfx):
                sample_id = sample_id[: -len(sfx)]

        if input_type == "fastq":
            sample_id = _normalize_fastq_sample_id(sample_id)

        return cls(sample_id=sample_id, path=path, input_type=input_type)

    @classmethod
    def from_fastq_pair(
        cls, r1_path: Path, r2_path: Path, sample_id: str
    ) -> SampleInput:
        return cls(
            sample_id=sample_id, path=r1_path, input_type="fastq", mate_path=r2_path
        )


def detect_sample(path: Path) -> SampleInput:
    """Convenience wrapper around :meth:`SampleInput.from_path`."""
    return SampleInput.from_path(path)


def _normalize_fastq_sample_id(sample_id: str) -> str:
    match = _ILLUMINA_TAIL_RE.match(sample_id)
    if match is not None:
        base = match.group("base")
        if base:
            return base

    mate_match = _FASTQ_MATE_TAIL_RE.match(sample_id)
    if mate_match is not None:
        base = mate_match.group("base")
        if base:
            return base

    return sample_id


def prepare_sample_inputs(samples: list[Path]) -> list[Path | SampleInput]:
    key_by_sample: dict[Path, tuple[str, str]] = {}
    mates_by_key: dict[str, dict[str, Path]] = {}

    for sample in samples:
        pair_info = _extract_fastq_pair_info(sample)
        if pair_info is None:
            continue
        key, mate = pair_info
        key_by_sample[sample] = (key, mate)
        mates_by_key.setdefault(key, {})[mate] = sample

    paired_keys = {
        key for key, mates in mates_by_key.items() if "1" in mates and "2" in mates
    }
    if not paired_keys:
        return list(samples)

    prepared: list[Path | SampleInput] = []
    emitted_keys: set[str] = set()
    for sample in samples:
        pair = key_by_sample.get(sample)
        if pair is None:
            prepared.append(sample)
            continue

        key, _mate = pair
        if key in paired_keys:
            if key not in emitted_keys:
                r1 = mates_by_key[key]["1"]
                r2 = mates_by_key[key]["2"]
                sample_id = SampleInput.from_path(r1).sample_id
                prepared.append(SampleInput.from_fastq_pair(r1, r2, sample_id))
                emitted_keys.add(key)
            continue

        prepared.append(sample)

    return prepared


def _extract_fastq_pair_info(sample_path: Path) -> tuple[str, str] | None:
    name = sample_path.name
    lower_name = name.lower()
    if not (
        lower_name.endswith(".fastq")
        or lower_name.endswith(".fq")
        or lower_name.endswith(".fastq.gz")
        or lower_name.endswith(".fq.gz")
    ):
        return None

    stem = name
    if stem.lower().endswith(".gz"):
        stem = stem[:-3]
    if stem.lower().endswith(".fastq"):
        stem = stem[:-6]
    elif stem.lower().endswith(".fq"):
        stem = stem[:-3]

    match = _FASTQ_PAIR_R_RE.match(stem)
    if match:
        return (match.group(1), match.group(2))

    match = _FASTQ_PAIR_NUM_RE.match(stem)
    if match:
        return (match.group(1), match.group(2))

    return None
