from __future__ import annotations

import sys
from pathlib import Path


def normalize_cgmlst_fastq_runtime(
    *,
    mode: str,
    prepared_samples: list[Path | object],
    normalized_policy: str,
    backend: str,
    cgmlst_mode: str,
    max_workers: int,
    threads: int,
    contains_fastq_samples_fn,
    fastq_kma_auto_threads_fn,
    console,
    err_console,
) -> tuple[str, str, int]:
    contains_fastq_samples = contains_fastq_samples_fn(prepared_samples)
    if mode != "cgmlst" or not contains_fastq_samples:
        return backend, cgmlst_mode, threads

    if normalized_policy == "chewbbaca":
        err_console.print(
            "[red]Error:[/red] --call-policy chewbbaca requires FASTA assemblies."
        )
        sys.exit(1)
    if backend.lower() == "minimap2":
        console.print(
            "[yellow]Warning:[/yellow] FASTQ cgMLST with minimap2 is much slower "
            "and mode optimizations are FASTA-oriented. "
            "Switching backend to [cyan]kma[/cyan]."
        )
        backend = "kma"
    if cgmlst_mode != "standard":
        console.print(
            "[yellow]Warning:[/yellow] FASTQ cgMLST currently treats "
            "[cyan]--cgmlst-mode[/cyan] as compatibility-only. "
            "Forcing mode to [cyan]standard[/cyan]."
        )
        cgmlst_mode = "standard"
    if backend.lower() == "kma" and max_workers <= 1 and threads == 1:
        auto_threads = fastq_kma_auto_threads_fn()
        if auto_threads > 1:
            console.print(
                "[yellow]Warning:[/yellow] FASTQ cgMLST with kma on "
                "a single thread is slow. Auto-setting per-sample threads "
                f"to [cyan]{auto_threads}[/cyan]."
            )
            threads = auto_threads

    return backend, cgmlst_mode, threads
