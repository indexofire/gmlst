from __future__ import annotations

import logging
from pathlib import Path

from gmlst.aligners.base import AlleleMatch

from . import cds as _cds
from . import exact_hash as _exact_hash

logger = logging.getLogger("gmlst.core")


def load_or_build_exact_hash_indexes_impl(
    *,
    allele_files: dict[str, Path],
    allele_sequences: dict[str, dict[str, str]],
    include_protein: bool,
) -> tuple[
    dict[str, list[tuple[str, str]]],
    dict[str, list[tuple[str, str]]] | None,
]:
    return _exact_hash.load_or_build_exact_hash_indexes_impl(
        allele_files=allele_files,
        allele_sequences=allele_sequences,
        include_protein=include_protein,
        scheme_precomputed_dir_fn=_exact_hash.scheme_precomputed_dir_impl,
        allele_files_fingerprint_fn=_exact_hash.allele_files_fingerprint_impl,
        build_allele_hash_index_fn=_exact_hash.build_allele_hash_index_impl,
        build_allele_protein_hash_index_fn=build_allele_protein_hash_index_impl,
        logger=logger,
    )


def build_allele_protein_hash_index_impl(
    allele_sequences: dict[str, dict[str, str]],
) -> dict[str, list[tuple[str, str]]]:
    return _exact_hash.build_allele_protein_hash_index_impl(
        allele_sequences,
        translate_cds_to_protein_fn=_exact_hash.translate_cds_to_protein_impl,
    )


def resolve_exact_cds_matches_impl(
    sample_path: Path,
    hash_index: dict[str, list[tuple[str, str]]],
    *,
    protein_hash_index: dict[str, list[tuple[str, str]]] | None = None,
    sample_cache_root: Path | None = None,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
) -> dict[str, object]:
    return _exact_hash.resolve_exact_cds_matches_impl(
        sample_path,
        hash_index,
        protein_hash_index=protein_hash_index,
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
) -> list[tuple[str, str | None]]:
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
) -> tuple[list[tuple[str, str | None]], list[str]]:
    return _exact_hash.load_or_build_sample_cds_data_impl(
        sample_path,
        cache_root=cache_root,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
        predict_cds_sequences_fn=predict_cds_sequences_impl,
        hash_cds_and_protein_fn=hash_cds_and_protein_impl,
        sample_cds_cache_config_fn=_exact_hash.sample_cds_cache_config_impl,
        logger=logger,
    )


def hash_cds_and_protein_impl(sequence: str) -> tuple[str, str | None]:
    return _exact_hash.hash_cds_and_protein_impl(
        sequence,
        translate_cds_to_protein_fn=_exact_hash.translate_cds_to_protein_impl,
    )
