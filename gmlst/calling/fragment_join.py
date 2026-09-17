"""Multi-fragment joint allele reconstruction.

When a gene is split across assembly contigs, no single HSP covers the full
allele and the locus degrades to a partial call.  This module inspects the
raw fragment HSPs for one locus and, when they are consistent, produces
joint evidence:

* ``reconstructed`` — the fragments overlap on the allele with exactly
  agreeing sequence, so they can be tiled into one synthetic full-length
  match that re-enters the normal calling pipeline (possibly yielding an
  exact call).
* ``joint`` — the fragments are disjoint; only the combined coverage is
  reported to upgrade the partial call.

All coordinate math is in ALLELE coordinates; fragment sequences are
allele-oriented by construction (blastn ``sseq`` natively, minimap2 slices
reverse-complemented by the parser), so this module never re-orients
sequences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from gmlst.aligners.base import AlleleMatch

JoinKind = Literal["reconstructed", "joint"]

_MAX_JOIN_FRAGMENTS = 3

# Overlaps shorter than this are treated as disjoint: a junction insertion
# whose prefix happens to extend the allele match can fabricate a tiny
# overlap and must not trigger reconstruction (soundness rule).
_MIN_JOIN_OVERLAP = 10


@dataclass
class JoinedEvidence:
    """Outcome of attempting to join the fragments of one locus."""

    kind: JoinKind
    allele_id: str
    strand: str
    joint_coverage: float
    """Union of fragment allele intervals / allele length."""
    synthetic: AlleleMatch | None = None
    """Tiled reconstruction; only for ``kind == "reconstructed"``."""
    template: AlleleMatch | None = None
    """Strongest member fragment; basis for ``kind == "joint"`` partial calls."""
    fragment_coords: list[dict[str, object]] = field(default_factory=list)
    """Per-fragment placement: ``{contig, allele_start, allele_end}``."""


@dataclass
class _Frag:
    """Fragment with resolved (non-None) coordinates and sequence."""

    match: AlleleMatch
    start: int
    end: int
    allele_length: int
    seq: str


def join_locus_fragments(
    fragments: list[AlleleMatch],
    *,
    min_identity: float,
    min_coverage: float,
    min_join_overlap: int = _MIN_JOIN_OVERLAP,
) -> JoinedEvidence | None:
    """Attempt to join fragment HSPs of one locus into joint evidence.

    Returns ``None`` when no convincing join exists (too few/too many
    fragments, below-identity hits, chimeric evidence for two different
    alleles, or sequence disagreement in an overlap).
    """
    usable = [
        _Frag(
            match=frag,
            start=frag.allele_start,
            end=frag.allele_end,
            allele_length=frag.allele_length,
            seq=(frag.sequence or "").upper(),
        )
        for frag in fragments
        if frag.identity >= min_identity
        and frag.sequence
        and frag.allele_start is not None
        and frag.allele_end is not None
        and frag.allele_length
        and frag.allele_end > frag.allele_start
    ]
    if not usable:
        return None

    groups: dict[tuple[str, str], list[_Frag]] = {}
    for frag in usable:
        groups.setdefault((frag.match.allele_id, frag.match.strand), []).append(frag)

    joinable = [
        sorted(group, key=lambda f: f.start)
        for group in groups.values()
        if 2 <= len(group) <= _MAX_JOIN_FRAGMENTS
    ]
    if not joinable:
        return None

    def strength(group: list[_Frag]) -> tuple[float, float]:
        return (
            _union_len(group) / group[0].allele_length,
            min(f.match.identity for f in group),
        )

    joinable.sort(key=strength, reverse=True)
    best = joinable[0]
    if len(joinable) > 1 and strength(joinable[1]) == strength(best):
        # Chimeric guard: equally strong evidence for another (allele, strand).
        return None

    allele_length = best[0].allele_length
    joint_coverage = _union_len(best) / allele_length
    if joint_coverage < min_coverage * 0.5:
        return None
    coords = [
        {
            "contig": frag.match.query_contig,
            "allele_start": frag.start,
            "allele_end": frag.end,
        }
        for frag in best
    ]

    if not _chains(best, min_join_overlap):
        # Disjoint fragments can never support an exact call: an indel at the
        # unsampled junction is invisible, so only joint coverage is reported
        # (soundness rule).
        template = max(best, key=lambda f: (f.match.identity, f.match.coverage))
        return JoinedEvidence(
            kind="joint",
            allele_id=best[0].match.allele_id,
            strand=best[0].match.strand,
            joint_coverage=joint_coverage,
            template=template.match,
            fragment_coords=coords,
        )

    tiled = _tile(best)
    if tiled is None:
        return None

    sequence, weighted_identity, span = tiled
    synthetic = AlleleMatch(
        locus=best[0].match.locus,
        allele_id=best[0].match.allele_id,
        identity=weighted_identity,
        coverage=span / allele_length,
        strand=best[0].match.strand,
        score=sum(f.match.score for f in best),
        alignment_length=span,
        sequence=sequence,
        allele_length=allele_length,
        allele_start=best[0].start,
        allele_end=max(f.end for f in best),
    )
    return JoinedEvidence(
        kind="reconstructed",
        allele_id=best[0].match.allele_id,
        strand=best[0].match.strand,
        joint_coverage=joint_coverage,
        synthetic=synthetic,
        fragment_coords=coords,
    )


def _union_len(sorted_group: list[_Frag]) -> int:
    """Total length of the union of allele intervals (gaps excluded)."""
    total = 0
    reach = -1
    for frag in sorted_group:
        total += max(0, frag.end - max(frag.start, reach))
        reach = max(reach, frag.end)
    return total


def _chains(sorted_group: list[_Frag], min_join_overlap: int) -> bool:
    """True when fragments overlap the running union enough to tile.

    Each later fragment must overlap the union of all earlier ones
    (``cursor`` = max end so far) by at least ``min_join_overlap`` bases;
    a fully contained middle fragment still chains.
    """
    cursor = sorted_group[0].end
    for frag in sorted_group[1:]:
        if min(frag.end, cursor) - frag.start < max(min_join_overlap, 1):
            return False
        cursor = max(cursor, frag.end)
    return True


def _tile(sorted_group: list[_Frag]) -> tuple[str, float, int] | None:
    """Tile overlapping fragments into one sequence.

    Returns ``(sequence, length-weighted identity, span)``, or ``None`` when
    the fragments disagree over any shared allele interval.  Each fragment's
    sequence is assumed to cover exactly ``[start, end)`` in allele
    coordinates (true for gapless blocks; gapped blocks fail verification
    conservatively).
    """
    sequence = sorted_group[0].seq
    group_start = sorted_group[0].start
    cursor = sorted_group[0].end
    contributed = cursor - group_start
    weighted_identity = sorted_group[0].match.identity * contributed
    total = contributed
    for frag in sorted_group[1:]:
        shared = min(frag.end, cursor) - frag.start
        if shared < 0:
            return None
        if shared > 0:
            offset = frag.start - group_start
            if frag.seq[:shared] != sequence[offset : offset + shared]:
                return None
        sequence += frag.seq[shared:]
        fresh = max(0, frag.end - max(frag.start, cursor))
        weighted_identity += frag.match.identity * fresh
        total += fresh
        cursor = max(cursor, frag.end)
    span = cursor - group_start
    identity = weighted_identity / total if total else 0.0
    return sequence, identity, span
