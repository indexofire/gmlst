from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from heapq import nsmallest

_BASE_BITS = {ord("A"): 0, ord("C"): 1, ord("G"): 2, ord("T"): 3}


def prefilter_assembly_candidates(
    *,
    allele_sequences: dict[tuple[str, str], str],
    assembly_sequences: Iterable[str],
    k: int,
    top_n: int,
    stride: int = 1,
) -> dict[str, list[tuple[str, float]]]:
    if k <= 0:
        raise ValueError("k must be positive")
    if top_n <= 0:
        raise ValueError("top_n must be positive")
    if stride <= 0:
        raise ValueError("stride must be positive")

    kmer_index: dict[int, set[tuple[str, str]]] = defaultdict(set)
    for (locus, allele_id), sequence in allele_sequences.items():
        unique_kmers = set(
            _iter_canonical_kmer_codes(sequence.upper(), k, stride=stride)
        )
        if not unique_kmers:
            continue
        for kmer in unique_kmers:
            kmer_index[kmer].add((locus, allele_id))

    per_locus_scores: dict[str, dict[str, float]] = defaultdict(dict)

    for sequence in assembly_sequences:
        seen_per_contig: set[int] = set()
        kmer_index_get = kmer_index.get
        for kmer in _iter_canonical_kmer_codes(sequence.upper(), k, stride=stride):
            if kmer in seen_per_contig:
                continue
            seen_per_contig.add(kmer)
            targets = kmer_index_get(kmer)
            if not targets:
                continue
            weight = 1.0 / float(len(targets))
            for locus, allele_id in targets:
                locus_scores = per_locus_scores[locus]
                locus_scores[allele_id] = locus_scores.get(allele_id, 0.0) + weight

    results: dict[str, list[tuple[str, float]]] = {}
    for locus, allele_scores in per_locus_scores.items():
        ranked = nsmallest(
            top_n,
            allele_scores.items(),
            key=lambda item: (-item[1], _allele_sort_key(item[0])),
        )
        results[locus] = ranked
    return results


def _iter_canonical_kmer_codes(seq: str, k: int, stride: int = 1) -> Iterable[int]:
    if len(seq) < k:
        return
    seq_bytes = seq.encode("ascii")
    mask = (1 << (2 * k)) - 1
    rc_shift = 2 * (k - 1)
    fwd_code = 0
    rc_code = 0
    valid = 0

    for idx, base in enumerate(seq_bytes):
        bits = _BASE_BITS.get(base)
        if bits is None:
            fwd_code = 0
            rc_code = 0
            valid = 0
            continue

        fwd_code = ((fwd_code << 2) | bits) & mask
        rc_code = (rc_code >> 2) | ((bits ^ 0b11) << rc_shift)
        valid += 1
        if valid >= k and (idx - k + 1) % stride == 0:
            yield fwd_code if fwd_code <= rc_code else rc_code


def _allele_sort_key(allele_id: str) -> tuple[int, int | str]:
    if allele_id.isdigit():
        return (0, int(allele_id))
    return (1, allele_id)
