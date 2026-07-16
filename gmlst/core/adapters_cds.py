from __future__ import annotations

import logging
from pathlib import Path

import gmlst.core as core
from gmlst.readers.sample import SampleInput

from . import cds as _cds
from .config import _configured_cgmlst_cds_training_file
from .exact_hash import scheme_precomputed_dir_impl

logger = logging.getLogger(__name__)


def resolve_cgmlst_cds_training_file_impl(
    *,
    allele_files: dict[str, Path],
    sample_paths: list[Path],
    mode: str,
) -> Path | None:
    return _cds.resolve_cgmlst_cds_training_file_impl(
        allele_files=allele_files,
        sample_paths=sample_paths,
        mode=mode,
        configured_training_file_fn=_configured_cgmlst_cds_training_file,
        scheme_precomputed_dir_fn=scheme_precomputed_dir_impl,
        logger=logger,
    )


def write_cds_coordinates_impl(
    *,
    samples: list[SampleInput],
    output_path: Path,
    prediction_mode: str,
    training_file: Path | None,
    closed_ends: bool,
) -> None:
    _cds.write_cds_coordinates_impl(
        samples=samples,
        output_path=output_path,
        prediction_mode=prediction_mode,
        training_file=training_file,
        closed_ends=closed_ends,
        predict_cds_genes_fn=core._predict_cds_genes,
        logger=logger,
    )
