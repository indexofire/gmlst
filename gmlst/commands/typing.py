"""Typing command for gmlst."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from gmlst.calling.scoring import passes_minscore
from gmlst.commands.common import (
    HELP_SETTINGS,
    backend_option,
    emit_versioned_json,
    err_console,
    novel_data_options,
    status_console,
    typing_output_options,
    typing_parallel_options,
    typing_threshold_options,
)
from gmlst.commands.typing_fastq import (
    contains_fastq_samples,
    fastq_kma_auto_threads,
    maybe_subsample_fastq,
    prepare_sample_paths_for_pairing,
    temp_root_from_output,
)
from gmlst.commands.typing_guess_run import _run_guess_typing
from gmlst.commands.typing_output import (
    announce_stream_output_written,
    close_stream_output,
    emit_final_typing_output,
    emit_streamed_result,
    open_stream_output,
    stream_header_if_needed,
)
from gmlst.commands.typing_runner import execute_typing_run
from gmlst.commands.typing_runtime import normalize_cgmlst_fastq_runtime
from gmlst.commands.typing_scheme import (
    effective_scheme_type,
    resolve_scheme_type,
    validate_scheme_mode,
)
from gmlst.commands.typing_schemefree import cmd_typing_tgmlst
from gmlst.commands.typing_species import resolve_scheme_for_typing
from gmlst.core import run_typing
from gmlst.database.cache import DatabaseCache
from gmlst.database.schema import Scheme
from gmlst.genbank_io import ensure_fasta_samples
from gmlst.novel import NovelAlleleWriter, NovelProfileWriter
from gmlst.novel.service import create_novel_writers, finalize_novel_typing_outputs
from gmlst.schema_versions import TYPING_RESULTS_V1
from gmlst.utils import setup_logging

logger = logging.getLogger(__name__)


def _emit_typing_results_json(data: object, output: Path | None) -> bool:
    """Emit typing results wrapped in the ``gmlst-typing-v1`` envelope."""
    return emit_versioned_json(data, output, TYPING_RESULTS_V1)


if TYPE_CHECKING:
    from gmlst.calling.st_lookup import STResult


@click.group(
    "typing",
    context_settings=HELP_SETTINGS,
    no_args_is_help=True,
)
def cmd_typing() -> None:
    """Typing command group: mlst, cgmlst, and tgmlst modes."""


cmd_typing.add_command(cmd_typing_tgmlst)


def _validate_guess_flags(
    guess: bool,
    scheme: str | None,
    organism: str | None,
    novel_allele: bool,
    novel_profile: bool,
) -> None:
    if not guess:
        return
    if scheme is not None or organism is not None:
        raise click.UsageError("--guess cannot be combined with -s or -n.")
    if novel_allele or novel_profile:
        raise click.UsageError("--guess cannot be combined with novel flags.")


@cmd_typing.command("mlst", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.argument(
    "samples",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--scheme",
    "-s",
    default=None,
    help="MLST scheme name, e.g. 'saureus_1' (omit to auto-detect species).",
)
@click.option(
    "--organism",
    "-n",
    default=None,
    help="Resolve the scheme by organism or scheme-name substring, e.g. 'bordetella'.",
)
@click.option(
    "--guess",
    "-g",
    is_flag=True,
    help=(
        "Unattended mixed-species typing: detect each assembly's species, "
        "pick the scheme automatically (downloading if needed), and never "
        "prompt. Incompatible with -s/-n and the novel flags."
    ),
)
@backend_option("blastn")
@typing_threshold_options
@typing_output_options
@typing_parallel_options
@click.option(
    "--count-same-copy",
    is_flag=True,
    help=(
        "Count same-allele multicopy hits (currently blastn) "
        "and show notation like 1,1."
    ),
)
@click.option(
    "--max-depth",
    "max_fastq_depth",
    default=100,
    show_default=True,
    type=click.FloatRange(min=0),
    help="Subsample FASTQ to this depth (0=disabled, FASTQ only).",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error logging.")
@click.option(
    "--detail",
    is_flag=True,
    help="Show contig position info in TSV output (FASTA only).",
)
@novel_data_options
def cmd_typing_mlst(
    samples: tuple[Path, ...],
    scheme: str | None,
    organism: str | None,
    guess: bool,
    backend: str,
    min_id: float,
    min_cov: float,
    min_depth: float,
    min_join_overlap: int,
    minscore: float,
    fmt: str,
    output: Path | None,
    cache_dir: Path | None,
    force_reindex: bool,
    no_header: bool,
    threads: int,
    max_workers: int,
    count_same_copy: bool,
    max_fastq_depth: float,
    quiet: bool,
    detail: bool,
    novel_allele: bool,
    novel_profile: bool,
    output_dir: Path | None,
) -> None:
    """Type samples against MLST schemes only."""
    if quiet:
        setup_logging(verbose=False, quiet=True)
    _validate_guess_flags(guess, scheme, organism, novel_allele, novel_profile)
    if guess:
        exit_code = _run_guess_typing(
            mode="mlst",
            samples=samples,
            backend=backend,
            cgmlst_mode="fast",
            min_id=min_id,
            min_cov=min_cov,
            min_depth=min_depth,
            min_join_overlap=min_join_overlap,
            minscore=minscore,
            fmt=fmt,
            output=output,
            cache_dir=cache_dir,
            force_reindex=force_reindex,
            no_header=no_header,
            threads=threads,
            max_workers=max_workers,
            count_same_copy=count_same_copy,
            quiet=quiet,
            detail=detail,
        )
        if exit_code != 0:
            sys.exit(exit_code)
        return
    with ensure_fasta_samples(samples) as samples_fasta:
        scheme = resolve_scheme_for_typing(
            mode="mlst",
            scheme=scheme,
            organism=organism,
            samples=samples_fasta,
            cache_dir=cache_dir,
        )
        _run_mlst_like_typing(
            mode="mlst",
            samples=samples_fasta,
            scheme=scheme,
            backend=backend,
            min_id=min_id,
            min_cov=min_cov,
            min_depth=min_depth,
            min_join_overlap=min_join_overlap,
            minscore=minscore,
            fmt=fmt,
            output=output,
            cache_dir=cache_dir,
            force_reindex=force_reindex,
            no_header=no_header,
            threads=threads,
            max_workers=max_workers,
            count_same_copy=count_same_copy,
            provider=None,
            novel_allele=novel_allele,
            novel_profile=novel_profile,
            output_dir=output_dir,
            quiet=quiet,
            detail=detail,
        )


@cmd_typing.command("cgmlst", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.argument(
    "samples",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--scheme",
    "-s",
    default=None,
    help="cgMLST/wgMLST scheme name, e.g. 'vparahaemolyticus_3' (omit to auto-detect).",
)
@click.option(
    "--organism",
    "-n",
    default=None,
    help="Resolve the scheme by organism or scheme-name substring, e.g. 'vibrio'.",
)
@click.option(
    "--guess",
    "-g",
    is_flag=True,
    help=(
        "Unattended mixed-species typing: detect each assembly's species, "
        "pick the scheme automatically (downloading if needed), and never "
        "prompt. Incompatible with -s/-n and the novel flags."
    ),
)
@backend_option("minimap2")
@click.option(
    "--cgmlst-mode",
    type=click.Choice(
        [
            "fast",
            "ultrafast",
            "balanced",
        ],
        case_sensitive=False,
    ),
    default="fast",
    show_default=True,
    help="cgMLST workflow mode.",
)
@typing_threshold_options
@typing_output_options
@typing_parallel_options
@click.option(
    "--count-same-copy",
    is_flag=True,
    help=(
        "Count same-allele multicopy hits (currently blastn) "
        "and show notation like 1,1."
    ),
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error logging.")
@click.option(
    "--prefilter-k",
    type=click.IntRange(min=11),
    default=31,
    show_default=True,
    help="k-mer length for cgMLST assembly prefilter.",
)
@click.option(
    "--prefilter-top-n",
    type=click.IntRange(min=1),
    default=20,
    show_default=True,
    help="Top N allele candidates per locus from prefilter.",
)
@click.option(
    "--prefilter-min-loci-fraction",
    type=click.FloatRange(min=0.0, max=1.0),
    default=0.3,
    show_default=True,
    help="Minimum loci fraction required to trust prefilter results.",
)
@click.option(
    "--no-prefilter",
    is_flag=True,
    help="Disable cgMLST assembly prefilter and use full-locus backend indexing.",
)
@novel_data_options
@click.option(
    "--cds-coordinates-out",
    type=click.Path(path_type=Path),
    help="Write predicted CDS coordinates TSV for alignment with chewBBACA outputs.",
)
@click.option(
    "--call-policy",
    type=click.Choice(["default", "chewbbaca", "chew-exact"], case_sensitive=False),
    default="default",
    show_default=True,
    help=(
        "Allele decision policy. "
        "chewbbaca: chewBBACA labels. "
        "chew-exact: forces single mode + CDS gate."
    ),
)
@click.option(
    "--chew-cds-gate/--no-chew-cds-gate",
    default=True,
    show_default=True,
    help=(
        "When --call-policy chewbbaca is enabled, require allele evidence to pass "
        "predicted-CDS gate before numeric classification."
    ),
)
def cmd_typing_cgmlst(
    samples: tuple[Path, ...],
    scheme: str | None,
    organism: str | None,
    guess: bool,
    backend: str,
    cgmlst_mode: str,
    min_id: float,
    min_cov: float,
    min_depth: float,
    min_join_overlap: int,
    minscore: float,
    fmt: str,
    output: Path | None,
    cache_dir: Path | None,
    force_reindex: bool,
    no_header: bool,
    threads: int,
    max_workers: int,
    count_same_copy: bool,
    quiet: bool,
    prefilter_k: int,
    prefilter_top_n: int,
    prefilter_min_loci_fraction: float,
    no_prefilter: bool,
    novel_allele: bool,
    novel_profile: bool,
    output_dir: Path | None,
    cds_coordinates_out: Path | None,
    call_policy: str,
    chew_cds_gate: bool,
) -> None:
    """Type samples against cgMLST/wgMLST schemes only."""
    if quiet:
        setup_logging(verbose=False, quiet=True)
    _validate_guess_flags(guess, scheme, organism, novel_allele, novel_profile)
    if guess:
        exit_code = _run_guess_typing(
            mode="cgmlst",
            samples=samples,
            backend=backend,
            cgmlst_mode=cgmlst_mode,
            min_id=min_id,
            min_cov=min_cov,
            min_depth=min_depth,
            min_join_overlap=min_join_overlap,
            minscore=minscore,
            fmt=fmt,
            output=output,
            cache_dir=cache_dir,
            force_reindex=force_reindex,
            no_header=no_header,
            threads=threads,
            max_workers=max_workers,
            count_same_copy=count_same_copy,
            quiet=quiet,
            detail=False,
        )
        if exit_code != 0:
            sys.exit(exit_code)
        return
    with ensure_fasta_samples(samples) as samples_fasta:
        scheme = resolve_scheme_for_typing(
            mode="cgmlst",
            scheme=scheme,
            organism=organism,
            samples=samples_fasta,
            cache_dir=cache_dir,
        )
        _run_mlst_like_typing(
            mode="cgmlst",
            samples=samples_fasta,
            scheme=scheme,
            backend=backend,
            cgmlst_mode=cgmlst_mode,
            min_id=min_id,
            min_cov=min_cov,
            min_depth=min_depth,
            min_join_overlap=min_join_overlap,
            minscore=minscore,
            fmt=fmt,
            output=output,
            cache_dir=cache_dir,
            force_reindex=force_reindex,
            no_header=no_header,
            threads=threads,
            max_workers=max_workers,
            count_same_copy=count_same_copy,
            provider=None,
            prefilter_enabled=not no_prefilter,
            prefilter_k=prefilter_k,
            prefilter_top_n=prefilter_top_n,
            prefilter_min_loci_fraction=prefilter_min_loci_fraction,
            novel_allele=novel_allele,
            novel_profile=novel_profile,
            output_dir=output_dir,
            cds_coordinates_out=cds_coordinates_out,
            call_policy=call_policy,
            chew_cds_gate=chew_cds_gate,
        )


def _resolve_scheme_with_fallback(
    cache: DatabaseCache,
    scheme: str,
    provider: str | None,
    provider_specified: bool,
    mode: str,
    ensure_scheme_type: str,
) -> tuple[Scheme, str, str]:
    if provider is None:
        provider = "pubmlst"
    try:
        scheme_obj = cache.ensure_scheme(
            scheme, provider=provider, scheme_type=ensure_scheme_type
        )
    except Exception as exc:
        if provider_specified:
            err_console.print(
                f"[red]Error:[/red] Could not load scheme '{scheme}' "
                f"from provider '{provider}': {exc}"
            )
            sys.exit(1)

        detected_provider = cache.detect_provider(
            scheme, prefer_type="cgmlst" if mode == "cgmlst" else "mlst"
        )
        if not detected_provider:
            err_console.print(
                f"[red]Error:[/red] Scheme '[cyan]{scheme}[/cyan]' not found."
            )
            err_console.print(
                "\nRun [bold]gmlst scheme list[/bold] to see available schemes."
            )
            sys.exit(1)

        if detected_provider != provider:
            logger.info("Provider fallback: %s -> %s", provider, detected_provider)
        provider = detected_provider

        scheme_type = resolve_scheme_type(cache, scheme, provider)
        validate_scheme_mode(
            scheme=scheme, scheme_type=scheme_type, mode=mode, err_console=err_console
        )
        ensure_scheme_type = effective_scheme_type(mode=mode, resolved_type=scheme_type)

        try:
            scheme_obj = cache.ensure_scheme(
                scheme, provider=provider, scheme_type=ensure_scheme_type
            )
        except Exception as fallback_exc:
            err_console.print(
                f"[red]Error:[/red] Could not load scheme '{scheme}' "
                f"from provider '{provider}': {fallback_exc}"
            )
            sys.exit(1)

    if scheme_obj is None:
        err_console.print(
            f"[red]Error:[/red] Could not load scheme object for '{scheme}'."
        )
        sys.exit(1)

    return scheme_obj, provider, ensure_scheme_type


def _normalize_call_policy(call_policy: str, mode: str) -> tuple[str, str]:
    """Validate --call-policy; return (normalized policy, output policy).

    ``chew-exact`` runs exact-only calling but formats output as chewBBACA.
    Exits with status 1 on unknown policies or non-default policies
    outside cgMLST.
    """
    normalized = call_policy.strip().lower()
    if normalized not in {"default", "chewbbaca", "chew-exact"}:
        err_console.print(
            f"[red]Error:[/red] Unsupported --call-policy '{call_policy}'."
        )
        sys.exit(1)
    if mode != "cgmlst" and normalized != "default":
        err_console.print("[red]Error:[/red] call-policy is only for cgMLST.")
        sys.exit(1)
    return normalized, "chewbbaca" if normalized == "chew-exact" else normalized


def _warn_thread_settings(*, mode: str, backend: str, threads: int) -> None:
    """Warn about backend/thread combinations with poor performance."""
    if backend.lower() == "nucmer" and threads > 1:
        status_console.print(
            "[yellow]Warning:[/yellow] nucmer backend may ignore thread settings; "
            "multi-thread speedups are limited."
        )
    if mode == "cgmlst" and backend.lower() == "kma" and threads == 1:
        status_console.print(
            "[yellow]Warning:[/yellow] cgMLST with kma is very slow on one thread. "
            "Use [cyan]-t[/cyan] (e.g. 8-16) for large schemes."
        )


def _run_mlst_like_typing(
    *,
    mode: str,
    cgmlst_mode: str = "fast",
    samples: tuple[Path, ...],
    scheme: str,
    backend: str,
    min_id: float,
    min_cov: float,
    min_depth: float,
    min_join_overlap: int = 10,
    minscore: float = 0.0,
    fmt: str,
    output: Path | None,
    cache_dir: Path | None,
    force_reindex: bool,
    no_header: bool,
    threads: int,
    count_same_copy: bool,
    provider: str | None,
    max_workers: int = 1,
    prefilter_enabled: bool = True,
    prefilter_k: int = 31,
    prefilter_top_n: int = 20,
    prefilter_min_loci_fraction: float = 0.3,
    novel_allele: bool = False,
    novel_profile: bool = False,
    output_dir: Path | None = None,
    cds_coordinates_out: Path | None = None,
    call_policy: str = "default",
    chew_cds_gate: bool = True,
    max_fastq_depth: float = 100,
    quiet: bool = False,
    detail: bool = False,
    suppress_output: bool = False,
    result_sink: list | None = None,
) -> None:
    cache = DatabaseCache(cache_dir)

    provider_specified = provider is not None
    if provider is None:
        provider = (
            cache.detect_provider(
                scheme, prefer_type="cgmlst" if mode == "cgmlst" else "mlst"
            )
            or "pubmlst"
        )

    scheme_type = resolve_scheme_type(cache, scheme, provider)
    validate_scheme_mode(
        scheme=scheme,
        scheme_type=scheme_type,
        mode=mode,
        err_console=err_console,
    )
    ensure_scheme_type = effective_scheme_type(mode=mode, resolved_type=scheme_type)
    normalized_policy, output_policy = _normalize_call_policy(call_policy, mode)

    prepared_samples = prepare_sample_paths_for_pairing(samples)
    if max_fastq_depth > 0:
        prepared_samples = maybe_subsample_fastq(prepared_samples, max_fastq_depth)
    backend, cgmlst_mode, threads = normalize_cgmlst_fastq_runtime(
        mode=mode,
        prepared_samples=prepared_samples,
        normalized_policy=normalized_policy,
        backend=backend,
        cgmlst_mode=cgmlst_mode,
        max_workers=max_workers,
        threads=threads,
        contains_fastq_samples_fn=contains_fastq_samples,
        fastq_kma_auto_threads_fn=fastq_kma_auto_threads,
        err_console=err_console,
    )

    scheme_obj, provider, ensure_scheme_type = _resolve_scheme_with_fallback(
        cache=cache,
        scheme=scheme,
        provider=provider,
        provider_specified=provider_specified,
        mode=mode,
        ensure_scheme_type=ensure_scheme_type,
    )

    _warn_thread_settings(mode=mode, backend=backend, threads=threads)
    if novel_profile and not novel_allele:
        err_console.print(
            "[red]Error:[/red] --novel-profile requires --novel-allele to be set."
        )
        sys.exit(1)

    # setup writers for novel data
    allele_writer, profile_writer = create_novel_writers(
        novel_allele=novel_allele,
        novel_profile=novel_profile,
        output_dir=output_dir,
        loci=scheme_obj.loci,
        allele_writer_cls=NovelAlleleWriter,
        profile_writer_cls=NovelProfileWriter,
    )

    streamed_output = fmt in {"tsv", "pretty"} and not suppress_output
    stream_file = open_stream_output(fmt=fmt, output=output)
    if streamed_output:
        stream_header_if_needed(
            fmt=fmt,
            no_header=no_header,
            loci=scheme_obj.loci,
            stream_file=stream_file,
        )

    def _on_result(result: STResult) -> None:
        if not streamed_output:
            return
        if minscore > 0 and not passes_minscore(result, minscore):
            return
        emit_streamed_result(
            result=result,
            fmt=fmt,
            loci=scheme_obj.loci,
            count_same_copy=count_same_copy,
            call_policy=output_policy,
            format_st_for_tsv_fn=_format_st_for_tsv,
            format_tsv_row_fn=_format_tsv_row,
            stream_file=stream_file,
            detail=detail,
        )

    if cds_coordinates_out is not None and max_workers > 1:
        err_console.print(
            "[red]Error:[/red] --cds-coordinates-out does not support "
            "--max-workers > 1."
        )
        sys.exit(1)

    try:
        # run typing
        try:
            with temp_root_from_output(output):
                results = execute_typing_run(
                    run_typing_fn=run_typing,
                    prepared_samples=prepared_samples,
                    scheme_name=scheme,
                    backend=backend,
                    provider=provider,
                    scheme_type=ensure_scheme_type,
                    cgmlst_mode=cgmlst_mode,
                    cache_root=cache_dir,
                    min_identity=min_id,
                    min_coverage=min_cov,
                    min_depth=min_depth,
                    min_join_overlap=min_join_overlap,
                    force_reindex=force_reindex,
                    threads=threads,
                    count_same_copy=count_same_copy,
                    prefilter_enabled=prefilter_enabled,
                    prefilter_k=prefilter_k,
                    prefilter_top_n=prefilter_top_n,
                    prefilter_min_loci_fraction=prefilter_min_loci_fraction,
                    cds_coordinates_out=cds_coordinates_out,
                    call_policy=output_policy,
                    chew_cds_gate=chew_cds_gate,
                    max_workers=max_workers,
                    on_result=_on_result,
                    quiet=quiet,
                )
        except Exception as exc:
            err_console.print(f"[red]Error during typing:[/red] {exc}")
            sys.exit(1)

        if minscore > 0:
            results = [r for r in results if passes_minscore(r, minscore)]

        if suppress_output:
            if result_sink is not None:
                result_sink.extend(results)
            return

        finalize_novel_typing_outputs(
            results=results,
            allele_writer=allele_writer,
            profile_writer=profile_writer,
            logger=logger,
        )

        # output results
        if emit_final_typing_output(
            results=results,
            fmt=fmt,
            output=output,
            emit_output_json_fn=_emit_typing_results_json,
        ):
            return

        if streamed_output:
            announce_stream_output_written(output=output)
            return

    finally:
        close_stream_output(stream_file)


def _format_st_for_tsv(result: STResult) -> str:
    if result.has_conflicting_multicopy or result.is_novel or result.st is None:
        return "-"
    return str(result.st)


def _format_tsv_row(
    result: STResult,
    loci: list[str],
    count_same_copy: bool,
    *,
    call_policy: str,
    detail: bool = False,
) -> str:
    return result.format_tsv_row(
        loci,
        include_scheme=True,
        count_same_copy=count_same_copy,
        call_policy=call_policy,
        detail=detail,
    )
