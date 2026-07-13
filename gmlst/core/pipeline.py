from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gmlst.aligners.base import AlignmentResult, AlleleMatch
from gmlst.calling.st_lookup import STResult
from gmlst.core.types import TypingContext
from gmlst.readers.sample import SampleInput


def _resolve_exact_matches(
    ctx: TypingContext,
    core_mod,
    sample,
) -> dict[str, AlleleMatch]:
    exact_matches: dict[str, AlleleMatch] = {}
    if ctx.use_exact_hash_prefilter and ctx.exact_hash_index:
        exact_matches = core_mod._resolve_exact_cds_matches(
            sample.path,
            ctx.exact_hash_index,
            protein_hash_index=ctx.protein_hash_index,
            sample_cache_root=getattr(ctx.cache, "root", ctx.cache_root),
            cds_prediction_mode=ctx.cds_prediction_mode,
            cds_training_file=ctx.cds_training_file,
            cds_closed_ends=ctx.cds_closed_ends,
        )
        if exact_matches:
            core_mod.logger.info(
                "Exact-hash pre-resolution matched %d loci for %s",
                len(exact_matches),
                sample.path.name,
            )
    return exact_matches


def _finalize_sample_result(
    ctx: TypingContext,
    core_mod,
    sample,
    scheme,
    backend: str,
    sample_source,
    aln: AlignmentResult,
    exact_matches: dict[str, AlleleMatch],
    index_path: Path | None,
) -> tuple[STResult, Path | None]:
    if exact_matches:
        aln = AlignmentResult(
            sample_id=aln.sample_id,
            matches=[*exact_matches.values(), *aln.matches],
            failed_loci=[],
            backend=aln.backend,
            runtime_seconds=aln.runtime_seconds,
        )
    effective_min_depth = ctx.min_depth
    locus_calls = core_mod.call_all_loci(
        aln,
        scheme.loci,
        min_identity=ctx.min_identity,
        min_coverage=ctx.min_coverage,
        min_depth=effective_min_depth,
    )
    locus_calls = core_mod._apply_post_alignment_refinements(
        locus_calls=locus_calls,
        aln=aln,
        aligner=ctx.aligner,
        sample=sample,
        sample_source=sample_source,
        scheme=scheme,
        mode_overrides=ctx.mode_overrides,
        use_minimap2_hash_prefilter=ctx.use_minimap2_hash_prefilter,
        scheme_type=ctx.scheme_type,
        backend=backend,
        kma_fastq_mem_mode=ctx.kma_fastq_mem_mode,
        threads=ctx.threads,
        count_same_copy=ctx.count_same_copy,
        min_identity=ctx.min_identity,
        min_coverage=ctx.min_coverage,
        effective_min_depth=effective_min_depth,
        minimap2_representative_main_alignment=ctx.minimap2_representative_main_alignment,
        ultrafast_second_pass_max_loci=ctx.ultrafast_second_pass_max_loci,
        cache=ctx.cache,
        scheme_name=ctx.scheme_name,
        provider=ctx.provider,
        allele_fastas=ctx.allele_fastas,
        force_reindex=ctx.force_reindex,
    )
    chew_cds_hashes: set[str] | None = None
    chew_cds_sequences: list[str] | None = None
    if (
        ctx.normalized_policy == "chewbbaca"
        and ctx.chew_cds_gate
        and sample.input_type == "fasta"
        and sample.mate_path is None
    ):
        sample_cds_hashes, sample_cds_sequences = (
            core_mod._load_or_build_sample_cds_data(
                sample.path,
                cache_root=getattr(ctx.cache, "root", ctx.cache_root),
                cds_prediction_mode=ctx.cds_prediction_mode,
                cds_training_file=ctx.cds_training_file,
                cds_closed_ends=ctx.cds_closed_ends,
            )
        )
        chew_cds_hashes = {dna_hash for dna_hash, _protein_hash in sample_cds_hashes}
        chew_cds_sequences = sample_cds_sequences

    st_result = core_mod.lookup_st(
        sample.sample_id,
        scheme,
        locus_calls,
        backend=backend,
        runtime_seconds=aln.runtime_seconds,
        call_policy=ctx.normalized_policy,
        chew_style_calls=(
            core_mod.classify_chew_style_calls(
                locus_calls=locus_calls,
                allele_files=scheme.allele_files,
                cds_dna_hashes=chew_cds_hashes,
                cds_sequences=chew_cds_sequences,
                enforce_cds_gate=ctx.chew_cds_gate,
            )
            if ctx.normalized_policy == "chewbbaca"
            else None
        ),
    )
    return st_result, index_path


def _resolve_sample_source(
    sample,
    aligner,
    backend: str,
) -> Path | tuple[Path, Path]:
    if not aligner.supports_fastq and sample.input_type == "fastq":
        raise ValueError(
            f"Backend '{backend}' does not support FASTQ input. Use 'kma'."
        )
    if sample.mate_path is not None:
        return (sample.path, sample.mate_path)
    return sample.path


def _run_prefilter_phase(
    ctx: TypingContext,
    core_mod,
    sample,
    scheme,
    aligner,
    backend: str,
    sample_source,
    exact_matches: dict[str, AlleleMatch],
    index_path: Path | None,
) -> tuple[AlignmentResult, Path | None]:
    with core_mod.temp_dir("gmlst_cgpf_") as tmp:
        prefilter_start = core_mod.time.perf_counter()
        representative_aln: core_mod.AlignmentResult | None = None
        if ctx.use_minimap2_hash_prefilter:
            candidates, representative_aln = (
                core_mod._minimap2_representative_prefilter_candidates(
                    aligner=aligner,
                    sample_path=sample.path,
                    loci=scheme.loci,
                    representatives=ctx.minimap2_prefilter_representatives,
                    representative_index_path=ctx.minimap2_prefilter_index_path,
                    min_identity=ctx.min_identity,
                    min_coverage=0.8,
                )
            )
        else:
            candidates = core_mod.prefilter_assembly_candidates(
                allele_sequences=ctx.prefilter_alleles or {},
                assembly_sequences=core_mod._iter_fasta_sequences(sample.path),
                k=ctx.prefilter_k,
                top_n=ctx.effective_prefilter_top_n,
                stride=ctx.effective_prefilter_stride,
            )
        prefilter_elapsed = core_mod.time.perf_counter() - prefilter_start
        core_mod.logger.info(
            "Prefilter completed in %.3fs for %s (%d loci candidates)",
            prefilter_elapsed,
            sample.path.name,
            len(candidates),
        )
        if not core_mod._prefilter_is_confident(
            candidates,
            total_loci=len(scheme.loci),
            min_loci_fraction=ctx.prefilter_min_loci_fraction,
        ):
            candidates = {}
        if ctx.use_minimap2_hash_prefilter:
            if (
                ctx.minimap2_representative_main_alignment
                and sample.input_type == "fasta"
            ):
                candidate_fastas = []
                core_mod.logger.info(
                    "Representative-only minimap2 main alignment enabled for %s",
                    sample.path.name,
                )
            else:
                candidate_loci = set(candidates.keys()) - set(exact_matches.keys())
                candidate_top_n = (
                    ctx.mode_overrides.minimap2_hash_locus_top_n
                    if ctx.mode_overrides.minimap2_hash_locus_top_n is not None
                    else core_mod._minimap2_hash_locus_top_n()
                )
                if (
                    candidate_top_n > 0
                    and ctx.allele_sequence_cache is not None
                    and candidate_loci
                ):
                    candidate_alleles = {
                        (locus, allele_id): sequence
                        for locus in candidate_loci
                        for allele_id, sequence in ctx.allele_sequence_cache.get(
                            locus, {}
                        ).items()
                    }
                    ranked_candidates = core_mod.prefilter_assembly_candidates(
                        allele_sequences=candidate_alleles,
                        assembly_sequences=core_mod._iter_fasta_sequences(sample.path),
                        k=ctx.prefilter_k,
                        top_n=candidate_top_n,
                        stride=ctx.effective_prefilter_stride,
                    )
                    candidate_fastas = core_mod._write_candidate_fastas(
                        ctx.allele_sequence_cache,
                        ranked_candidates,
                        tmp,
                    )
                    unresolved_candidate_loci = candidate_loci - set(
                        ranked_candidates.keys()
                    )
                    if unresolved_candidate_loci:
                        candidate_fastas.extend(
                            core_mod._select_candidate_locus_fastas(
                                scheme.allele_files,
                                unresolved_candidate_loci,
                            )
                        )
                    core_mod.logger.info(
                        "Minimap2 hash candidate narrowing retained "
                        "%d/%d loci at top_n=%d",
                        len(candidate_loci) - len(unresolved_candidate_loci),
                        len(candidate_loci),
                        candidate_top_n,
                    )
                else:
                    candidate_fastas = core_mod._select_candidate_locus_fastas(
                        scheme.allele_files,
                        candidate_loci,
                    )
        else:
            if exact_matches:
                candidates = {
                    locus: ranked
                    for locus, ranked in candidates.items()
                    if locus not in exact_matches
                }
            candidate_fastas = core_mod._write_candidate_fastas(
                ctx.allele_sequence_cache,
                candidates,
                tmp,
            )
        if candidate_fastas:
            sample_index_dir = tmp / "idx"
            sample_index_dir.mkdir(parents=True, exist_ok=True)
            if backend == "minimap2" and sample.input_type == "fasta":
                core_mod._write_merged_fasta(
                    candidate_fastas,
                    sample_index_dir / "alleles.fasta",
                )
                sample_index_path = sample_index_dir
                core_mod.logger.info(
                    "Prepared minimap2 FASTA candidate database for %s "
                    "without building .mmi index (%d files)",
                    sample.path.name,
                    len(candidate_fastas),
                )
            else:
                index_start = core_mod.time.perf_counter()
                sample_index_path = aligner.index(candidate_fastas, sample_index_dir)
                index_elapsed = core_mod.time.perf_counter() - index_start
                core_mod.logger.info(
                    "Candidate index build completed in %.3fs for %s (%d files)",
                    index_elapsed,
                    sample.path.name,
                    len(candidate_fastas),
                )
        else:
            if (
                ctx.use_minimap2_hash_prefilter
                and backend == "minimap2"
                and sample.input_type == "fasta"
                and ctx.minimap2_representative_main_alignment
                and representative_aln is not None
            ):
                sample_index_path = (
                    ctx.minimap2_prefilter_index_path
                    if ctx.minimap2_prefilter_index_path is not None
                    else ctx.index_dir
                )
            else:
                if index_path is None:
                    index_path = core_mod._ensure_full_index(
                        aligner=aligner,
                        backend=backend,
                        scheme_name=ctx.scheme_name,
                        allele_fastas=ctx.allele_fastas,
                        index_dir=ctx.index_dir,
                        force_reindex=ctx.force_reindex,
                    )
                sample_index_path = index_path
                core_mod.logger.info(
                    "Using persistent full index for %s after prefilter fallback",
                    sample.path.name,
                )
        align_start = core_mod.time.perf_counter()
        residual_loci = [locus for locus in scheme.loci if locus not in exact_matches]
        if (
            residual_loci
            and ctx.use_minimap2_hash_prefilter
            and backend == "minimap2"
            and sample.input_type == "fasta"
            and ctx.minimap2_representative_main_alignment
            and representative_aln is not None
        ):
            representative_matches = [
                match
                for match in representative_aln.matches
                if match.locus in residual_loci
            ]
            aln = core_mod.AlignmentResult(
                sample_id=representative_aln.sample_id,
                matches=representative_matches,
                failed_loci=[
                    locus
                    for locus in residual_loci
                    if locus not in {match.locus for match in representative_matches}
                ],
                backend=representative_aln.backend,
                runtime_seconds=representative_aln.runtime_seconds,
            )
            core_mod.logger.info(
                "Using representative-only minimap2 main alignment for %s",
                sample.path.name,
            )
        elif residual_loci:
            aln = aligner.align(
                sample_source,
                sample_index_path,
                residual_loci,
                sample.input_type,
            )
        else:
            aln = core_mod.AlignmentResult(
                sample_id=sample.sample_id,
                matches=[],
                failed_loci=[],
                backend=backend,
                runtime_seconds=0.0,
            )
        align_elapsed = core_mod.time.perf_counter() - align_start
        core_mod.logger.info(
            "Alignment completed in %.3fs for %s",
            align_elapsed,
            sample.path.name,
        )
    return aln, index_path


def _run_direct_alignment_phase(
    core_mod,
    sample,
    scheme,
    aligner,
    backend: str,
    sample_source,
    exact_matches: dict[str, AlleleMatch],
    index_path: Path | None,
) -> AlignmentResult:
    if index_path is None:
        raise RuntimeError("missing aligner index path")
    align_start = core_mod.time.perf_counter()
    residual_loci = [locus for locus in scheme.loci if locus not in exact_matches]
    if residual_loci:
        aln = aligner.align(
            sample_source,
            index_path,
            residual_loci,
            sample.input_type,
        )
    else:
        aln = core_mod.AlignmentResult(
            sample_id=sample.sample_id,
            matches=[],
            failed_loci=[],
            backend=backend,
            runtime_seconds=0.0,
        )
    align_elapsed = core_mod.time.perf_counter() - align_start
    core_mod.logger.info(
        "Alignment completed in %.3fs for %s",
        align_elapsed,
        sample.path.name,
    )
    return aln


def _type_single_sample(ctx: TypingContext) -> tuple[STResult, Path | None]:
    core_mod = ctx.core
    sample = ctx.sample
    scheme = ctx.scheme
    backend = ctx.backend
    aligner = ctx.aligner
    index_path = ctx.index_path

    core_mod.logger.info("Typing %s with %s …", sample.path.name, backend)

    sample_source = _resolve_sample_source(sample, aligner, backend)
    exact_matches = _resolve_exact_matches(ctx, core_mod, sample)

    if ctx.use_prefilter:
        aln, index_path = _run_prefilter_phase(
            ctx,
            core_mod,
            sample,
            scheme,
            aligner,
            backend,
            sample_source,
            exact_matches,
            index_path,
        )
    else:
        aln = _run_direct_alignment_phase(
            core_mod,
            sample,
            scheme,
            aligner,
            backend,
            sample_source,
            exact_matches,
            index_path,
        )

    return _finalize_sample_result(
        ctx,
        core_mod,
        sample,
        scheme,
        backend,
        sample_source,
        aln,
        exact_matches,
        index_path,
    )


def _setup_typing_config(
    core,
    sample_paths: list[Path | SampleInput],
    scheme_name: str,
    backend: str,
    *,
    provider: str,
    scheme_type: str,
    cgmlst_mode: str,
    cache_root: Path | None,
    min_identity: float,
    min_coverage: float,
    min_depth: float,
    force_reindex: bool,
    threads: int,
    count_same_copy: bool,
    prefilter_enabled: bool,
    prefilter_k: int,
    prefilter_top_n: int,
    prefilter_min_loci_fraction: float,
    cds_coordinates_out: Path | None,
    call_policy: str,
    chew_cds_gate: bool,
) -> tuple[TypingContext, list[SampleInput]]:
    cache = core.DatabaseCache(cache_root)
    normalized_policy = call_policy.strip().lower()
    if normalized_policy not in {"default", "chewbbaca"}:
        raise ValueError(
            f"Unknown call policy '{call_policy}'. Supported: default, chewbbaca."
        )

    scheme = cache.ensure_scheme(
        scheme_name,
        provider=provider,
        scheme_type=scheme_type,
    )

    mode_overrides = core._cgmlst_mode_overrides(
        cgmlst_mode=cgmlst_mode,
        scheme_type=scheme_type,
        backend=backend,
    )
    minimap2_fasta_emit_cigar = (
        mode_overrides.minimap2_fasta_emit_cigar
        if mode_overrides.minimap2_fasta_emit_cigar is not None
        else core._minimap2_fasta_emit_cigar_enabled()
    )
    minimap2_fasta_speed_profile = (
        mode_overrides.minimap2_fasta_speed_profile
        if mode_overrides.minimap2_fasta_speed_profile is not None
        else core._minimap2_fasta_speed_profile()
    )
    kma_fastq_mem_mode = backend == "kma" and core._kma_fastq_mem_mode_enabled()
    minimap2_representative_main_alignment = (
        mode_overrides.minimap2_representative_main_alignment
        if mode_overrides.minimap2_representative_main_alignment is not None
        else core._minimap2_representative_main_alignment()
    )
    ultrafast_second_pass_max_loci = core._minimap2_ultrafast_second_pass_max_loci()
    if ultrafast_second_pass_max_loci is None:
        ultrafast_second_pass_max_loci = (
            mode_overrides.minimap2_ultrafast_second_pass_max_loci
        )

    aligner = core.get_aligner(
        backend,
        threads=threads,
        count_same_copy=count_same_copy,
        fasta_emit_cigar=minimap2_fasta_emit_cigar,
        fasta_speed_profile=minimap2_fasta_speed_profile,
        fastq_mem_mode=kma_fastq_mem_mode,
    )
    aligner.check_dependencies()

    samples = [
        sample_path
        if isinstance(sample_path, SampleInput)
        else core.detect_sample(sample_path)
        for sample_path in sample_paths
    ]

    index_dir = cache.index_dir(scheme_name, backend, provider=provider)
    allele_fastas = list(scheme.allele_files.values())
    minimap2_hash_prefilter_enabled = (
        core._minimap2_hash_prefilter_enabled()
        or mode_overrides.minimap2_hash_prefilter
    )
    exact_hash_prefilter_enabled = (
        core._exact_hash_prefilter_enabled() or mode_overrides.exact_hash_prefilter
    )
    protein_exact_hash_prefilter_enabled = mode_overrides.protein_exact_hash_prefilter
    use_prefilter = (
        prefilter_enabled
        and scheme_type == "cgmlst"
        and (
            backend in {"blastn", "nucmer"}
            or (backend == "minimap2" and minimap2_hash_prefilter_enabled)
        )
        and all(
            sample.input_type == "fasta" and sample.mate_path is None
            for sample in samples
        )
    )
    if (
        prefilter_enabled
        and scheme_type == "cgmlst"
        and (
            backend == "kma"
            or (backend == "minimap2" and not minimap2_hash_prefilter_enabled)
        )
    ):
        core.logger.info(
            "Skipping cgMLST prefilter for backend '%s' and using "
            "persistent full index",
            backend,
        )
    prefilter_max_loci = core._cgmlst_prefilter_max_loci()
    if (
        use_prefilter
        and prefilter_max_loci > 0
        and len(scheme.loci) > prefilter_max_loci
    ):
        core.logger.info(
            "Skipping cgMLST prefilter for scheme '%s': %d loci exceed limit %d",
            scheme_name,
            len(scheme.loci),
            prefilter_max_loci,
        )
        use_prefilter = False

    effective_prefilter_top_n = (
        max(prefilter_top_n, 80) if backend == "minimap2" else prefilter_top_n
    )
    effective_prefilter_stride = 1

    index_path: Path | None = None
    if not use_prefilter:
        index_path = core._ensure_full_index(
            aligner=aligner,
            backend=backend,
            scheme_name=scheme_name,
            allele_fastas=allele_fastas,
            index_dir=index_dir,
            force_reindex=force_reindex,
        )

    use_minimap2_hash_prefilter = (
        backend == "minimap2" and minimap2_hash_prefilter_enabled
    )
    use_exact_hash_prefilter = (
        scheme_type == "cgmlst"
        and exact_hash_prefilter_enabled
        and all(
            sample.input_type == "fasta" and sample.mate_path is None
            for sample in samples
        )
    )
    if use_prefilter and use_minimap2_hash_prefilter and not use_exact_hash_prefilter:
        prefilter_alleles = core._load_representative_allele_sequences(
            scheme.allele_files
        )
        allele_sequence_cache = None
    else:
        allele_sequence_cache = (
            core._load_scheme_allele_sequences(scheme.allele_files)
            if (use_prefilter or use_exact_hash_prefilter)
            else None
        )
        prefilter_alleles = (
            core._flatten_allele_sequences(allele_sequence_cache)
            if allele_sequence_cache is not None
            else None
        )
    minimap2_prefilter_representatives = (
        core._representatives_from_nested_alleles(allele_sequence_cache)
        if allele_sequence_cache is not None
        else core._load_representative_allele_sequences(scheme.allele_files)
    )
    exact_hash_index: dict[str, list[tuple[str, str]]] | None = None
    protein_hash_index: dict[str, list[tuple[str, str]]] | None = None
    if use_exact_hash_prefilter and allele_sequence_cache is not None:
        exact_hash_index, protein_hash_index = core._load_or_build_exact_hash_indexes(
            allele_files=scheme.allele_files,
            allele_sequences=allele_sequence_cache,
            include_protein=protein_exact_hash_prefilter_enabled,
        )
    minimap2_prefilter_index_path: Path | None = None
    if use_prefilter and use_minimap2_hash_prefilter:
        minimap2_prefilter_index_path = (
            core._load_or_build_minimap2_representative_index(
                aligner=aligner,
                index_dir=cache.index_dir(
                    scheme_name,
                    "minimap2_representatives",
                    provider=provider,
                ),
                representatives=minimap2_prefilter_representatives,
                force_reindex=force_reindex,
            )
        )

    cds_prediction_mode = core._cgmlst_cds_prediction_mode()
    cds_closed_ends = core._cgmlst_cds_closed_ends()
    cds_training_file = core._resolve_cgmlst_cds_training_file(
        allele_files=scheme.allele_files,
        sample_paths=[sample.path for sample in samples],
        mode=cds_prediction_mode,
    )
    effective_cds_coordinates_out = (
        cds_coordinates_out or core._cgmlst_cds_coordinates_out()
    )
    if effective_cds_coordinates_out is not None:
        core._write_cds_coordinates(
            samples=samples,
            output_path=effective_cds_coordinates_out,
            prediction_mode=cds_prediction_mode,
            training_file=cds_training_file,
            closed_ends=cds_closed_ends,
        )

    base_ctx = TypingContext(
        core=core,
        sample=None,
        scheme=scheme,
        backend=backend,
        aligner=aligner,
        cache=cache,
        cache_root=cache_root,
        scheme_name=scheme_name,
        provider=provider,
        mode_overrides=mode_overrides,
        scheme_type=scheme_type,
        use_prefilter=use_prefilter,
        use_minimap2_hash_prefilter=use_minimap2_hash_prefilter,
        use_exact_hash_prefilter=use_exact_hash_prefilter,
        exact_hash_index=exact_hash_index,
        protein_hash_index=protein_hash_index,
        allele_sequence_cache=allele_sequence_cache,
        prefilter_alleles=prefilter_alleles,
        minimap2_prefilter_representatives=minimap2_prefilter_representatives,
        minimap2_prefilter_index_path=minimap2_prefilter_index_path,
        prefilter_k=prefilter_k,
        effective_prefilter_top_n=effective_prefilter_top_n,
        effective_prefilter_stride=effective_prefilter_stride,
        prefilter_min_loci_fraction=prefilter_min_loci_fraction,
        index_dir=index_dir,
        index_path=index_path,
        allele_fastas=allele_fastas,
        force_reindex=force_reindex,
        min_identity=min_identity,
        min_coverage=min_coverage,
        min_depth=min_depth,
        threads=threads,
        count_same_copy=count_same_copy,
        kma_fastq_mem_mode=kma_fastq_mem_mode,
        minimap2_representative_main_alignment=minimap2_representative_main_alignment,
        ultrafast_second_pass_max_loci=ultrafast_second_pass_max_loci,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
        normalized_policy=normalized_policy,
        chew_cds_gate=chew_cds_gate,
    )
    return base_ctx, samples


def _type_all_samples(
    base_ctx: TypingContext,
    samples: list[SampleInput],
    on_result: Callable[[STResult], None] | None,
) -> list[STResult]:
    results: list[STResult] = []
    index_path = base_ctx.index_path
    for sample in samples:
        ctx = base_ctx.evolve(sample=sample, index_path=index_path)
        st_result, index_path = _type_single_sample(ctx)
        results.append(st_result)
        if on_result is not None:
            on_result(st_result)
    return results


def run_typing_impl(
    sample_paths: list[Path | SampleInput],
    scheme_name: str,
    backend: str,
    *,
    provider: str = "pubmlst",
    scheme_type: str = "mlst",
    cgmlst_mode: str = "standard",
    cache_root: Path | None = None,
    min_identity: float = 95.0,
    min_coverage: float = 0.95,
    min_depth: float = 10.0,
    force_reindex: bool = False,
    threads: int = 1,
    count_same_copy: bool = False,
    prefilter_enabled: bool = True,
    prefilter_k: int = 31,
    prefilter_top_n: int = 20,
    prefilter_min_loci_fraction: float = 0.3,
    cds_coordinates_out: Path | None = None,
    call_policy: str = "default",
    chew_cds_gate: bool = True,
    on_result: Callable[[STResult], None] | None = None,
) -> list[STResult]:
    import gmlst.core as core

    base_ctx, samples = _setup_typing_config(
        core,
        sample_paths,
        scheme_name,
        backend,
        provider=provider,
        scheme_type=scheme_type,
        cgmlst_mode=cgmlst_mode,
        cache_root=cache_root,
        min_identity=min_identity,
        min_coverage=min_coverage,
        min_depth=min_depth,
        force_reindex=force_reindex,
        threads=threads,
        count_same_copy=count_same_copy,
        prefilter_enabled=prefilter_enabled,
        prefilter_k=prefilter_k,
        prefilter_top_n=prefilter_top_n,
        prefilter_min_loci_fraction=prefilter_min_loci_fraction,
        cds_coordinates_out=cds_coordinates_out,
        call_policy=call_policy,
        chew_cds_gate=chew_cds_gate,
    )
    return _type_all_samples(base_ctx, samples, on_result)
