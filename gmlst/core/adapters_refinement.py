from __future__ import annotations

from pathlib import Path

from gmlst.aligners.base import AlignmentResult
from gmlst.calling.allele import LocusCall
from gmlst.core.types import CgmlstModeOverrides
from gmlst.database.cache import DatabaseCache
from gmlst.readers.sample import SampleInput

from . import refinement as _refinement


def write_merged_fasta_impl(fasta_paths: list[Path], out_path: Path) -> None:
    _refinement._write_merged_fasta_impl(fasta_paths, out_path)


def align_targeted_loci_impl(
    *,
    aligner,
    sample_source: Path | tuple[Path, Path],
    sample_id: str,
    sample_input_type: str,
    loci: list[str],
    targeted_fastas: list[Path],
    temp_prefix: str,
    merge_fasta_for_fasta: bool = True,
    force_build_index: bool = False,
) -> tuple[AlignmentResult, float]:
    import gmlst.core as core

    return _refinement._align_targeted_loci_impl(
        aligner=aligner,
        sample_source=sample_source,
        sample_id=sample_id,
        sample_input_type=sample_input_type,
        loci=loci,
        targeted_fastas=targeted_fastas,
        temp_prefix=temp_prefix,
        write_merged_fasta_fn=core._write_merged_fasta,
        merge_fasta_for_fasta=merge_fasta_for_fasta,
        force_build_index=force_build_index,
    )


def merge_calls_from_alignment_impl(
    *,
    base_calls: dict[str, LocusCall],
    alignment: AlignmentResult,
    loci: list[str],
    min_identity: float,
    min_coverage: float,
    min_depth: float,
) -> None:
    import gmlst.core as core

    _refinement._merge_calls_from_alignment_impl(
        base_calls=base_calls,
        alignment=alignment,
        loci=loci,
        min_identity=min_identity,
        min_coverage=min_coverage,
        min_depth=min_depth,
        call_all_loci_fn=core.call_all_loci,
        merge_fallback_calls_fn=core._merge_fallback_calls,
    )


def recompute_all_loci_with_additional_alignment_impl(
    *,
    base_alignment: AlignmentResult,
    additional_alignment: AlignmentResult,
    all_loci: list[str],
    min_identity: float,
    min_coverage: float,
    min_depth: float,
) -> dict[str, LocusCall]:
    import gmlst.core as core

    return _refinement._recompute_all_loci_with_additional_alignment_impl(
        base_alignment=base_alignment,
        additional_alignment=additional_alignment,
        all_loci=all_loci,
        min_identity=min_identity,
        min_coverage=min_coverage,
        min_depth=min_depth,
        call_all_loci_fn=core.call_all_loci,
    )


def confirm_loci_with_tuned_aligner_impl(
    *,
    base_calls: dict[str, LocusCall],
    backend: str,
    aligner_kwargs: dict[str, object],
    sample: SampleInput,
    sample_source: Path | tuple[Path, Path],
    candidate_loci: list[str],
    allele_files: dict[str, Path],
    temp_prefix: str,
    log_template: str,
    min_identity: float,
    min_coverage: float,
    min_depth: float,
) -> None:
    import gmlst.core as core

    _refinement._confirm_loci_with_tuned_aligner_impl(
        base_calls=base_calls,
        backend=backend,
        aligner_kwargs=aligner_kwargs,
        sample=sample,
        sample_source=sample_source,
        candidate_loci=candidate_loci,
        allele_files=allele_files,
        temp_prefix=temp_prefix,
        log_template=log_template,
        min_identity=min_identity,
        min_coverage=min_coverage,
        min_depth=min_depth,
        get_aligner_fn=core.get_aligner,
        align_targeted_loci_fn=core._align_targeted_loci,
        merge_calls_from_alignment_fn=core._merge_calls_from_alignment,
        select_candidate_locus_fastas_fn=core._select_candidate_locus_fastas,
        logger=core.logger,
    )


def align_evidence_fallback_loci_impl(
    *,
    fallback_aligner,
    fallback_backend: str,
    sample: SampleInput,
    sample_source: Path | tuple[Path, Path],
    loci: list[str],
    scheme_allele_files: dict[str, Path],
    cache: DatabaseCache,
    scheme_name: str,
    provider: str,
    allele_fastas: list[Path],
    force_reindex: bool,
) -> tuple[AlignmentResult, float] | None:
    import gmlst.core as core

    return _refinement._align_evidence_fallback_loci_impl(
        fallback_aligner=fallback_aligner,
        fallback_backend=fallback_backend,
        sample=sample,
        sample_source=sample_source,
        loci=loci,
        scheme_allele_files=scheme_allele_files,
        cache=cache,
        scheme_name=scheme_name,
        provider=provider,
        allele_fastas=allele_fastas,
        force_reindex=force_reindex,
        select_candidate_locus_fastas_fn=core._select_candidate_locus_fastas,
        align_targeted_loci_fn=core._align_targeted_loci,
        ensure_full_index_fn=core._ensure_full_index,
    )


def apply_post_alignment_refinements_impl(
    *,
    locus_calls: dict[str, LocusCall],
    aln: AlignmentResult,
    aligner,
    sample: SampleInput,
    sample_source: Path | tuple[Path, Path],
    scheme,
    mode_overrides: CgmlstModeOverrides,
    use_minimap2_hash_prefilter: bool,
    scheme_type: str,
    backend: str,
    kma_fastq_mem_mode: bool,
    threads: int,
    count_same_copy: bool,
    min_identity: float,
    min_coverage: float,
    effective_min_depth: float,
    minimap2_representative_main_alignment: bool,
    ultrafast_second_pass_max_loci: int | None,
    cache: DatabaseCache,
    scheme_name: str,
    provider: str,
    allele_fastas: list[Path],
    force_reindex: bool,
) -> dict[str, LocusCall]:
    import gmlst.core as core

    return _refinement._apply_post_alignment_refinements_impl(
        locus_calls=locus_calls,
        aln=aln,
        aligner=aligner,
        sample=sample,
        sample_source=sample_source,
        scheme=scheme,
        mode_overrides=mode_overrides,
        use_minimap2_hash_prefilter=use_minimap2_hash_prefilter,
        scheme_type=scheme_type,
        backend=backend,
        kma_fastq_mem_mode=kma_fastq_mem_mode,
        threads=threads,
        count_same_copy=count_same_copy,
        min_identity=min_identity,
        min_coverage=min_coverage,
        effective_min_depth=effective_min_depth,
        minimap2_representative_main_alignment=minimap2_representative_main_alignment,
        ultrafast_second_pass_max_loci=ultrafast_second_pass_max_loci,
        cache=cache,
        scheme_name=scheme_name,
        provider=provider,
        allele_fastas=allele_fastas,
        force_reindex=force_reindex,
        align_targeted_loci_fn=core._align_targeted_loci,
        recompute_all_loci_with_additional_alignment_fn=(
            core._recompute_all_loci_with_additional_alignment
        ),
        confirm_loci_with_tuned_aligner_fn=core._confirm_loci_with_tuned_aligner,
        align_evidence_fallback_loci_fn=core._align_evidence_fallback_loci,
        merge_calls_from_alignment_fn=core._merge_calls_from_alignment,
        select_candidate_locus_fastas_fn=core._select_candidate_locus_fastas,
        get_aligner_fn=core.get_aligner,
        low_confidence_loci_fn=core._low_confidence_loci,
        call_rank_fn=core._call_rank,
        ultrafast_confirmation_rank_fn=core._ultrafast_confirmation_rank,
        ultrafast_second_pass_rank_fn=core._ultrafast_second_pass_rank,
        adaptive_ultrafast_second_pass_budget_fn=(
            core._adaptive_ultrafast_second_pass_budget
        ),
        minimap2_hash_refine_max_loci_fn=core._minimap2_hash_refine_max_loci,
        kma_fastq_mem_confirm_max_loci_fn=core._kma_fastq_mem_confirm_max_loci,
        minimap2_bsr_confirm_max_loci_fn=core._minimap2_bsr_confirm_max_loci,
        cgmlst_evidence_fallback_backend_fn=core._cgmlst_evidence_fallback_backend,
        cgmlst_evidence_fallback_max_loci_fn=core._cgmlst_evidence_fallback_max_loci,
        logger=core.logger,
    )


def merge_fallback_calls_impl(
    base_calls: dict[str, LocusCall],
    fallback_calls: dict[str, LocusCall],
) -> None:
    import gmlst.core as core

    for locus, fallback_call in fallback_calls.items():
        base_call = base_calls.get(locus)
        if base_call is None or core._call_rank(fallback_call) > core._call_rank(
            base_call
        ):
            base_calls[locus] = fallback_call
