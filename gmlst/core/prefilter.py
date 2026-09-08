"""Locus-candidate prefiltering for large cgMLST schemes.

Narrows whole-scheme alignment down to plausible loci before the expensive
full pass: k-mer candidate ranking, one representative allele per locus,
minimap2 representative-index alignment, and the cgMLST mode override
table that shapes the fast/ultrafast/balanced pipeline profiles.
"""

from __future__ import annotations

import math
from pathlib import Path

from gmlst.aligners.base import AlignmentResult
from gmlst.core.types import CgmlstModeOverrides


def prefilter_is_confident_impl(
    candidates: dict[str, list[tuple[str, float]]],
    *,
    total_loci: int,
    min_loci_fraction: float,
) -> bool:
    """Return True when enough loci have candidates to trust the prefilter.

    The fraction is clamped to ``[0, 1]`` and at least one locus is
    required; a failed check makes callers fall back to the full index.
    """
    if total_loci <= 0:
        return False
    clamped_fraction = min(1.0, max(0.0, min_loci_fraction))
    min_loci = max(1, math.ceil(total_loci * clamped_fraction))
    loci_with_candidates = sum(1 for ranked in candidates.values() if ranked)
    return loci_with_candidates >= min_loci


def flatten_allele_sequences_impl(
    allele_sequences: dict[str, dict[str, str]],
) -> dict[tuple[str, str], str]:
    """Flatten a nested per-locus allele map to ``(locus, allele_id)`` keys."""
    return {
        (locus, allele_id): sequence
        for locus, allele_ids in allele_sequences.items()
        for allele_id, sequence in allele_ids.items()
    }


def representative_alleles_impl(
    allele_sequences: dict[tuple[str, str], str],
    *,
    allele_order_key_fn,
) -> dict[tuple[str, str], str]:
    """Keep only the lowest-ordered allele per locus from a flat map."""
    representatives: dict[tuple[str, str], str] = {}
    by_locus: dict[str, tuple[str, str]] = {}
    for locus, allele_id in allele_sequences:
        current = by_locus.get(locus)
        if current is None or allele_order_key_fn(allele_id) < allele_order_key_fn(
            current[1]
        ):
            by_locus[locus] = (locus, allele_id)
    for key in by_locus.values():
        representatives[key] = allele_sequences[key]
    return representatives


def allele_order_key_impl(allele_id: str) -> tuple[int, int | str]:
    """Sort key ranking numeric allele IDs before non-numeric ones."""
    if allele_id.isdigit():
        return (0, int(allele_id))
    return (1, allele_id)


def select_candidate_locus_fastas_impl(
    allele_files: dict[str, Path],
    candidate_loci: set[str],
) -> list[Path]:
    """Return the allele FASTA paths for *candidate_loci* only."""
    if not candidate_loci:
        return []
    return [path for locus, path in allele_files.items() if locus in candidate_loci]


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
    """Shortlist loci by aligning the sample against representative alleles.

    Returns per-locus best ``(allele_id, identity * coverage)`` candidates
    (passing the thresholds) plus the representative alignment, which the
    ultrafast mode reuses directly as the main alignment.
    """
    if not representatives:
        return {}, None
    if representative_index_path is None:
        raise ValueError("Representative index path is required for minimap2 prefilter")

    rep_aln = aligner.align(sample_path, representative_index_path, loci, "fasta")
    best_by_locus: dict[str, tuple[str, float]] = {}
    for match in rep_aln.matches:
        if match.identity < min_identity or match.coverage < min_coverage:
            continue
        score = match.identity * match.coverage
        current = best_by_locus.get(match.locus)
        if current is None or score > current[1]:
            best_by_locus[match.locus] = (match.allele_id, score)

    return (
        {
            locus: [(allele_id, score)]
            for locus, (allele_id, score) in best_by_locus.items()
        },
        rep_aln,
    )


def cgmlst_mode_overrides_impl(
    *,
    cgmlst_mode: str,
    scheme_type: str,
    backend: str,
    logger,
) -> CgmlstModeOverrides:
    """Build the pipeline overrides table for a cgMLST mode.

    Only cgMLST + minimap2 gets mode-specific overrides; every other
    scheme/backend combination gets all-``None`` values so environment
    defaults apply. Unknown modes warn and fall back to ``fast``.
    """
    if scheme_type != "cgmlst" or backend != "minimap2":
        return CgmlstModeOverrides(
            exact_hash_prefilter=False,
            minimap2_hash_prefilter=False,
            minimap2_hash_locus_top_n=None,
            minimap2_hash_refine_max_loci=None,
            minimap2_fasta_emit_cigar=None,
            minimap2_fasta_speed_profile=None,
            minimap2_representative_main_alignment=None,
            minimap2_bsr_confirm_max_loci=None,
            minimap2_ultrafast_second_pass_max_loci=None,
            evidence_fallback_backend=None,
            evidence_fallback_max_loci=None,
        )

    mode = cgmlst_mode.strip().lower()
    if mode == "fast":
        return CgmlstModeOverrides(
            exact_hash_prefilter=True,
            minimap2_hash_prefilter=True,
            minimap2_hash_locus_top_n=None,
            minimap2_hash_refine_max_loci=500,
            minimap2_fasta_emit_cigar=True,
            minimap2_fasta_speed_profile="default",
            minimap2_representative_main_alignment=False,
            minimap2_bsr_confirm_max_loci=None,
            minimap2_ultrafast_second_pass_max_loci=None,
            evidence_fallback_backend="blastn",
            evidence_fallback_max_loci=500,
        )
    if mode == "ultrafast":
        return CgmlstModeOverrides(
            exact_hash_prefilter=True,
            minimap2_hash_prefilter=True,
            minimap2_hash_locus_top_n=None,
            minimap2_hash_refine_max_loci=0,
            minimap2_fasta_emit_cigar=False,
            minimap2_fasta_speed_profile="ultrafast",
            minimap2_representative_main_alignment=True,
            minimap2_bsr_confirm_max_loci=120,
            minimap2_ultrafast_second_pass_max_loci=None,
            evidence_fallback_backend="none",
            evidence_fallback_max_loci=0,
        )
    if mode == "balanced":
        return CgmlstModeOverrides(
            exact_hash_prefilter=True,
            minimap2_hash_prefilter=True,
            minimap2_hash_locus_top_n=None,
            minimap2_hash_refine_max_loci=500,
            minimap2_fasta_emit_cigar=True,
            minimap2_fasta_speed_profile="default",
            minimap2_representative_main_alignment=False,
            minimap2_bsr_confirm_max_loci=None,
            minimap2_ultrafast_second_pass_max_loci=None,
            evidence_fallback_backend="blastn",
            evidence_fallback_max_loci=300,
        )

    logger.warning("Unknown cgMLST mode %r; using 'fast'", cgmlst_mode)
    return CgmlstModeOverrides(
        exact_hash_prefilter=True,
        minimap2_hash_prefilter=True,
        minimap2_hash_locus_top_n=None,
        minimap2_hash_refine_max_loci=500,
        minimap2_fasta_emit_cigar=True,
        minimap2_fasta_speed_profile="default",
        minimap2_representative_main_alignment=False,
        minimap2_bsr_confirm_max_loci=None,
        minimap2_ultrafast_second_pass_max_loci=None,
        evidence_fallback_backend="blastn",
        evidence_fallback_max_loci=500,
    )
