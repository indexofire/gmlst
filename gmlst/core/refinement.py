from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from logging import Logger
from pathlib import Path

from gmlst.aligners.base import AlignmentResult
from gmlst.calling.allele import LocusCall
from gmlst.core.types import CgmlstModeOverrides
from gmlst.database.cache import DatabaseCache
from gmlst.readers.sample import SampleInput
from gmlst.utils import temp_dir


def _write_merged_fasta_impl(fasta_paths: list[Path], out_path: Path) -> None:
    with out_path.open("wb") as out:
        for fasta in sorted(fasta_paths):
            with fasta.open("rb") as src:
                shutil.copyfileobj(src, out)


def _align_targeted_loci_impl(
    *,
    aligner,
    sample_source: Path | tuple[Path, Path],
    sample_id: str,
    sample_input_type: str,
    loci: list[str],
    targeted_fastas: list[Path],
    temp_prefix: str,
    write_merged_fasta_fn: Callable[[list[Path], Path], None],
    merge_fasta_for_fasta: bool = True,
    force_build_index: bool = False,
) -> tuple[AlignmentResult, float]:
    if not loci or not targeted_fastas:
        return (
            AlignmentResult(
                sample_id=sample_id,
                matches=[],
                failed_loci=[],
                backend=aligner.name,
                runtime_seconds=0.0,
            ),
            0.0,
        )

    with temp_dir(temp_prefix) as tmp:
        index_dir = tmp / "idx"
        index_dir.mkdir(parents=True, exist_ok=True)
        if (
            sample_input_type == "fasta"
            and merge_fasta_for_fasta
            and not force_build_index
        ):
            write_merged_fasta_fn(targeted_fastas, index_dir / "alleles.fasta")
            index_path = index_dir
        else:
            index_path = aligner.index(targeted_fastas, index_dir)

        align_start = time.perf_counter()
        aln = aligner.align(sample_source, index_path, loci, sample_input_type)
        align_elapsed = time.perf_counter() - align_start
    return aln, align_elapsed


def _merge_calls_from_alignment_impl(
    *,
    base_calls: dict[str, LocusCall],
    alignment: AlignmentResult,
    loci: list[str],
    min_identity: float,
    min_coverage: float,
    min_depth: float,
    call_all_loci_fn,
    merge_fallback_calls_fn,
) -> None:
    extra_calls = call_all_loci_fn(
        alignment,
        loci,
        min_identity=min_identity,
        min_coverage=min_coverage,
        min_depth=min_depth,
    )
    merge_fallback_calls_fn(base_calls, extra_calls)


def _recompute_all_loci_with_additional_alignment_impl(
    *,
    base_alignment: AlignmentResult,
    additional_alignment: AlignmentResult,
    all_loci: list[str],
    min_identity: float,
    min_coverage: float,
    min_depth: float,
    call_all_loci_fn,
) -> dict[str, LocusCall]:
    merged_aln = AlignmentResult(
        sample_id=base_alignment.sample_id,
        matches=[*base_alignment.matches, *additional_alignment.matches],
        failed_loci=[],
        backend=base_alignment.backend,
        runtime_seconds=(
            base_alignment.runtime_seconds + additional_alignment.runtime_seconds
        ),
    )
    return call_all_loci_fn(
        merged_aln,
        all_loci,
        min_identity=min_identity,
        min_coverage=min_coverage,
        min_depth=min_depth,
    )


def _confirm_loci_with_tuned_aligner_impl(
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
    get_aligner_fn,
    align_targeted_loci_fn,
    merge_calls_from_alignment_fn,
    select_candidate_locus_fastas_fn,
    logger: Logger,
) -> None:
    if not candidate_loci:
        return

    targeted_fastas = select_candidate_locus_fastas_fn(
        allele_files,
        set(candidate_loci),
    )
    if not targeted_fastas:
        return

    confirm_aligner = get_aligner_fn(backend, **aligner_kwargs)
    confirm_aligner.check_dependencies()
    confirm_aln, confirm_elapsed = align_targeted_loci_fn(
        aligner=confirm_aligner,
        sample_source=sample_source,
        sample_id=sample.sample_id,
        sample_input_type=sample.input_type,
        loci=candidate_loci,
        targeted_fastas=targeted_fastas,
        temp_prefix=temp_prefix,
    )
    logger.info(
        log_template,
        confirm_elapsed,
        sample.path.name,
        len(candidate_loci),
    )
    merge_calls_from_alignment_fn(
        base_calls=base_calls,
        alignment=confirm_aln,
        loci=candidate_loci,
        min_identity=min_identity,
        min_coverage=min_coverage,
        min_depth=min_depth,
    )


def _align_evidence_fallback_loci_impl(
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
    select_candidate_locus_fastas_fn,
    align_targeted_loci_fn,
    ensure_full_index_fn,
) -> tuple[AlignmentResult, float] | None:
    if fallback_backend == "blastn":
        targeted_fastas = select_candidate_locus_fastas_fn(
            scheme_allele_files,
            set(loci),
        )
        if not targeted_fastas:
            return None
        return align_targeted_loci_fn(
            aligner=fallback_aligner,
            sample_source=sample_source,
            sample_id=sample.sample_id,
            sample_input_type=sample.input_type,
            loci=sorted(loci),
            targeted_fastas=targeted_fastas,
            temp_prefix="gmlst_fallback_blastn_",
            force_build_index=True,
        )

    fallback_index_dir = cache.index_dir(
        scheme_name,
        fallback_backend,
        provider=provider,
    )
    fallback_index_path = ensure_full_index_fn(
        aligner=fallback_aligner,
        backend=fallback_backend,
        scheme_name=scheme_name,
        allele_fastas=allele_fastas,
        index_dir=fallback_index_dir,
        force_reindex=force_reindex,
    )
    fallback_start = time.perf_counter()
    fallback_aln = fallback_aligner.align(
        sample_source,
        fallback_index_path,
        sorted(loci),
        sample.input_type,
    )
    fallback_elapsed = time.perf_counter() - fallback_start
    return fallback_aln, fallback_elapsed


def _refine_minimap2_hash_prefilter(
    *,
    locus_calls: dict[str, LocusCall],
    aln: AlignmentResult,
    aligner,
    sample: SampleInput,
    sample_source: Path | tuple[Path, Path],
    scheme,
    mode_overrides: CgmlstModeOverrides,
    use_minimap2_hash_prefilter: bool,
    backend: str,
    min_identity: float,
    min_coverage: float,
    effective_min_depth: float,
    align_targeted_loci_fn,
    recompute_all_loci_with_additional_alignment_fn,
    select_candidate_locus_fastas_fn,
    minimap2_hash_refine_max_loci_fn,
    logger: Logger,
) -> dict[str, LocusCall]:
    if use_minimap2_hash_prefilter and backend == "minimap2":
        unresolved_loci = [
            locus for locus, call in locus_calls.items() if call.call_type == "missing"
        ]
        refine_limit = (
            mode_overrides.minimap2_hash_refine_max_loci
            if mode_overrides.minimap2_hash_refine_max_loci is not None
            else minimap2_hash_refine_max_loci_fn()
        )
        if (
            refine_limit > 0
            and unresolved_loci
            and len(unresolved_loci) <= refine_limit
        ):
            refine_fastas = select_candidate_locus_fastas_fn(
                scheme.allele_files,
                set(unresolved_loci),
            )
            refine_aln, refine_elapsed = align_targeted_loci_fn(
                aligner=aligner,
                sample_source=sample_source,
                sample_id=aln.sample_id,
                sample_input_type=sample.input_type,
                loci=unresolved_loci,
                targeted_fastas=refine_fastas,
                temp_prefix="gmlst_refine_",
            )
            logger.info(
                "Refinement alignment completed in %.3fs for %s (%d loci)",
                refine_elapsed,
                sample.path.name,
                len(unresolved_loci),
            )
            locus_calls = recompute_all_loci_with_additional_alignment_fn(
                base_alignment=aln,
                additional_alignment=refine_aln,
                all_loci=scheme.loci,
                min_identity=min_identity,
                min_coverage=min_coverage,
                min_depth=effective_min_depth,
            )
    return locus_calls


def _refine_kma_fastq_mem_strict(
    *,
    locus_calls: dict[str, LocusCall],
    scheme_type: str,
    backend: str,
    sample: SampleInput,
    sample_source: Path | tuple[Path, Path],
    scheme,
    kma_fastq_mem_mode: bool,
    threads: int,
    count_same_copy: bool,
    min_identity: float,
    min_coverage: float,
    effective_min_depth: float,
    kma_fastq_mem_confirm_max_loci_fn,
    call_rank_fn,
    confirm_loci_with_tuned_aligner_fn,
    logger: Logger,
) -> None:
    if (
        scheme_type == "cgmlst"
        and backend == "kma"
        and sample.input_type == "fastq"
        and kma_fastq_mem_mode
    ):
        confirm_max_loci = kma_fastq_mem_confirm_max_loci_fn()
        if confirm_max_loci > 0:
            confirm_loci = sorted(
                (
                    locus
                    for locus, call in locus_calls.items()
                    if call.call_type == "closest"
                ),
                key=lambda locus: call_rank_fn(locus_calls[locus]),
            )[:confirm_max_loci]
            if confirm_loci:
                logger.info(
                    "KMA FASTQ mem_mode strict confirmation selecting %d loci for %s",
                    len(confirm_loci),
                    sample.path.name,
                )
                confirm_loci_with_tuned_aligner_fn(
                    base_calls=locus_calls,
                    backend="kma",
                    aligner_kwargs={
                        "threads": threads,
                        "count_same_copy": count_same_copy,
                        "fastq_mem_mode": False,
                    },
                    sample=sample,
                    sample_source=sample_source,
                    candidate_loci=confirm_loci,
                    allele_files=scheme.allele_files,
                    temp_prefix="gmlst_kma_fastq_confirm_",
                    log_template=(
                        "KMA FASTQ mem_mode strict confirmation completed "
                        "in %.3fs for %s (%d loci)"
                    ),
                    min_identity=min_identity,
                    min_coverage=min_coverage,
                    min_depth=effective_min_depth,
                )


def _refine_bsr_minimap2_confirmation(
    *,
    locus_calls: dict[str, LocusCall],
    scheme_type: str,
    backend: str,
    sample: SampleInput,
    sample_source: Path | tuple[Path, Path],
    scheme,
    mode_overrides: CgmlstModeOverrides,
    minimap2_representative_main_alignment: bool,
    threads: int,
    count_same_copy: bool,
    min_identity: float,
    min_coverage: float,
    effective_min_depth: float,
    minimap2_bsr_confirm_max_loci_fn,
    low_confidence_loci_fn,
    ultrafast_confirmation_rank_fn,
    call_rank_fn,
    confirm_loci_with_tuned_aligner_fn,
    logger: Logger,
) -> None:
    bsr_confirm_max_loci_env = minimap2_bsr_confirm_max_loci_fn()
    bsr_confirm_max_loci = (
        bsr_confirm_max_loci_env
        if bsr_confirm_max_loci_env > 0
        else (
            mode_overrides.minimap2_bsr_confirm_max_loci
            if mode_overrides.minimap2_bsr_confirm_max_loci is not None
            else 0
        )
    )
    if (
        scheme_type == "cgmlst"
        and backend == "minimap2"
        and sample.input_type == "fasta"
        and bsr_confirm_max_loci > 0
    ):
        low_conf_loci = low_confidence_loci_fn(locus_calls)
        if low_conf_loci:
            if minimap2_representative_main_alignment:
                confirm_loci = sorted(
                    low_conf_loci,
                    key=lambda locus: ultrafast_confirmation_rank_fn(
                        locus_calls[locus]
                    ),
                )[:bsr_confirm_max_loci]
            else:
                confirm_loci = sorted(
                    low_conf_loci,
                    key=lambda locus: call_rank_fn(locus_calls[locus]),
                )[:bsr_confirm_max_loci]
            if len(confirm_loci) < len(low_conf_loci):
                logger.info(
                    "BSR-like minimap2 confirmation selecting %d/%d "
                    "low-confidence loci for %s",
                    len(confirm_loci),
                    len(low_conf_loci),
                    sample.path.name,
                )
            confirm_loci_with_tuned_aligner_fn(
                base_calls=locus_calls,
                backend="minimap2",
                aligner_kwargs={
                    "threads": threads,
                    "count_same_copy": count_same_copy,
                    "fasta_emit_cigar": True,
                    "fasta_speed_profile": "fast",
                },
                sample=sample,
                sample_source=sample_source,
                candidate_loci=sorted(confirm_loci),
                allele_files=scheme.allele_files,
                temp_prefix="gmlst_bsr_confirm_",
                log_template=(
                    "BSR-like minimap2 confirmation completed in %.3fs for %s (%d loci)"
                ),
                min_identity=min_identity,
                min_coverage=min_coverage,
                min_depth=effective_min_depth,
            )
        else:
            logger.info(
                "Skipping BSR-like minimap2 confirmation for %s: "
                "no low-confidence loci",
                sample.path.name,
            )


def _refine_ultrafast_second_pass(
    *,
    locus_calls: dict[str, LocusCall],
    scheme_type: str,
    backend: str,
    sample: SampleInput,
    sample_source: Path | tuple[Path, Path],
    scheme,
    minimap2_representative_main_alignment: bool,
    ultrafast_second_pass_max_loci: int | None,
    threads: int,
    count_same_copy: bool,
    min_identity: float,
    min_coverage: float,
    effective_min_depth: float,
    adaptive_ultrafast_second_pass_budget_fn,
    ultrafast_second_pass_rank_fn,
    confirm_loci_with_tuned_aligner_fn,
    logger: Logger,
) -> None:
    if (
        scheme_type == "cgmlst"
        and backend == "minimap2"
        and sample.input_type == "fasta"
        and minimap2_representative_main_alignment
        and ultrafast_second_pass_max_loci != 0
    ):
        second_pass_budget = ultrafast_second_pass_max_loci
        if second_pass_budget is None:
            second_pass_budget = adaptive_ultrafast_second_pass_budget_fn(locus_calls)
        second_pass_loci = sorted(
            (
                locus
                for locus, call in locus_calls.items()
                if call.call_type in {"partial", "closest"}
            ),
            key=lambda locus: ultrafast_second_pass_rank_fn(locus_calls[locus]),
        )[:second_pass_budget]
        if second_pass_loci:
            logger.info(
                "Ultrafast second-pass selecting %d loci (budget=%d) for %s",
                len(second_pass_loci),
                second_pass_budget,
                sample.path.name,
            )
            confirm_loci_with_tuned_aligner_fn(
                base_calls=locus_calls,
                backend="minimap2",
                aligner_kwargs={
                    "threads": threads,
                    "count_same_copy": count_same_copy,
                    "fasta_emit_cigar": True,
                    "fasta_speed_profile": "default",
                },
                sample=sample,
                sample_source=sample_source,
                candidate_loci=second_pass_loci,
                allele_files=scheme.allele_files,
                temp_prefix="gmlst_ultra_second_pass_",
                log_template=(
                    "Ultrafast second-pass minimap2 confirmation completed "
                    "in %.3fs for %s (%d loci)"
                ),
                min_identity=min_identity,
                min_coverage=min_coverage,
                min_depth=effective_min_depth,
            )


def _refine_evidence_fallback(
    *,
    locus_calls: dict[str, LocusCall],
    scheme_type: str,
    backend: str,
    sample: SampleInput,
    sample_source: Path | tuple[Path, Path],
    scheme,
    mode_overrides: CgmlstModeOverrides,
    threads: int,
    count_same_copy: bool,
    min_identity: float,
    min_coverage: float,
    effective_min_depth: float,
    cache: DatabaseCache,
    scheme_name: str,
    provider: str,
    allele_fastas: list[Path],
    force_reindex: bool,
    cgmlst_evidence_fallback_backend_fn,
    cgmlst_evidence_fallback_max_loci_fn,
    low_confidence_loci_fn,
    get_aligner_fn,
    align_evidence_fallback_loci_fn,
    merge_calls_from_alignment_fn,
    logger: Logger,
) -> None:
    fallback_backend = (
        mode_overrides.evidence_fallback_backend
        if mode_overrides.evidence_fallback_backend is not None
        else cgmlst_evidence_fallback_backend_fn()
    )
    if (
        scheme_type == "cgmlst"
        and backend == "minimap2"
        and fallback_backend != "none"
        and fallback_backend != backend
    ):
        low_conf_loci = low_confidence_loci_fn(locus_calls)
        max_loci = (
            mode_overrides.evidence_fallback_max_loci
            if mode_overrides.evidence_fallback_max_loci is not None
            else cgmlst_evidence_fallback_max_loci_fn()
        )
        if low_conf_loci and (max_loci <= 0 or len(low_conf_loci) <= max_loci):
            fallback_aligner = get_aligner_fn(
                fallback_backend,
                threads=threads,
                count_same_copy=count_same_copy,
            )
            fallback_aligner.check_dependencies()
            if fallback_aligner.supports_fastq or sample.input_type == "fasta":
                fallback_result = align_evidence_fallback_loci_fn(
                    fallback_aligner=fallback_aligner,
                    fallback_backend=fallback_backend,
                    sample=sample,
                    sample_source=sample_source,
                    loci=sorted(low_conf_loci),
                    scheme_allele_files=scheme.allele_files,
                    cache=cache,
                    scheme_name=scheme_name,
                    provider=provider,
                    allele_fastas=allele_fastas,
                    force_reindex=force_reindex,
                )
                if fallback_result is not None:
                    fallback_aln, fallback_elapsed = fallback_result
                    logger.info(
                        "Evidence fallback alignment (%s) completed in %.3fs "
                        "for %s (%d loci)",
                        fallback_backend,
                        fallback_elapsed,
                        sample.path.name,
                        len(low_conf_loci),
                    )
                    merge_calls_from_alignment_fn(
                        base_calls=locus_calls,
                        alignment=fallback_aln,
                        loci=sorted(low_conf_loci),
                        min_identity=min_identity,
                        min_coverage=min_coverage,
                        min_depth=effective_min_depth,
                    )


def _apply_post_alignment_refinements_impl(
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
    align_targeted_loci_fn,
    recompute_all_loci_with_additional_alignment_fn,
    confirm_loci_with_tuned_aligner_fn,
    align_evidence_fallback_loci_fn,
    merge_calls_from_alignment_fn,
    select_candidate_locus_fastas_fn,
    get_aligner_fn,
    low_confidence_loci_fn,
    call_rank_fn,
    ultrafast_confirmation_rank_fn,
    ultrafast_second_pass_rank_fn,
    adaptive_ultrafast_second_pass_budget_fn,
    minimap2_hash_refine_max_loci_fn,
    kma_fastq_mem_confirm_max_loci_fn,
    minimap2_bsr_confirm_max_loci_fn,
    cgmlst_evidence_fallback_backend_fn,
    cgmlst_evidence_fallback_max_loci_fn,
    logger: Logger,
) -> dict[str, LocusCall]:
    locus_calls = _refine_minimap2_hash_prefilter(
        locus_calls=locus_calls,
        aln=aln,
        aligner=aligner,
        sample=sample,
        sample_source=sample_source,
        scheme=scheme,
        mode_overrides=mode_overrides,
        use_minimap2_hash_prefilter=use_minimap2_hash_prefilter,
        backend=backend,
        min_identity=min_identity,
        min_coverage=min_coverage,
        effective_min_depth=effective_min_depth,
        align_targeted_loci_fn=align_targeted_loci_fn,
        recompute_all_loci_with_additional_alignment_fn=(
            recompute_all_loci_with_additional_alignment_fn
        ),
        select_candidate_locus_fastas_fn=select_candidate_locus_fastas_fn,
        minimap2_hash_refine_max_loci_fn=minimap2_hash_refine_max_loci_fn,
        logger=logger,
    )

    _refine_kma_fastq_mem_strict(
        locus_calls=locus_calls,
        scheme_type=scheme_type,
        backend=backend,
        sample=sample,
        sample_source=sample_source,
        scheme=scheme,
        kma_fastq_mem_mode=kma_fastq_mem_mode,
        threads=threads,
        count_same_copy=count_same_copy,
        min_identity=min_identity,
        min_coverage=min_coverage,
        effective_min_depth=effective_min_depth,
        kma_fastq_mem_confirm_max_loci_fn=kma_fastq_mem_confirm_max_loci_fn,
        call_rank_fn=call_rank_fn,
        confirm_loci_with_tuned_aligner_fn=confirm_loci_with_tuned_aligner_fn,
        logger=logger,
    )

    _refine_bsr_minimap2_confirmation(
        locus_calls=locus_calls,
        scheme_type=scheme_type,
        backend=backend,
        sample=sample,
        sample_source=sample_source,
        scheme=scheme,
        mode_overrides=mode_overrides,
        minimap2_representative_main_alignment=minimap2_representative_main_alignment,
        threads=threads,
        count_same_copy=count_same_copy,
        min_identity=min_identity,
        min_coverage=min_coverage,
        effective_min_depth=effective_min_depth,
        minimap2_bsr_confirm_max_loci_fn=minimap2_bsr_confirm_max_loci_fn,
        low_confidence_loci_fn=low_confidence_loci_fn,
        ultrafast_confirmation_rank_fn=ultrafast_confirmation_rank_fn,
        call_rank_fn=call_rank_fn,
        confirm_loci_with_tuned_aligner_fn=confirm_loci_with_tuned_aligner_fn,
        logger=logger,
    )

    _refine_ultrafast_second_pass(
        locus_calls=locus_calls,
        scheme_type=scheme_type,
        backend=backend,
        sample=sample,
        sample_source=sample_source,
        scheme=scheme,
        minimap2_representative_main_alignment=minimap2_representative_main_alignment,
        ultrafast_second_pass_max_loci=ultrafast_second_pass_max_loci,
        threads=threads,
        count_same_copy=count_same_copy,
        min_identity=min_identity,
        min_coverage=min_coverage,
        effective_min_depth=effective_min_depth,
        adaptive_ultrafast_second_pass_budget_fn=(
            adaptive_ultrafast_second_pass_budget_fn
        ),
        ultrafast_second_pass_rank_fn=ultrafast_second_pass_rank_fn,
        confirm_loci_with_tuned_aligner_fn=confirm_loci_with_tuned_aligner_fn,
        logger=logger,
    )

    _refine_evidence_fallback(
        locus_calls=locus_calls,
        scheme_type=scheme_type,
        backend=backend,
        sample=sample,
        sample_source=sample_source,
        scheme=scheme,
        mode_overrides=mode_overrides,
        threads=threads,
        count_same_copy=count_same_copy,
        min_identity=min_identity,
        min_coverage=min_coverage,
        effective_min_depth=effective_min_depth,
        cache=cache,
        scheme_name=scheme_name,
        provider=provider,
        allele_fastas=allele_fastas,
        force_reindex=force_reindex,
        cgmlst_evidence_fallback_backend_fn=cgmlst_evidence_fallback_backend_fn,
        cgmlst_evidence_fallback_max_loci_fn=cgmlst_evidence_fallback_max_loci_fn,
        low_confidence_loci_fn=low_confidence_loci_fn,
        get_aligner_fn=get_aligner_fn,
        align_evidence_fallback_loci_fn=align_evidence_fallback_loci_fn,
        merge_calls_from_alignment_fn=merge_calls_from_alignment_fn,
        logger=logger,
    )

    return locus_calls
