"""Index/prefilter adapter layer binding sequence and index implementations.

Thin wrappers that re-export the dependency-injected implementations from
:mod:`gmlst.core.indexing`, :mod:`gmlst.core.prefilter`, and
:mod:`gmlst.core.sequences` with concrete ordering keys, hashers, and
loggers wired in, so :mod:`gmlst.core` faces no import cycle when calling
them during cgMLST index building and representative prefilters.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from gmlst.aligners.base import AlignmentResult
from gmlst.core import indexing as _indexing
from gmlst.core import prefilter as _prefilter
from gmlst.core import sequences as _sequences
from gmlst.core.types import CgmlstModeOverrides

logger = logging.getLogger(__name__)


def ensure_full_index_impl(
    *,
    aligner,
    backend: str,
    scheme_name: str,
    allele_fastas: list[Path],
    index_dir: Path,
    force_reindex: bool,
) -> Path:
    """Return a reusable full-scheme index, rebuilding only when stale."""
    return _indexing.ensure_full_index_impl(
        aligner=aligner,
        backend=backend,
        scheme_name=scheme_name,
        allele_fastas=allele_fastas,
        index_dir=index_dir,
        force_reindex=force_reindex,
        logger=logger,
        index_is_empty_fn=_indexing.index_is_empty_impl,
        purge_backend_index_fn=_indexing.purge_backend_index_impl,
        find_index_fn=_indexing.find_index_impl,
        is_index_stale_fn=_indexing.is_index_stale_impl,
    )


def load_scheme_allele_sequences_impl(
    allele_files: dict[str, Path],
    max_per_locus: int = 0,
) -> dict[str, dict[str, str]]:
    """Load per-locus allele sequences, optionally capped per locus."""
    return _sequences.load_scheme_allele_sequences_impl(
        allele_files,
        split_allele_header_fn=_sequences.split_allele_header_impl,
        max_per_locus=max_per_locus,
    )


def load_representative_allele_sequences_impl(
    allele_files: dict[str, Path],
) -> dict[tuple[str, str], str]:
    """Stream allele FASTAs and keep the lowest-ordered allele per locus."""
    return _sequences.load_representative_allele_sequences_impl(
        allele_files,
        split_allele_header_fn=_sequences.split_allele_header_impl,
        allele_order_key_fn=_prefilter.allele_order_key_impl,
    )


def representatives_from_nested_alleles_impl(
    allele_sequences: dict[str, dict[str, str]],
) -> dict[tuple[str, str], str]:
    """Pick the lowest-ordered allele per locus from in-memory sequences."""
    return _sequences.representatives_from_nested_alleles_impl(
        allele_sequences,
        allele_order_key_fn=_prefilter.allele_order_key_impl,
    )


def load_or_build_minimap2_representative_index_impl(
    *,
    aligner,
    index_dir: Path,
    representatives: dict[tuple[str, str], str],
    force_reindex: bool,
) -> Path:
    """Load or rebuild the persistent minimap2 representative-allele index."""
    return _indexing.load_or_build_minimap2_representative_index_impl(
        aligner=aligner,
        index_dir=index_dir,
        representatives=representatives,
        force_reindex=force_reindex,
        representative_fingerprint_fn=_indexing.representative_fingerprint_impl,
        is_index_stale_fn=_indexing.is_index_stale_impl,
        purge_backend_index_fn=_indexing.purge_backend_index_impl,
        allele_order_key_fn=_prefilter.allele_order_key_impl,
        logger=logger,
    )


def representative_fingerprint_impl(
    representatives: dict[tuple[str, str], str],
) -> str:
    """Hash the sorted representative set for index staleness checks."""
    return _indexing.representative_fingerprint_impl(
        representatives,
        allele_order_key_fn=_prefilter.allele_order_key_impl,
        hasher=hashlib.sha256(),
    )


def write_candidate_fastas_impl(
    allele_sequences: dict[str, dict[str, str]],
    candidates: dict[str, list[tuple[str, float]]],
    out_dir: Path,
) -> list[Path]:
    """Write one ``<locus>.tfa`` per locus containing its candidate alleles."""
    return _sequences.write_candidate_fastas_impl(
        allele_sequences,
        candidates,
        out_dir,
    )


def representative_alleles_impl(
    allele_sequences: dict[tuple[str, str], str],
) -> dict[tuple[str, str], str]:
    """Keep one (lowest-ordered) allele per locus from a flat mapping."""
    return _prefilter.representative_alleles_impl(
        allele_sequences,
        allele_order_key_fn=_prefilter.allele_order_key_impl,
    )


def minimap2_representative_prefilter_candidates_impl(
    *,
    aligner,
    sample_path: Path,
    loci: list[str],
    representatives: dict[tuple[str, str], str],
    representative_index_path: Path | None,
    min_identity: float,
    min_coverage: float,
) -> tuple[dict[str, list[tuple[str, float]]], AlignmentResult | None]:
    """Align against the representative index to shortlist candidate loci.

    Returns the per-locus best ``(allele_id, score)`` candidates plus the
    representative alignment itself (reused as the main alignment in
    ultrafast representative-only mode).
    """
    return _prefilter.minimap2_representative_prefilter_candidates_impl(
        aligner=aligner,
        sample_path=sample_path,
        loci=loci,
        representatives=representatives,
        representative_index_path=representative_index_path,
        min_identity=min_identity,
        min_coverage=min_coverage,
    )


def cgmlst_mode_overrides_impl(
    *,
    cgmlst_mode: str,
    scheme_type: str,
    backend: str,
) -> CgmlstModeOverrides:
    """Compute mode-specific pipeline overrides (fast/ultrafast/balanced)."""
    return _prefilter.cgmlst_mode_overrides_impl(
        cgmlst_mode=cgmlst_mode,
        scheme_type=scheme_type,
        backend=backend,
        logger=logger,
    )
