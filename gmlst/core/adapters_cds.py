"""CDS adapter layer binding ``cds.py`` implementations to concrete helpers.

These thin wrappers re-export the dependency-injected implementation
functions from :mod:`gmlst.core.cds` with the real config/env lookups and
loggers wired in, so :mod:`gmlst.core` can consume them without creating
an import cycle with the implementation modules.
"""

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
    """Resolve the Pyrodigal training file, wiring in env/config helpers.

    Delegates to :func:`gmlst.core.cds.resolve_cgmlst_cds_training_file_impl`
    with the ``GMLST_CGMLST_CDS_TRAINING_FILE`` lookup and the scheme
    pre-computed directory resolver bound.
    """
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
    """Write per-sample CDS coordinate TSVs, binding the core predictor."""
    _cds.write_cds_coordinates_impl(
        samples=samples,
        output_path=output_path,
        prediction_mode=prediction_mode,
        training_file=training_file,
        closed_ends=closed_ends,
        predict_cds_genes_fn=core._predict_cds_genes,
        logger=logger,
    )
