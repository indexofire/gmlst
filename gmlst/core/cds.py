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
