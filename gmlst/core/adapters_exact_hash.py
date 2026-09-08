"""Exact-hash adapter layer binding ``exact_hash.py`` to concrete helpers.

Thin wrappers that re-export the dependency-injected implementations from
:mod:`gmlst.core.exact_hash` with the CDS predictor, ``AlleleMatch`` class,
and per-adapter caching chain wired in, breaking the import cycle between
:mod:`gmlst.core` and the implementation modules.
"""

from __future__ import annotations

import logging
from pathlib import Path

from gmlst.aligners.base import AlleleMatch

from . import cds as _cds
from . import exact_hash as _exact_hash

logger = logging.getLogger(__name__)


def load_or_build_exact_hash_indexes_impl(
    *,
    allele_files: dict[str, Path],
    allele_sequences: dict[str, dict[str, str]],
) -> dict[str, list[tuple[str, str]]]:
    """Load the cached scheme hash index or rebuild and persist it."""
    return _exact_hash.load_or_build_exact_hash_indexes_impl(
        allele_files=allele_files,
        allele_sequences=allele_sequences,
        scheme_precomputed_dir_fn=_exact_hash.scheme_precomputed_dir_impl,
        allele_files_fingerprint_fn=_exact_hash.allele_files_fingerprint_impl,
        build_allele_hash_index_fn=_exact_hash.build_allele_hash_index_impl,
        logger=logger,
    )


def resolve_exact_cds_matches_impl(
    sample_path: Path,
    hash_index: dict[str, list[tuple[str, str]]],
    *,
    sample_cache_root: Path | None = None,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
) -> dict[str, object]:
    """Resolve unambiguous exact allele matches via cached sample CDS hashes."""
    return _exact_hash.resolve_exact_cds_matches_impl(
        sample_path,
        hash_index,
        sample_cache_root=sample_cache_root,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
        load_or_build_sample_cds_hashes_fn=load_or_build_sample_cds_hashes_impl,
        allele_match_cls=AlleleMatch,
    )


def predict_cds_sequences_impl(
    sample_path: Path,
    *,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
) -> list[str]:
    """Return the uppercased predicted CDS sequences for *sample_path*."""
    return _exact_hash.predict_cds_sequences_impl(
        sample_path,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
        predict_cds_genes_fn=_cds.predict_cds_genes_impl,
    )


def load_or_build_sample_cds_hashes_impl(
    sample_path: Path,
    *,
    cache_root: Path | None,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
) -> list[str]:
    """Return SHA-256 digests of the sample's predicted CDS sequences."""
    return _exact_hash.load_or_build_sample_cds_hashes_impl(
        sample_path,
        cache_root=cache_root,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
        load_or_build_sample_cds_data_fn=load_or_build_sample_cds_data_impl,
    )


def load_or_build_sample_cds_sequences_impl(
    sample_path: Path,
    *,
    cache_root: Path | None,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
) -> list[str]:
    """Return the sample's predicted CDS sequences (cached prediction)."""
    return _exact_hash.load_or_build_sample_cds_sequences_impl(
        sample_path,
        cache_root=cache_root,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
        load_or_build_sample_cds_data_fn=load_or_build_sample_cds_data_impl,
    )


def load_or_build_sample_cds_data_impl(
    sample_path: Path,
    *,
    cache_root: Path | None,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
) -> tuple[list[str], list[str]]:
    """Return ``(cds_hash_records, cds_sequences)`` for the sample."""
    return _exact_hash.load_or_build_sample_cds_data_impl(
        sample_path,
        cache_root=cache_root,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
        predict_cds_sequences_fn=predict_cds_sequences_impl,
        hash_cds_fn=hash_cds_impl,
        sample_cds_cache_config_fn=_exact_hash.sample_cds_cache_config_impl,
        logger=logger,
    )


def hash_cds_impl(sequence: str) -> str:
    """Return the scheme-canonical SHA-256 digest for a CDS sequence."""
    return _exact_hash.hash_cds_impl(sequence)
