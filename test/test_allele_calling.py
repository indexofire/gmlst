"""Regression tests for best-allele ranking."""

from __future__ import annotations

from gmlst.aligners.base import AlleleMatch
from gmlst.calling.allele import call_best_allele


def _match(
    allele_id: str,
    *,
    identity: float,
    coverage: float,
    score: float,
    alignment_length: int,
) -> AlleleMatch:
    return AlleleMatch(
        locus="gltA",
        allele_id=allele_id,
        identity=identity,
        coverage=coverage,
        score=score,
        alignment_length=alignment_length,
    )


def test_exact_match_beats_longer_imperfect_hit_with_higher_bitscore() -> None:
    """A longer, near-match allele must not outrank a full-length exact hit.

    Mirrors the Campylobacter gltA case: allele 901 is 477 bp and aligns over
    481 bp at 95.842% identity (bitscore 771), while allele 291 is a 402 bp
    full-length exact match (bitscore 743).
    """
    exact = _match(
        "291",
        identity=100.0,
        coverage=1.0,
        score=743.0,
        alignment_length=402,
    )
    longer = _match(
        "901",
        identity=95.842,
        coverage=481 / 477,
        score=771.0,
        alignment_length=481,
    )

    call = call_best_allele(
        [longer, exact],
        min_identity=95.0,
        min_coverage=0.95,
    )

    assert call.allele_id == "291"
    assert call.call_type == "exact"
