from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def execute_typing_run(
    *,
    run_typing_fn,
    prepared_samples: list[Path | object],
    scheme_name: str,
    backend: str,
    provider: str,
    scheme_type: str,
    cgmlst_mode: str,
    cache_root,
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
    cds_coordinates_out,
    call_policy: str,
    chew_cds_gate: bool,
    max_workers: int,
    on_result,
    console,
) -> list:
    if max_workers > 1 and len(prepared_samples) > 1:
        if threads != 1:
            console.print(
                "[yellow]Warning:[/yellow] --max-workers uses sample-level "
                "parallelism; forcing per-sample backend threads to 1."
            )
        if backend.lower() in {"kma", "minimap2"}:
            _ = run_typing_fn(
                sample_paths=[],
                scheme_name=scheme_name,
                backend=backend,
                provider=provider,
                scheme_type=scheme_type,
                cgmlst_mode=cgmlst_mode,
                cache_root=cache_root,
                min_identity=min_identity,
                min_coverage=min_coverage,
                min_depth=min_depth,
                force_reindex=force_reindex,
                threads=1,
                count_same_copy=count_same_copy,
                prefilter_enabled=prefilter_enabled,
                prefilter_k=prefilter_k,
                prefilter_top_n=prefilter_top_n,
                prefilter_min_loci_fraction=prefilter_min_loci_fraction,
                cds_coordinates_out=cds_coordinates_out,
                call_policy=call_policy,
                chew_cds_gate=chew_cds_gate,
                on_result=None,
            )

        def _worker(sample_entry: Path | object) -> list:
            return run_typing_fn(
                sample_paths=[sample_entry],
                scheme_name=scheme_name,
                backend=backend,
                provider=provider,
                scheme_type=scheme_type,
                cgmlst_mode=cgmlst_mode,
                cache_root=cache_root,
                min_identity=min_identity,
                min_coverage=min_coverage,
                min_depth=min_depth,
                force_reindex=False,
                threads=1,
                count_same_copy=count_same_copy,
                prefilter_enabled=prefilter_enabled,
                prefilter_k=prefilter_k,
                prefilter_top_n=prefilter_top_n,
                prefilter_min_loci_fraction=prefilter_min_loci_fraction,
                cds_coordinates_out=cds_coordinates_out,
                call_policy=call_policy,
                chew_cds_gate=chew_cds_gate,
                on_result=None,
            )

        futures: dict[object, int] = {}
        ordered_results: list[object | None] = [None for _ in prepared_samples]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for idx, sample_entry in enumerate(prepared_samples):
                future = executor.submit(_worker, sample_entry)
                futures[future] = idx
            for future in as_completed(futures):
                idx = futures[future]
                batch = future.result()
                ordered_results[idx] = batch[0] if batch else None

        results = [result for result in ordered_results if result is not None]
        for result in results:
            on_result(result)
        return results

    return run_typing_fn(
        sample_paths=prepared_samples,
        scheme_name=scheme_name,
        backend=backend,
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
        on_result=on_result,
    )
