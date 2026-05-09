from __future__ import annotations

from gmlst.calling.allele import LocusCall


def _low_confidence_loci(locus_calls: dict[str, LocusCall]) -> set[str]:
    low_conf: set[str] = set()
    for locus, call in locus_calls.items():
        if call.multiple_hits or call.call_type in {"novel", "partial", "missing"}:
            low_conf.add(locus)
            continue
        match = call.best_match
        if match is not None and (match.identity < 98.0 or match.coverage < 0.98):
            low_conf.add(locus)
    return low_conf


def _call_rank(call: LocusCall) -> tuple[int, float]:
    priority = {
        "exact": 5,
        "closest": 4,
        "novel": 3,
        "partial": 2,
        "missing": 1,
    }
    return (priority.get(call.call_type, 0), call.confidence)


def _ultrafast_confirmation_rank(call: LocusCall) -> tuple[int, float, float, float]:
    priority = {
        "partial": 0,
        "closest": 1,
        "novel": 2,
        "missing": 3,
        "exact": 4,
    }
    match = call.best_match
    identity = match.identity if match is not None else 0.0
    coverage = match.coverage if match is not None else 0.0
    return (
        priority.get(call.call_type, 5),
        -identity,
        -coverage,
        -call.confidence,
    )


def _ultrafast_second_pass_rank(call: LocusCall) -> tuple[int, float, float]:
    match = call.best_match
    identity = match.identity if match is not None else 0.0
    coverage = match.coverage if match is not None else 0.0
    return (-identity, -coverage, -call.confidence)


def _adaptive_ultrafast_second_pass_budget(locus_calls: dict[str, LocusCall]) -> int:
    candidate_count = sum(
        1 for call in locus_calls.values() if call.call_type in {"partial", "closest"}
    )
    if candidate_count <= 0:
        return 0
    if candidate_count <= 40:
        return candidate_count
    if candidate_count <= 120:
        return 40
    if candidate_count <= 300:
        return 60
    return 80
