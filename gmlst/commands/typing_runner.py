from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


def _make_progress(quiet: bool) -> Progress | None:
    if quiet:
        return None
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        transient=False,
    )


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
    quiet: bool = False,
) -> list:
    total = len(prepared_samples)
    progress = _make_progress(quiet and total > 1)
    show_progress = progress is not None and total > 1

    if max_workers > 1 and total > 1:
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
        next_flush_idx = 0
        flush_lock = threading.Lock()
        completed_count = 0

        def _try_flush() -> None:
            nonlocal next_flush_idx, completed_count
            with flush_lock:
                while next_flush_idx < len(ordered_results):
                    result = ordered_results[next_flush_idx]
                    if result is None:
                        break
                    on_result(result)
                    next_flush_idx += 1
                    completed_count += 1
                    if task_id is not None:
                        progress.update(task_id, completed=completed_count)

        task_id = None
        ctx = progress if progress is not None else _NullCtx()

        with ctx:
            if show_progress:
                task_id = progress.add_task(
                    f"Typing ({max_workers} workers)", total=total
                )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for idx, sample_entry in enumerate(prepared_samples):
                    future = executor.submit(_worker, sample_entry)
                    futures[future] = idx
                for future in as_completed(futures):
                    idx = futures[future]
                    batch = future.result()
                    ordered_results[idx] = batch[0] if batch else None
                    _try_flush()

        results = [r for r in ordered_results if r is not None]
        return results

    task_id = None
    ctx = progress if progress is not None else _NullCtx()

    with ctx:
        if show_progress:
            task_id = progress.add_task(f"Typing ({backend})", total=total)
        original_on_result = on_result

        def _progress_on_result(result):
            original_on_result(result)
            if task_id is not None:
                nonlocal_count[0] += 1
                progress.update(task_id, completed=nonlocal_count[0])

        nonlocal_count = [0]

        results = run_typing_fn(
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
            on_result=_progress_on_result if show_progress else on_result,
        )

    return results


class _NullCtx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
