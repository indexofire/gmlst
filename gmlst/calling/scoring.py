"""Quality scoring for MLST typing results.

Every sample gets a continuous 0-100 score — the mean of per-locus
scores over all scheme loci, so missing loci dilute the aggregate — plus
a tseemann/mlst-style status code (PERFECT / NOVEL / MIXED / MISSING /
BAD / NONE / OK).

Per-locus scoring reuses the caller's existing continuous confidence
(:attr:`LocusCall.confidence`, 0-1) so the score reflects identity,
coverage, and depth evidence. Exact calls score 100; conflicting
multi-copy loci score 0; missing loci score 0.

Unlike the historical ``calling/confidence.py`` (geometric mean, never
wired into any output and removed as dead code in v0.3.1), these scores
are additive means and are emitted in the JSON payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gmlst.calling.allele import LocusCall
    from gmlst.calling.st_lookup import STResult

#: Aggregate scores below this value yield status ``BAD``.
BAD_SCORE_THRESHOLD = 50.0

STATUS_PERFECT = "PERFECT"
STATUS_NOVEL = "NOVEL"
STATUS_MIXED = "MIXED"
STATUS_MISSING = "MISSING"
STATUS_BAD = "BAD"
STATUS_NONE = "NONE"
STATUS_OK = "OK"


@dataclass(frozen=True)
class SampleScore:
    """Aggregate quality assessment for one typed sample."""

    score: float
    status: str


def locus_score(call: LocusCall | None) -> float:
    """Score one locus call on a 0-100 scale.

    * exact call → 100 (evidence-independent by definition)
    * conflicting multi-copy → 0 (profile ambiguous)
    * missing / absent → 0
    * closest / novel / partial → the caller's 0-1 confidence × 100
    """
    if call is None or call.call_type == "missing":
        return 0.0
    if call.multiple_hits:
        return 0.0
    if call.call_type == "exact":
        return 100.0
    confidence = min(max(call.confidence, 0.0), 1.0)
    return round(confidence * 100.0, 1)


def sample_score(result: STResult) -> float:
    """Return the mean per-locus score over all loci in *result*."""
    if not result.locus_calls:
        return 0.0
    total = sum(locus_score(call) for call in result.locus_calls.values())
    return round(total / len(result.locus_calls), 1)


def sample_status(result: STResult, score: float) -> str:
    """Classify *result* into a tseemann/mlst-style status code.

    Precedence: NONE → MIXED → PERFECT → BAD → NOVEL → MISSING → OK.
    """
    if not result.locus_calls:
        return STATUS_NONE
    if result.has_conflicting_multicopy:
        return STATUS_MIXED
    if not result.is_novel and result.st is not None:
        return STATUS_PERFECT
    if score < BAD_SCORE_THRESHOLD:
        return STATUS_BAD
    if result.is_complete:
        return STATUS_NOVEL
    if any(
        call.call_type in ("missing", "partial") for call in result.locus_calls.values()
    ):
        return STATUS_MISSING
    return STATUS_OK


def score_result(result: STResult) -> SampleScore:
    """Return the aggregate score and status for one sample."""
    score = sample_score(result)
    return SampleScore(score=score, status=sample_status(result, score))


def passes_minscore(result: STResult, minscore: float) -> bool:
    """Return True when *result*'s aggregate score is at least *minscore*."""
    return sample_score(result) >= minscore
