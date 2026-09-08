"""CDS prediction support for cgMLST workflows.

Coordinates Pyrodigal/Prodigal gene prediction used by exact-hash allele
calling and chewBBACA-style classification: resolves the training file to
use, runs prediction for a sample, and exports predicted CDS coordinates.
All implementation functions take injected callables/loggers so the core
package can wire them via adapter modules without import cycles.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from gmlst.readers.sample import SampleInput


def resolve_cgmlst_cds_training_file_impl(
    *,
    allele_files: dict[str, Path],
    sample_paths: list[Path],
    mode: str,
    configured_training_file_fn,
    scheme_precomputed_dir_fn,
    logger,
) -> Path | None:
    """Resolve the Pyrodigal training file to use for CDS prediction.

    Resolution order:
    1. ``GMLST_CGMLST_CDS_TRAINING_FILE`` (via *configured_training_file_fn*)
    2. ``<scheme>/pre_computed/pyrodigal_training.trn`` next to the allele
       files, if it already exists
    3. In ``"single"`` mode only: auto-create it by training on the first
       existing sample file; other modes return ``None`` on a miss.

    Returns ``None`` (never raises) when no training file can be resolved;
    callers then fall back to meta mode or untrained prediction.
    """
    configured = configured_training_file_fn()
    if configured is not None:
        target = configured
    else:
        target = scheme_precomputed_dir_fn(allele_files) / "pyrodigal_training.trn"

    if target.exists() and target.is_file():
        return target
    if mode != "single":
        return None

    sample_path: Path | None = None
    for candidate in sample_paths:
        if candidate.exists() and candidate.is_file():
            sample_path = candidate
            break
    if sample_path is None:
        return None

    from gmlst.core.gene_predictor import create_pyrodigal_training_file

    try:
        create_pyrodigal_training_file(sample_path, target)
    except Exception as exc:
        logger.warning(
            "Failed to auto-create Pyrodigal training file at %s: %s",
            target,
            exc,
        )
        return None
    return target


def predict_cds_genes_impl(
    sample_path: Path,
    *,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
) -> list[Any]:
    """Predict CDS genes for *sample_path* and return ``PredictedGene`` objects.

    Uses a Pyrodigal-backed :class:`ProdigalPredictor` with fallback to the
    external ``prodigal`` binary. *cds_prediction_mode* selects Prodigal's
    ``meta``/``single`` strategy; *cds_closed_ends* suppresses partial genes
    at contig edges.
    """
    from gmlst.core.gene_predictor import ProdigalPredictor

    predictor = ProdigalPredictor(
        tool="pyrodigal",
        mode=cds_prediction_mode,
        training_file=cds_training_file,
        closed_ends=cds_closed_ends,
        enable_fallback=True,
    )
    return predictor.predict(sample_path, sample_path.stem)


def write_cds_coordinates_impl(
    *,
    samples: list[SampleInput],
    output_path: Path,
    prediction_mode: str,
    training_file: Path | None,
    closed_ends: bool,
    predict_cds_genes_fn,
    logger,
) -> None:
    """Write a TSV of predicted CDS coordinates for all FASTA-only samples.

    Skips FASTQ samples and paired inputs (gene prediction requires an
    assembly). Creates parent directories and writes one row per predicted
    gene with coordinates, strand, partial flags, and run settings.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "sample_id",
                "gene_id",
                "contig_id",
                "start",
                "end",
                "strand",
                "length",
                "partial_begin",
                "partial_end",
                "mode",
                "training_file",
                "closed_ends",
            ]
        )
        for sample in samples:
            if sample.input_type != "fasta" or sample.mate_path is not None:
                continue
            genes = predict_cds_genes_fn(
                sample.path,
                cds_prediction_mode=prediction_mode,
                cds_training_file=training_file,
                cds_closed_ends=closed_ends,
            )
            for gene in genes:
                writer.writerow(
                    [
                        sample.sample_id,
                        getattr(gene, "gene_id", ""),
                        getattr(gene, "contig_id", "") or "",
                        getattr(gene, "start", "") or "",
                        getattr(gene, "end", "") or "",
                        getattr(gene, "strand", "") or "",
                        len(getattr(gene, "sequence", "")),
                        int(bool(getattr(gene, "partial_begin", False))),
                        int(bool(getattr(gene, "partial_end", False))),
                        prediction_mode,
                        str(training_file) if training_file is not None else "",
                        int(closed_ends),
                    ]
                )
    logger.info("Wrote CDS coordinates to %s", output_path)
