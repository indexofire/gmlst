"""Best-allele selection logic per locus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from gmlst.aligners.base import AlignmentResult, AlleleMatch

CallType = Literal["exact", "closest", "novel", "partial", "missing"]

# Default thresholds — match tseemann/mlst defaults
MIN_IDENTITY: float = 95.0
MIN_COVERAGE: float = 0.95
MIN_DEPTH: float = 10.0  # for FASTQ only


@dataclass
class LocusCall:
    """Result of calling one locus from alignment hits."""

    locus: str
    allele_id: str | None
    call_type: CallType
    confidence: float  # 0.0 – 1.0
    best_match: AlleleMatch | None = None
    multiple_hits: bool = False
    """True when ≥2 alleles passed thresholds (possible paralog)."""
    allele_ids: list[str] = field(default_factory=list)
    """All distinct allele IDs passing thresholds for this locus."""
    copy_count: int = 1
    novel_sequence: str | None = None
    """Extracted sequence when call_type is 'novel'."""


def call_best_allele(
    matches: list[AlleleMatch],
    *,
    min_identity: float = MIN_IDENTITY,
    min_coverage: float = MIN_COVERAGE,
    min_depth: float = MIN_DEPTH,
) -> LocusCall:
    """Select the best allele from a list of hits for one locus.

    Parameters
    ----------
    matches:
        All :class:`AlleleMatch` objects for a single locus, any order.
    min_identity:
        Minimum percent identity threshold (default 95 %).
    min_coverage:
        Minimum allele coverage fraction threshold (default 0.95).
    min_depth:
        Minimum mean read depth for FASTQ inputs (ignored when depth is None).

    Returns
    -------
    LocusCall
        The best call for this locus.
    """
    if not matches:
        return LocusCall(
            locus="",
            allele_id=None,
            call_type="missing",
            confidence=0.0,
        )

    locus = matches[0].locus

    # Filter by identity and coverage thresholds
    valid: list[AlleleMatch] = []
    for m in matches:
        if m.identity < min_identity:
            continue
        if m.coverage < min_coverage:
            continue
        if m.depth is not None and m.depth < min_depth:
            continue
        valid.append(m)

    if not valid:
        # Check whether anything came close (partial coverage)
        if matches and max(m.coverage for m in matches) >= min_coverage * 0.5:
            best = _rank_matches(matches)[0]
            return LocusCall(
                locus=locus,
                allele_id=best.allele_id,
                call_type="partial",
                confidence=_confidence(best),
                best_match=best,
                allele_ids=[best.allele_id],
                copy_count=best.copy_count,
            )
        return LocusCall(
            locus=locus,
            allele_id=None,
            call_type="missing",
            confidence=0.0,
        )

    ranked = _rank_matches(valid)
    best = ranked[0]
    exact_hits = [m for m in ranked if m.identity == 100.0 and m.coverage >= 1.0]
    unique_alleles = list(dict.fromkeys(m.allele_id for m in exact_hits))
    multiple = len(unique_alleles) > 1

    call_type: CallType = best.call_type  # type: ignore[assignment]
    if call_type not in ("exact", "closest", "novel", "partial", "missing"):
        call_type = "closest"
    if call_type == "closest" and best.identity == 100.0 and best.coverage < 1.0:
        call_type = "partial"

    # Extract sequence for novel alleles
    novel_sequence = None
    if call_type == "novel" and hasattr(best, "sequence") and best.sequence:
        novel_sequence = best.sequence.replace("-", "")  # Remove gaps

    return LocusCall(
        locus=locus,
        allele_id=best.allele_id,
        call_type=call_type,
        confidence=_confidence(best),
        best_match=best,
        multiple_hits=multiple,
        allele_ids=unique_alleles,
        copy_count=best.copy_count,
        novel_sequence=novel_sequence,
    )


def call_all_loci(
    result: AlignmentResult,
    loci: list[str],
    **thresholds,
) -> dict[str, LocusCall]:
    """Call every locus in *loci* from an :class:`AlignmentResult`.

    Returns
    -------
    dict[str, LocusCall]
        Mapping from locus name to its :class:`LocusCall`.
    """
    calls: dict[str, LocusCall] = {}
    for locus in loci:
        hits = result.matches_for(locus)
        locus_call = call_best_allele(hits, **thresholds)
        if not locus_call.locus:
            locus_call = LocusCall(
                locus=locus,
                allele_id=None,
                call_type="missing",
                confidence=0.0,
            )
        calls[locus] = locus_call
    return calls


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _rank_matches(matches: list[AlleleMatch]) -> list[AlleleMatch]:
    """Sort matches best-first by (identity, coverage, depth)."""
    return sorted(
        matches,
        key=lambda m: (m.score, m.coverage, m.identity, m.depth or 0.0),
        reverse=True,
    )


def _confidence(match: AlleleMatch) -> float:
    """Compute a 0–1 confidence score for a single match.

    Combines identity, coverage, and (optionally) depth.
    """
    base = (match.identity / 100.0) * match.coverage
    if match.depth is not None:
        # Saturate depth contribution at 30×; very high depth slightly penalised
        depth_factor = min(match.depth / 30.0, 1.0)
        if match.depth > 300:
            depth_factor *= 0.9  # possible contamination flag
        return base * depth_factor
    return base
