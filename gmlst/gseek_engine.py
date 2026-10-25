"""Optional gseek bridge for gmlst alignment backends.

``GMLST_ENGINE`` selects the implementation:

- ``legacy`` (default): the aligner classes in :mod:`gmlst.aligners`;
- ``gseek``: gseek plans/parses the alignment;
- ``shadow``: run both, compare, log, and return legacy.

The switch uses :mod:`gseek.compat`; legacy mode never imports gseek.
"""

from __future__ import annotations

import functools
import importlib
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypeVar

from gmlst.aligners.base import (
    Aligner,
    AlignmentResult,
    AlleleMatch,
    build_alignment_result,
    cap_fragments,
    select_best_matches,
    split_allele_id,
)
from gmlst.fasta_io import iter_fasta_records

logger = logging.getLogger(__name__)
_ENGINE_ENV = "GMLST_ENGINE"


@functools.lru_cache(maxsize=1)
def _resolver() -> Any:
    """Cache tool probes for one gmlst process."""
    execution = importlib.import_module("gseek.execution")
    return execution.ToolResolver()


_VALID_MODES = frozenset({"legacy", "gseek", "shadow"})
T = TypeVar("T")


class _LegacyMode:
    value = "legacy"


class _LegacyEngine:
    mode = _LegacyMode()

    def run(
        self,
        legacy: Callable[[], T],
        gseek: Callable[[], T],
        *,
        compare: Callable[[T, T], bool] | None = None,
    ) -> T:
        return legacy()


def engine() -> Any:
    """Return the engine switch, importing gseek only for gseek/shadow."""
    raw = os.environ.get(_ENGINE_ENV, "legacy").strip().lower() or "legacy"
    if raw not in _VALID_MODES:
        raise RuntimeError(
            f"unknown GMLST_ENGINE={raw!r}; expected one of {sorted(_VALID_MODES)}"
        )
    if raw == "legacy":
        return _LegacyEngine()
    try:
        compat = importlib.import_module("gseek.compat")
    except ImportError as exc:
        raise RuntimeError(
            "GMLST_ENGINE=gseek requires the optional gseek package "
            "(install gmlst[gseek])"
        ) from exc
    return compat.Engine.from_env(_ENGINE_ENV, logger=logger)


def engine_mode() -> str:
    return engine().mode.value


class GseekAligner:
    """Aligner facade that dispatches legacy/gseek/shadow per call."""

    def __init__(self, name: str, legacy: Aligner) -> None:
        self._name = name
        self._legacy = legacy

    @property
    def name(self) -> str:
        return self._legacy.name

    @property
    def supports_fastq(self) -> bool:
        return self._legacy.supports_fastq

    def check_dependencies(self) -> None:
        self._legacy.check_dependencies()

    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
        # The legacy index is the allele FASTA materialization used by both
        # paths; gseek BLASTN is run in subject mode against the sample.
        return self._legacy.index(allele_fastas, index_dir)

    def align(
        self,
        sample: Path | tuple[Path, Path],
        index_path: Path,
        loci: list[str],
        input_type: Literal["fasta", "fastq"],
    ) -> AlignmentResult:
        def legacy() -> AlignmentResult:
            return self._legacy.align(sample, index_path, loci, input_type)

        def gseek() -> AlignmentResult:
            return _gseek_align(self._name, sample, index_path, loci, input_type)

        return engine().run(
            legacy,
            gseek,
            compare=_same_alignment,
        )


def _same_alignment(left: AlignmentResult, right: AlignmentResult) -> bool:
    def keys(result: AlignmentResult) -> list[tuple[Any, ...]]:
        return sorted(
            (
                match.locus,
                match.allele_id,
                round(match.identity, 3),
                round(match.coverage, 4),
                match.alignment_length,
                match.strand,
                match.query_contig,
                match.query_start,
                match.query_end,
            )
            for match in result.matches
        )

    return keys(left) == keys(right) and sorted(left.failed_loci) == sorted(
        right.failed_loci
    )


def _gseek_align(
    backend: str,
    sample: Path | tuple[Path, Path],
    index_path: Path,
    loci: list[str],
    input_type: Literal["fasta", "fastq"],
) -> AlignmentResult:
    if backend != "blastn":
        raise RuntimeError(f"gseek backend not implemented for {backend!r} yet")
    if isinstance(sample, tuple):
        raise ValueError("BlastnAligner does not support paired input")
    if input_type != "fasta":
        raise ValueError("BlastnAligner does not support FASTQ input. Use kma backend.")

    gseek = importlib.import_module("gseek")

    sample_id = sample.stem.split(".")[0]
    alleles_fasta = index_path.parent / "alleles.fasta"
    started = time.perf_counter()
    result = gseek.align(
        backend="blast",
        query=alleles_fasta,
        target=sample,
        params={
            "task": "megablast",
            "evalue": 10.0,
            "dust": False,
            "min_identity": 80.0,
        },
        index="none",
        resolver=_resolver(),
        record_manifest=False,
    )
    fragments = _blast_fragments(result.records, loci)
    allele_order = {
        header: index
        for index, (header, _) in enumerate(iter_fasta_records(alleles_fasta))
    }
    contig_order = {
        header: index for index, (header, _) in enumerate(iter_fasta_records(sample))
    }
    fragments.sort(
        key=lambda frag: (
            allele_order.get(f"{frag.locus}_{frag.allele_id}", 10**9),
            contig_order.get(frag.query_contig or "", 10**9),
            frag.query_start or 0,
        )
    )
    best = [
        AlleleMatch(
            locus=frag.locus,
            allele_id=frag.allele_id,
            identity=frag.identity,
            coverage=frag.coverage,
            alignment_length=frag.alignment_length,
            score=frag.score,
            sequence=frag.sequence,
            strand=frag.strand,
            query_contig=frag.query_contig,
            query_start=frag.query_start,
            query_end=frag.query_end,
        )
        for frag in select_best_matches(fragments)
    ]
    return build_alignment_result(
        sample_id=sample_id,
        backend="blastn",
        matches=best,
        fragments=cap_fragments(fragments),
        loci=loci,
        runtime_seconds=time.perf_counter() - started,
    )


def _blast_fragments(records: tuple[Any, ...], loci: list[str]) -> list[AlleleMatch]:
    loci_set = set(loci)
    fragments: list[AlleleMatch] = []
    for record in records:
        locus, allele_id = split_allele_id(record.query_id)
        if locus not in loci_set:
            continue
        qlen = record.query_length or 0
        aln_len = record.aligned_length or 0
        coverage = aln_len / qlen if qlen else 0.0
        reverse = record.is_reverse
        tstart = record.target_start or 0
        tend = record.target_end or 0
        fragments.append(
            AlleleMatch(
                locus=locus,
                allele_id=allele_id,
                identity=record.identity or 0.0,
                coverage=coverage,
                alignment_length=aln_len,
                score=record.bit_score or 0.0,
                sequence=None,
                strand="-" if reverse else "+",
                query_contig=record.target_id,
                query_start=tstart + 1,
                query_end=tend,
                allele_length=qlen,
                allele_start=(record.query_start or 0) + 1,
                allele_end=record.query_end or 0,
            )
        )
    return fragments


__all__ = ["GseekAligner", "engine", "engine_mode"]
