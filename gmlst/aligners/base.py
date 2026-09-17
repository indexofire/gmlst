"""Core types and Aligner Protocol shared by all backends."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

CallType = Literal["exact", "closest", "novel", "partial", "missing"]


@dataclass
class AlleleMatch:
    """Normalised alignment hit for one allele against one locus.

    All backends must convert their native output into this structure so that
    downstream calling logic is backend-agnostic.
    """

    locus: str
    """Gene name, e.g. ``"abcZ"``."""

    allele_id: str
    """Allele number as a string, e.g. ``"42"``."""

    identity: float
    """Percent identity (0–100)."""

    coverage: float
    """Fraction of the allele sequence covered by the alignment (0.0–1.0)."""

    strand: str = "+"
    """Alignment strand: ``"+"`` or ``"-"``."""

    score: float = 0.0
    """Backend-specific score, normalised to 0–100 where possible."""

    depth: float | None = None
    """Mean read depth across the allele (FASTQ inputs only)."""

    alignment_length: int = 0
    """Length of the alignment block in bases."""

    sequence: str | None = None
    """Extracted sequence for novel alleles (optional)."""
    copy_count: int = 1
    """Approximate number of distinct genomic occurrences for this allele."""
    query_contig: str | None = None
    """Contig/chromosome identifier for FASTA assembly mappings."""
    query_contig_length: int | None = None
    """Contig/chromosome length when available."""
    query_start: int | None = None
    """0-based start coordinate on the query contig/chromosome."""
    query_end: int | None = None
    """0-based end coordinate on the query contig/chromosome."""
    allele_length: int | None = None
    """Allele/template full length when available."""
    allele_start: int | None = None
    """0-based aligned start on allele/template."""
    allele_end: int | None = None
    """0-based aligned end on allele/template."""

    @property
    def call_type(self) -> CallType:
        """Classify this match using tseemann-compatible thresholds."""
        if self.identity == 100.0 and self.coverage >= 1.0:
            return "exact"
        if self.identity >= 95.0 and self.coverage >= 0.95:
            return "closest"
        if self.coverage >= 0.95:
            # Good coverage but low identity → likely a novel allele
            return "novel"
        if self.coverage > 0.0:
            return "partial"
        return "missing"

    @property
    def is_exact(self) -> bool:
        """True only for a perfect, full-length allele match.

        Requires identity of exactly 100.0% and coverage of at least 1.0;
        coverage above 1.0 (alignment longer than the allele) still
        qualifies as exact.
        """
        return self.identity == 100.0 and self.coverage >= 1.0


@dataclass
class AlignmentResult:
    """All allele matches produced by one backend for one sample."""

    sample_id: str
    matches: list[AlleleMatch] = field(default_factory=list)
    failed_loci: list[str] = field(default_factory=list)
    backend: str = ""
    runtime_seconds: float = 0.0
    fragments: list[AlleleMatch] = field(default_factory=list)
    """Raw per-HSP fragment hits (before best-per-(locus, allele) collapse).

    Backends that cannot report fragments simply leave this empty; the
    ``matches`` list semantics are unaffected.
    """
    _matches_by_locus: dict[str, list[AlleleMatch]] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _fragments_by_locus: dict[str, list[AlleleMatch]] | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def matches_for(self, locus: str) -> list[AlleleMatch]:
        """Return all hits for a single locus, sorted best-first."""
        if self._matches_by_locus is None:
            grouped: dict[str, list[AlleleMatch]] = defaultdict(list)
            for match in self.matches:
                grouped[match.locus].append(match)
            for hits in grouped.values():
                hits.sort(
                    key=lambda m: (m.identity, m.coverage, m.depth or 0.0),
                    reverse=True,
                )
            self._matches_by_locus = dict(grouped)
        return self._matches_by_locus.get(locus, [])

    def fragments_for(self, locus: str) -> list[AlleleMatch]:
        """Return all raw fragment HSPs for a single locus, in file order."""
        if self._fragments_by_locus is None:
            grouped: dict[str, list[AlleleMatch]] = defaultdict(list)
            for fragment in self.fragments:
                grouped[fragment.locus].append(fragment)
            self._fragments_by_locus = dict(grouped)
        return self._fragments_by_locus.get(locus, [])


# ---------------------------------------------------------------------------
# Aligner Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Aligner(Protocol):
    """Interface every alignment backend must satisfy.

    Backends are stateless; per-run state lives in ``index_dir``.
    """

    @property
    def name(self) -> str:
        """Short identifier, e.g. ``"blastn"``."""
        ...

    @property
    def supports_fastq(self) -> bool:
        """Whether this backend can handle raw FASTQ reads."""
        ...

    def check_dependencies(self) -> None:
        """Raise ``RuntimeError`` if required external tools are missing."""
        ...

    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
        """Build a backend-specific index from allele FASTA files.

        Parameters
        ----------
        allele_fastas:
            One FASTA file per locus (e.g. ``arcC.tfa``).
        index_dir:
            Directory in which to write index artifacts.

        Returns
        -------
        Path
            The index path (file or directory) to pass back to :meth:`align`.
        """
        ...

    def align(
        self,
        sample: Path | tuple[Path, Path],
        index_path: Path,
        loci: list[str],
        input_type: Literal["fasta", "fastq"],
    ) -> AlignmentResult:
        """Run alignment and return normalised results.

        Parameters
        ----------
        sample:
            Path to query file, or paired FASTQ paths ``(R1, R2)``.
        index_path:
            Path returned by :meth:`index`.
        loci:
            Gene names expected in the scheme (used to detect missing loci).
        input_type:
            ``"fasta"`` for assembled genomes, ``"fastq"`` for raw reads.
        """
        ...


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def split_allele_id(qseqid: str) -> tuple[str, str]:
    """Split ``arcC_1`` → ``("arcC", "1")``.

    Handles both ``_`` and ``-`` separators.
    """
    for sep in ("_", "-"):
        if sep in qseqid:
            locus, allele_id = qseqid.rsplit(sep, 1)
            return locus, allele_id
    return qseqid, "1"


_MAX_FRAGMENTS_PER_LOCUS = 100
"""Upper bound on fragment HSPs kept per locus after parsing."""


def cap_fragments(
    fragments: list[AlleleMatch],
    limit: int = _MAX_FRAGMENTS_PER_LOCUS,
) -> list[AlleleMatch]:
    """Keep at most *limit* fragments per locus, best (identity, length) first.

    Identity leads because imperfect alleles spawn many shifted HSPs that
    are slightly longer than the exact allele's fragments.
    """
    grouped: dict[str, list[AlleleMatch]] = defaultdict(list)
    for fragment in fragments:
        grouped[fragment.locus].append(fragment)
    capped: list[AlleleMatch] = []
    for locus_frags in grouped.values():
        locus_frags.sort(key=lambda f: (f.identity, f.alignment_length), reverse=True)
        capped.extend(locus_frags[:limit])
    return capped


def select_best_matches(rows: list[AlleleMatch]) -> list[AlleleMatch]:
    """Return the best row per (locus, allele_id): identity desc, coverage desc.

    Full ties keep the first-seen row; output follows first-occurrence
    order of each (locus, allele_id) key.
    """
    best: dict[tuple[str, str], AlleleMatch] = {}
    for row in rows:
        key = (row.locus, row.allele_id)
        existing = best.get(key)
        if (
            existing is None
            or row.identity > existing.identity
            or (row.identity == existing.identity and row.coverage > existing.coverage)
        ):
            best[key] = row
    return list(best.values())


def build_alignment_result(
    sample_id: str,
    backend: str,
    matches: list[AlleleMatch],
    fragments: list[AlleleMatch],
    loci: list[str],
    runtime_seconds: float,
) -> AlignmentResult:
    """Assemble an :class:`AlignmentResult` with failed loci derived from *matches*."""
    called_loci = {m.locus for m in matches}
    failed = [loc for loc in loci if loc not in called_loci]
    return AlignmentResult(
        sample_id=sample_id,
        matches=matches,
        failed_loci=failed,
        backend=backend,
        runtime_seconds=runtime_seconds,
        fragments=fragments,
    )
