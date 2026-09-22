"""Species identification from genome k-mer fingerprints.

A fingerprint is the set of canonical k-mer codes (same rolling hash as
:mod:`gmlst.kmer_prefilter`) sampled from one species' smallest MLST
scheme. A query genome is sketched the same way and scored by
containment — ``|query ∩ fingerprint| / |fingerprint|`` — because the
genome sketch is huge and noisy while the fingerprint is the reference.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gmlst.core.sequences import (
    load_scheme_allele_sequences_impl,
    split_allele_header_impl,
)
from gmlst.database.atomic import atomic_write_text
from gmlst.database.cache import DatabaseCache
from gmlst.fasta_io import iter_fasta_records
from gmlst.kmer_prefilter import _iter_canonical_kmer_codes

FINGERPRINT_K = 21
FINGERPRINT_SAMPLE_RATE = 7
FINGERPRINTS_FILENAME = "species_fingerprints.json"

# Cap on allele sequences sketched per scheme: one allele per locus, at
# most this many loci.
MAX_SCHEME_SEQUENCES = 2000
# Cap on genome bases read for one detection query.
GENOME_SKETCH_CAP_BP = 5_000_000

# Detection thresholds: an organism is only a confident winner above the
# minimum score AND with a clear margin over the runner-up.
DETECT_MIN_CONTAINMENT = 0.05
DETECT_MIN_TOP_SCORE = 0.3
DETECT_MARGIN_FACTOR = 2.0

ProgressCb = Callable[[str, str], None]


def sketch_sequence(
    seq: str, *, k: int = FINGERPRINT_K, sample_rate: int = FINGERPRINT_SAMPLE_RATE
) -> set[int]:
    """Return a deterministic sample of *seq*'s canonical k-mer codes.

    Sampling keeps k-mers whose code is divisible by *sample_rate* — a
    value-based rule, so a subsequence and its containing genome sample
    the same k-mer subset regardless of genomic offset (positional
    strides would break containment scoring). K-mers containing non-ACGT
    characters are skipped by the underlying rolling hash.
    """
    if k <= 0:
        raise ValueError("k must be positive")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    return {
        code
        for code in _iter_canonical_kmer_codes(seq.upper(), k, stride=1)
        if code % sample_rate == 0
    }


def sketch_fasta_sample(
    path: Path,
    *,
    cap_bp: int = GENOME_SKETCH_CAP_BP,
    k: int = FINGERPRINT_K,
    sample_rate: int = FINGERPRINT_SAMPLE_RATE,
) -> set[int]:
    """Sketch FASTA records from *path* until *cap_bp* bases were read."""
    hashes: set[int] = set()
    total_bp = 0
    for _header, sequence in iter_fasta_records(path):
        hashes |= sketch_sequence(sequence, k=k, sample_rate=sample_rate)
        total_bp += len(sequence)
        if total_bp >= cap_bp:
            break
    return hashes


def detect_species(
    query_hashes: set[int], fingerprints: list[dict[str, Any]]
) -> list[tuple[str, float]]:
    """Rank organisms by containment of their fingerprint in the query.

    Returns ``(organism, score)`` pairs with score above
    :data:`DETECT_MIN_CONTAINMENT`, sorted by descending score then
    organism name for determinism.
    """
    ranked: list[tuple[str, float]] = []
    for fingerprint in fingerprints:
        organism = str(fingerprint.get("organism", ""))
        hashes = fingerprint.get("hashes") or []
        if not organism or not hashes:
            continue
        reference = set(hashes)
        score = len(query_hashes & reference) / len(reference)
        if score > DETECT_MIN_CONTAINMENT:
            ranked.append((organism, score))
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked


def is_unique_detection(ranked: list[tuple[str, float]]) -> bool:
    """Apply the detection margin rule to a ranked organism list.

    The winner is unique when its score reaches :data:`DETECT_MIN_TOP_SCORE`
    and is at least :data:`DETECT_MARGIN_FACTOR` times the runner-up's.
    """
    if not ranked:
        return False
    top_score = ranked[0][1]
    if top_score < DETECT_MIN_TOP_SCORE:
        return False
    if len(ranked) == 1:
        return True
    return top_score >= DETECT_MARGIN_FACTOR * ranked[1][1]


def schemes_for_organism(
    cache: DatabaseCache,
    organism: str,
    scheme_types: set[str],
) -> list[dict[str, Any]]:
    """Return catalog rows whose organism matches *organism* exactly
    (case-insensitive) and whose type is in *scheme_types*, sorted by
    locus count then scheme name. Blocked schemes are excluded."""
    from gmlst.database.cache import _load_blocked_schemes
    from gmlst.database.providers import AVAILABLE_PROVIDERS

    target = organism.strip().lower()
    types = {scheme_type.lower() for scheme_type in scheme_types}
    blocked = _load_blocked_schemes()
    rows: list[dict[str, Any]] = []
    for provider in AVAILABLE_PROVIDERS:
        catalog = cache.load_catalog(provider)
        if not catalog:
            continue
        provider_blocked = blocked.get(provider, set())
        for item in catalog:
            if str(item.get("organism", "")).strip().lower() != target:
                continue
            if str(item.get("scheme_type", "")).lower() not in types:
                continue
            if item.get("scheme_name") in provider_blocked:
                continue
            if item.get("extra", {}).get("directory", "") in provider_blocked:
                continue
            row = dict(item)
            row.setdefault("provider", provider)
            rows.append(row)
    rows.sort(
        key=lambda row: (int(row.get("n_loci") or 0), str(row.get("scheme_name")))
    )
    return rows


def fingerprints_path(cache: DatabaseCache) -> Path:
    """Return the fingerprints file location inside the cache root."""
    return cache.root / FINGERPRINTS_FILENAME


def save_fingerprints(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(payload, separators=(",", ":")))


def load_fingerprints(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def build_fingerprints(
    cache: DatabaseCache,
    *,
    organisms: set[str] | None = None,
    max_connections: int | None = None,
    progress_cb: ProgressCb | None = None,
) -> dict[str, Any]:
    """Build one fingerprint per catalog organism.

    Each organism is sketched from its smallest MLST-type scheme (falling
    back to its smallest cgMLST scheme for cgMLST-only species); the
    source scheme is downloaded via ``cache.ensure_scheme`` when needed.
    Failures for one organism skip that organism without aborting the
    build. ``progress_cb(event, detail)`` observes the build: ``total``,
    ``download``, ``sketch``, and ``skip`` events.
    """

    def emit(event: str, detail: str) -> None:
        if progress_cb is not None:
            progress_cb(event, detail)

    groups = _catalog_schemes_by_organism(cache, organisms)
    emit("total", str(len(groups)))

    fingerprints: list[dict[str, Any]] = []
    for organism in sorted(groups):
        source = _select_source_scheme(groups[organism])
        if source is None:
            emit("skip", f"{organism}: no mlst/cgmlst scheme in catalog")
            continue
        name = str(source["scheme_name"])
        provider = str(source.get("provider", "pubmlst"))
        scheme_type = str(source.get("scheme_type", "mlst")).lower() or "mlst"
        try:
            if not cache.is_downloaded(name, provider):
                emit("download", f"{name} ({provider})")
            scheme = cache.ensure_scheme(
                name,
                provider=provider,
                scheme_type=scheme_type,
                max_connections=max_connections,
            )
            hashes = _sketch_scheme(scheme)
        except Exception as exc:
            emit("skip", f"{organism}: {name}: {exc}")
            continue
        if not hashes:
            emit("skip", f"{organism}: {name}: no allele sequences")
            continue
        fingerprints.append(
            {
                "organism": organism,
                "k": FINGERPRINT_K,
                "sample_rate": FINGERPRINT_SAMPLE_RATE,
                "hashes": sorted(hashes),
                "source_scheme": name,
            }
        )
        emit("sketch", organism)

    return {
        "version": 1,
        "k": FINGERPRINT_K,
        "sample_rate": FINGERPRINT_SAMPLE_RATE,
        "fingerprints": fingerprints,
    }


def _catalog_schemes_by_organism(
    cache: DatabaseCache,
    organisms: set[str] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Group catalog rows from every provider by exact organism field.

    Blocked schemes (hidden from ``scheme list``) are excluded so
    fingerprint sources stay downloadable through the regular commands.
    """
    from gmlst.database.cache import _load_blocked_schemes
    from gmlst.database.providers import AVAILABLE_PROVIDERS

    blocked = _load_blocked_schemes()
    wanted = {o.strip().lower() for o in organisms} if organisms else None
    groups: dict[str, list[dict[str, Any]]] = {}
    for provider in AVAILABLE_PROVIDERS:
        catalog = cache.load_catalog(provider)
        if not catalog:
            continue
        provider_blocked = blocked.get(provider, set())
        for item in catalog:
            organism = str(item.get("organism", "")).strip()
            if not organism:
                continue
            if wanted is not None and organism.lower() not in wanted:
                continue
            row = dict(item)
            row.setdefault("provider", provider)
            if row["scheme_name"] in provider_blocked:
                continue
            if row.get("extra", {}).get("directory", "") in provider_blocked:
                continue
            groups.setdefault(organism, []).append(row)
    return groups


def _select_source_scheme(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the smallest MLST scheme, else the smallest cgMLST scheme.

    Smallest = ``min(n_loci, scheme_name)``; organisms with neither an
    MLST nor a cgMLST scheme are skipped by the caller.
    """

    def sort_key(row: dict[str, Any]) -> tuple[int, str]:
        return (int(row.get("n_loci") or 0), str(row.get("scheme_name", "")))

    for scheme_type in ("mlst", "cgmlst"):
        typed = [
            row
            for row in rows
            if str(row.get("scheme_type", "")).lower() == scheme_type
        ]
        if typed:
            return min(typed, key=sort_key)
    return None


def _sketch_scheme(
    scheme: Any, *, max_sequences: int = MAX_SCHEME_SEQUENCES
) -> set[int]:
    """Sketch the first allele of each locus, capped at *max_sequences*
    sequences per scheme.

    One allele per locus keeps the fingerprint a compact species signal:
    containment scoring measures how much of the reference fingerprint a
    query genome carries, and a single genome carries only one allele of
    each housekeeping gene.
    """
    allele_files = getattr(scheme, "allele_files", None) or {}
    if not allele_files:
        return set()
    allele_sequences = load_scheme_allele_sequences_impl(
        allele_files,
        split_allele_header_fn=split_allele_header_impl,
        max_per_locus=1,
    )
    hashes: set[int] = set()
    for locus_sequences in list(allele_sequences.values())[:max_sequences]:
        for sequence in locus_sequences.values():
            hashes |= sketch_sequence(sequence)
            break
    return hashes
