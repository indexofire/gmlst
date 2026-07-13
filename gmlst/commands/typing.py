"""Typing command for gmlst."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import click

from gmlst.aligners import AVAILABLE_BACKENDS
from gmlst.commands.common import (
    console,
    emit_output_json,
    emit_output_text,
    err_console,
)
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
    detect_provider,
    effective_scheme_type,
    resolve_scheme_type,
    validate_scheme_mode,
)
from gmlst.core import run_typing
from gmlst.database.cache import DatabaseCache
from gmlst.novel import NovelAlleleWriter, NovelProfileWriter
from gmlst.novel.service import create_novel_writers, finalize_novel_typing_outputs
from gmlst.readers.sample import (
    SampleInput,
    prepare_sample_inputs,
)
from gmlst.readers.sample import (
    _extract_fastq_pair_info as _sample_extract_fastq_pair_info,
)
from gmlst.schemefree import (
    SchemaFreeConfig,
    SchemeFreeTyper,
    profiles_to_json,
    profiles_to_tsv,
    write_error_report_json,
    write_summary_report_json,
)
from gmlst.utils import setup_logging

logger = logging.getLogger("gmlst")

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

if TYPE_CHECKING:
    from gmlst.calling.st_lookup import STResult


class TypingGroup(click.Group):
    def list_commands(self, ctx: click.Context) -> list[str]:
        preferred = ["mlst", "cgmlst", "tgmlst"]
        existing = [name for name in preferred if name in self.commands]
        remaining = sorted(
            name
            for name in self.commands
            if name not in preferred and not name.startswith("_")
        )
        return existing + remaining

    def resolve_command(
        self,
        ctx: click.Context,
        args: list[str],
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0] not in self.commands:
            legacy_cmd = self.commands.get("_legacy")
            if legacy_cmd is not None:
                return ("_legacy", legacy_cmd, args)
        return super().resolve_command(ctx, args)


@click.group(
    "typing",
    cls=TypingGroup,
    context_settings={**HELP_SETTINGS, "allow_extra_args": True},
    invoke_without_command=True,
    no_args_is_help=True,
)
@click.option(
    "--scheme",
    "-s",
    required=False,
    hidden=True,
    help="MLST scheme name, e.g. 'saureus_1', 'ecoli_1'.",
)
@click.option(
    "--backend",
    "-b",
    default="blastn",
    show_default=True,
    type=click.Choice(AVAILABLE_BACKENDS, case_sensitive=False),
    hidden=True,
    help="Alignment backend to use.",
)
@click.option(
    "--min-id",
    default=95.0,
    show_default=True,
    hidden=True,
    help="Minimum percent identity.",
)
@click.option(
    "--min-cov",
    default=0.95,
    show_default=True,
    hidden=True,
    help="Minimum allele coverage (0-1).",
)
@click.option(
    "--min-depth",
    default=10.0,
    show_default=True,
    hidden=True,
    help="Min read depth (FASTQ only).",
)
@click.option(
    "--format",
    "fmt",
    default="tsv",
    show_default=True,
    type=click.Choice(["tsv", "json", "pretty"]),
    hidden=True,
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    hidden=True,
    help="Write output to file.",
)
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    hidden=True,
    help="Override cache directory.",
)
@click.option(
    "--force-reindex", is_flag=True, hidden=True, help="Rebuild aligner index."
)
@click.option("--no-header", is_flag=True, hidden=True, help="Suppress TSV header line")
@click.option(
    "--threads",
    "-t",
    default=1,
    show_default=True,
    hidden=True,
    help="Number of alignment threads (backend-dependent).",
)
@click.option(
    "--count-same-copy",
    is_flag=True,
    hidden=True,
    help=(
        "Count same-allele multicopy hits (currently blastn) "
        "and show notation like 1,1."
    ),
)
@click.option(
    "--quiet", "-q", is_flag=True, hidden=True, help="Suppress non-error logging."
)
@click.option(
    "--novel-allele",
    is_flag=True,
    hidden=True,
    help="Save novel allele sequences to {locus}_novel.fasta files.",
)
@click.option(
    "--novel-profile",
    is_flag=True,
    hidden=True,
    help="Save novel ST profiles to profiles_novel.txt (requires --novel-allele).",
)
@click.option(
    "--data-dir",
    "--output-dir",
    "output_dir",
    type=click.Path(path_type=Path),
    hidden=True,
    help="Directory for novel allele/profile output files (default: cwd).",
)
@click.option(
    "--hash-strategy",
    default="safe",
    show_default=True,
    hidden=True,
    type=click.Choice(
        ["safe", "fast", "ultra", "strict", "blast"], case_sensitive=False
    ),
    help="Hash strategy for allele identification (schemefree mode).",
)
@click.option(
    "--schemefree-save-scheme",
    type=click.Path(path_type=Path),
    hidden=True,
    help="Write discovered schemefree scheme JSON.",
)
@click.option(
    "--schemefree-load-scheme",
    type=click.Path(exists=True, path_type=Path),
    hidden=True,
    help="Load an existing schemefree scheme JSON before typing.",
)
@click.option(
    "--schemefree-stats",
    is_flag=True,
    hidden=True,
    help="Print schemefree pipeline timing and count stats.",
)
@click.option(
    "--schemefree-max-workers",
    type=int,
    hidden=True,
    help="Override schemefree max parallel samples.",
)
@click.option(
    "--schemefree-assemble-timeout",
    type=float,
    hidden=True,
    help="Override schemefree assembly timeout seconds.",
)
@click.option(
    "--schemefree-error-report",
    type=click.Path(path_type=Path),
    hidden=True,
    help="Write per-sample schemefree errors to JSON.",
)
@click.option(
    "--schemefree-fail-on-error",
    is_flag=True,
    hidden=True,
    help="Return non-zero if any schemefree sample fails.",
)
@click.option(
    "--schemefree-summary-report",
    type=click.Path(path_type=Path),
    hidden=True,
    help="Write machine-readable schemefree run summary JSON.",
)
@click.pass_context
def cmd_typing(
    ctx: click.Context,
    scheme: str | None,
    backend: str,
    min_id: float,
    min_cov: float,
    min_depth: float,
    fmt: str,
    output: Path | None,
    cache_dir: Path | None,
    force_reindex: bool,
    no_header: bool,
    threads: int,
    count_same_copy: bool,
    quiet: bool,
    novel_allele: bool,
    novel_profile: bool,
    output_dir: Path | None,
    hash_strategy: str,
    schemefree_save_scheme: Path | None,
    schemefree_load_scheme: Path | None,
    schemefree_stats: bool,
    schemefree_max_workers: int | None,
    schemefree_assemble_timeout: float | None,
    schemefree_error_report: Path | None,
    schemefree_fail_on_error: bool,
    schemefree_summary_report: Path | None,
) -> None:
    """Typing command group: mlst, cgmlst, and tgmlst modes."""
    if ctx.invoked_subcommand is not None:
        return

    click.echo(ctx.get_help())


@cmd_typing.command("_legacy", hidden=True)
@click.argument(
    "samples",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.pass_context
def cmd_typing_legacy(ctx: click.Context, samples: tuple[Path, ...]) -> None:
    parent = ctx.parent
    if parent is None:
        raise click.UsageError("Legacy typing context missing")

    params = parent.params
    scheme = params.get("scheme")
    if not isinstance(scheme, str) or not scheme:
        raise click.UsageError("Legacy typing requires -s/--scheme")

    quiet = bool(params.get("quiet", False))
    if quiet:
        setup_logging(verbose=False, quiet=True)

    if scheme.lower() == "schemefree":
        exit_code = _run_schemefree_typing(
            samples=list(samples),
            hash_strategy=str(params.get("hash_strategy", "safe")),
            fmt=str(params.get("fmt", "tsv")),
            output=params.get("output"),
            no_header=bool(params.get("no_header", False)),
            save_scheme_path=params.get("schemefree_save_scheme"),
            load_scheme_path=params.get("schemefree_load_scheme"),
            show_stats=bool(params.get("schemefree_stats", False)),
            max_workers=params.get("schemefree_max_workers"),
            threads=int(params.get("threads", 1)),
            assemble_timeout=params.get("schemefree_assemble_timeout"),
            error_report_path=params.get("schemefree_error_report"),
            fail_on_error=bool(params.get("schemefree_fail_on_error", False)),
            summary_report_path=params.get("schemefree_summary_report"),
        )
        if exit_code != 0:
            sys.exit(exit_code)
        return

    legacy_mode = _infer_typing_mode(
        scheme=scheme,
        provider=params.get("provider"),
        cache_dir=params.get("cache_dir"),
    )
    _run_mlst_like_typing(
        mode=legacy_mode,
        samples=samples,
        scheme=scheme,
        backend=str(params.get("backend", "blastn")),
        min_id=float(params.get("min_id", 95.0)),
        min_cov=float(params.get("min_cov", 0.95)),
        min_depth=float(params.get("min_depth", 10.0)),
        fmt=str(params.get("fmt", "tsv")),
        output=params.get("output"),
        cache_dir=params.get("cache_dir"),
        force_reindex=bool(params.get("force_reindex", False)),
        no_header=bool(params.get("no_header", False)),
        threads=int(params.get("threads", 1)),
        max_workers=int(params.get("max_workers", 1)),
        count_same_copy=bool(params.get("count_same_copy", False)),
        provider=params.get("provider"),
        novel_allele=bool(params.get("novel_allele", False)),
        novel_profile=bool(params.get("novel_profile", False)),
        output_dir=params.get("output_dir"),
    )


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
    required=True,
    help="MLST scheme name, e.g. 'saureus_1', 'ecoli_1'.",
)
@click.option(
    "--backend",
    "-b",
    default="blastn",
    show_default=True,
    type=click.Choice(AVAILABLE_BACKENDS, case_sensitive=False),
    help="Alignment backend to use.",
)
@click.option(
    "--min-id", default=95.0, show_default=True, help="Minimum percent identity."
)
@click.option(
    "--min-cov", default=0.95, show_default=True, help="Minimum allele coverage (0-1)."
)
@click.option(
    "--min-depth", default=10.0, show_default=True, help="Min read depth (FASTQ only)."
)
@click.option(
    "--format",
    "fmt",
    default="tsv",
    show_default=True,
    type=click.Choice(["tsv", "json", "pretty"]),
    help="Output format.",
)
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Write output to file."
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
@click.option("--force-reindex", is_flag=True, help="Rebuild aligner index.")
@click.option("--no-header", is_flag=True, help="Suppress TSV header line")
@click.option(
    "--threads",
    "-t",
    default=1,
    show_default=True,
    help="Number of alignment threads (backend-dependent).",
)
@click.option(
    "--max-workers",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Number of samples to type in parallel (mlst/cgmlst).",
)
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
    "--novel-allele",
    is_flag=True,
    help="Save novel allele sequences to {locus}_novel.fasta files.",
)
@click.option(
    "--novel-profile",
    is_flag=True,
    help="Save novel ST profiles to profiles_novel.txt (requires --novel-allele).",
)
@click.option(
    "--data-dir",
    "--output-dir",
    "output_dir",
    type=click.Path(path_type=Path),
    help="Directory for novel allele/profile output files (default: cwd).",
)
def cmd_typing_mlst(
    samples: tuple[Path, ...],
    scheme: str,
    backend: str,
    min_id: float,
    min_cov: float,
    min_depth: float,
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
    novel_allele: bool,
    novel_profile: bool,
    output_dir: Path | None,
) -> None:
    """Type samples against MLST schemes only."""
    if quiet:
        setup_logging(verbose=False, quiet=True)
    _run_mlst_like_typing(
        mode="mlst",
        samples=samples,
        scheme=scheme,
        backend=backend,
        min_id=min_id,
        min_cov=min_cov,
        min_depth=min_depth,
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
    required=True,
    help="cgMLST/wgMLST scheme name, e.g. 'vparahaemolyticus_3'.",
)
@click.option(
    "--backend",
    "-b",
    default="minimap2",
    show_default=True,
    type=click.Choice(AVAILABLE_BACKENDS, case_sensitive=False),
    help="Alignment backend to use.",
)
@click.option(
    "--cgmlst-mode",
    type=click.Choice(
        [
            "standard",
            "chew-fast",
            "chew-ultrafast",
            "chew-bsr",
            "chew-balanced",
        ],
        case_sensitive=False,
    ),
    default="standard",
    show_default=True,
    help="cgMLST workflow mode.",
)
@click.option(
    "--min-id", default=95.0, show_default=True, help="Minimum percent identity."
)
@click.option(
    "--min-cov", default=0.95, show_default=True, help="Minimum allele coverage (0-1)."
)
@click.option(
    "--min-depth", default=10.0, show_default=True, help="Min read depth (FASTQ only)."
)
@click.option(
    "--format",
    "fmt",
    default="tsv",
    show_default=True,
    type=click.Choice(["tsv", "json", "pretty"]),
    help="Output format.",
)
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Write output to file."
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
@click.option("--force-reindex", is_flag=True, help="Rebuild aligner index.")
@click.option("--no-header", is_flag=True, help="Suppress TSV header line")
@click.option(
    "--threads",
    "-t",
    default=1,
    show_default=True,
    help="Number of alignment threads (backend-dependent).",
)
@click.option(
    "--max-workers",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Number of samples to type in parallel (mlst/cgmlst).",
)
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
@click.option(
    "--novel-allele",
    is_flag=True,
    help="Save novel allele sequences to {locus}_novel.fasta files.",
)
@click.option(
    "--novel-profile",
    is_flag=True,
    help="Save novel ST profiles to profiles_novel.txt (requires --novel-allele).",
)
@click.option(
    "--data-dir",
    "--output-dir",
    "output_dir",
    type=click.Path(path_type=Path),
    help="Directory for novel allele/profile output files (default: cwd).",
)
@click.option(
    "--cds-coordinates-out",
    type=click.Path(path_type=Path),
    help="Write predicted CDS coordinates TSV for alignment with chewBBACA outputs.",
)
@click.option(
    "--call-policy",
    type=click.Choice(["default", "chewbbaca"], case_sensitive=False),
    default="default",
    show_default=True,
    help="Allele decision policy for output classification.",
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
    scheme: str,
    backend: str,
    cgmlst_mode: str,
    min_id: float,
    min_cov: float,
    min_depth: float,
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
    _run_mlst_like_typing(
        mode="cgmlst",
        samples=samples,
        scheme=scheme,
        backend=backend,
        cgmlst_mode=cgmlst_mode,
        min_id=min_id,
        min_cov=min_cov,
        min_depth=min_depth,
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


@cmd_typing.command("tgmlst", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.argument(
    "samples",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option(
    "--format",
    "fmt",
    default="tsv",
    show_default=True,
    type=click.Choice(["tsv", "json", "pretty"]),
    help="Output format.",
)
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Write output to file."
)
@click.option("--no-header", is_flag=True, help="Suppress TSV header line")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error logging.")
@click.option(
    "--hash-strategy",
    default="safe",
    show_default=True,
    type=click.Choice(
        ["safe", "fast", "ultra", "strict", "blast"], case_sensitive=False
    ),
    help="Hash strategy for allele identification.",
)
@click.option(
    "--save-scheme",
    "save_scheme",
    type=click.Path(path_type=Path),
    help="Write discovered schemefree scheme JSON.",
)
@click.option(
    "--schemefree-save-scheme",
    "save_scheme",
    type=click.Path(path_type=Path),
    hidden=True,
)
@click.option(
    "--load-scheme",
    "load_scheme",
    type=click.Path(exists=True, path_type=Path),
    help="Load an existing schemefree scheme JSON before typing.",
)
@click.option(
    "--schemefree-load-scheme",
    "load_scheme",
    type=click.Path(exists=True, path_type=Path),
    hidden=True,
)
@click.option(
    "--stats",
    "show_stats",
    is_flag=True,
    help="Print schemefree pipeline timing and count stats.",
)
@click.option("--schemefree-stats", "show_stats", is_flag=True, hidden=True)
@click.option(
    "--max-workers",
    "max_workers",
    type=int,
    help="Override schemefree max parallel samples.",
)
@click.option("--schemefree-max-workers", "max_workers", type=int, hidden=True)
@click.option(
    "--threads",
    "threads",
    "-t",
    type=click.IntRange(min=1),
    help="MMseqs clustering threads for tgMLST.",
)
@click.option(
    "--assemble-timeout",
    "assemble_timeout",
    type=float,
    help="Override schemefree assembly timeout seconds.",
)
@click.option(
    "--schemefree-assemble-timeout",
    "assemble_timeout",
    type=float,
    hidden=True,
)
@click.option(
    "--error-report",
    "error_report",
    type=click.Path(path_type=Path),
    help="Write per-sample schemefree errors to JSON.",
)
@click.option(
    "--schemefree-error-report",
    "error_report",
    type=click.Path(path_type=Path),
    hidden=True,
)
@click.option(
    "--fail-on-error",
    "fail_on_error",
    is_flag=True,
    help="Return non-zero if any schemefree sample fails.",
)
@click.option("--schemefree-fail-on-error", "fail_on_error", is_flag=True, hidden=True)
@click.option(
    "--summary-report",
    "summary_report",
    type=click.Path(path_type=Path),
    help="Write machine-readable schemefree run summary JSON.",
)
@click.option(
    "--schemefree-summary-report",
    "summary_report",
    type=click.Path(path_type=Path),
    hidden=True,
)
def cmd_typing_tgmlst(
    samples: tuple[Path, ...],
    fmt: str,
    output: Path | None,
    no_header: bool,
    quiet: bool,
    hash_strategy: str,
    save_scheme: Path | None,
    load_scheme: Path | None,
    show_stats: bool,
    max_workers: int | None,
    threads: int | None,
    assemble_timeout: float | None,
    error_report: Path | None,
    fail_on_error: bool,
    summary_report: Path | None,
) -> None:
    """Run scheme-free typing pipeline (tgMLST)."""
    if quiet:
        setup_logging(verbose=False, quiet=True)

    exit_code = _run_schemefree_typing(
        samples=list(samples),
        hash_strategy=hash_strategy,
        fmt=fmt,
        output=output,
        no_header=no_header,
        save_scheme_path=save_scheme,
        load_scheme_path=load_scheme,
        show_stats=show_stats,
        max_workers=max_workers,
        threads=threads,
        assemble_timeout=assemble_timeout,
        error_report_path=error_report,
        fail_on_error=fail_on_error,
        summary_report_path=summary_report,
    )
    if exit_code != 0:
        sys.exit(exit_code)


def _run_mlst_like_typing(
    *,
    mode: str,
    cgmlst_mode: str = "standard",
    samples: tuple[Path, ...],
    scheme: str,
    backend: str,
    min_id: float,
    min_cov: float,
    min_depth: float,
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
) -> None:
    cache = DatabaseCache(cache_dir)

    provider_specified = provider is not None
    if provider is None:
        provider = detect_provider(cache=cache, scheme=scheme) or "pubmlst"

    scheme_type = resolve_scheme_type(cache, scheme, provider)
    validate_scheme_mode(
        scheme=scheme,
        scheme_type=scheme_type,
        mode=mode,
        err_console=err_console,
    )
    ensure_scheme_type = effective_scheme_type(mode=mode, resolved_type=scheme_type)
    normalized_policy = call_policy.strip().lower()
    if normalized_policy not in {"default", "chewbbaca"}:
        err_console.print(
            f"[red]Error:[/red] Unsupported --call-policy '{call_policy}'."
        )
        sys.exit(1)
    if mode != "cgmlst" and normalized_policy != "default":
        err_console.print(
            "[red]Error:[/red] --call-policy chewbbaca is only supported for cgMLST."
        )
        sys.exit(1)

    prepared_samples = _prepare_sample_paths_for_pairing(samples)
    if max_fastq_depth > 0:
        prepared_samples = _maybe_subsample_fastq(
            prepared_samples, max_fastq_depth, console
        )
    backend, cgmlst_mode, threads = normalize_cgmlst_fastq_runtime(
        mode=mode,
        prepared_samples=prepared_samples,
        normalized_policy=normalized_policy,
        backend=backend,
        cgmlst_mode=cgmlst_mode,
        max_workers=max_workers,
        threads=threads,
        contains_fastq_samples_fn=_contains_fastq_samples,
        fastq_kma_auto_threads_fn=_fastq_kma_auto_threads,
        console=console,
        err_console=err_console,
    )

    try:
        scheme_obj = cache.ensure_scheme(
            scheme,
            provider=provider,
            scheme_type=ensure_scheme_type,
        )
    except Exception as exc:
        if provider_specified:
            err_console.print(
                f"[red]Error:[/red] Could not load scheme '{scheme}' "
                f"from provider '{provider}': {exc}"
            )
            sys.exit(1)

        detected_provider = detect_provider(cache, scheme)
        if not detected_provider:
            err_console.print(
                f"[red]Error:[/red] Scheme '[cyan]{scheme}[/cyan]' not found."
            )
            err_console.print(
                "\nRun [bold]gmlst scheme list[/bold] to see available schemes."
            )
            sys.exit(1)

        if detected_provider != provider:
            logger.info(
                "Provider fallback: %s -> %s",
                provider,
                detected_provider,
            )
        provider = detected_provider

        scheme_type = resolve_scheme_type(cache, scheme, provider)
        validate_scheme_mode(
            scheme=scheme,
            scheme_type=scheme_type,
            mode=mode,
            err_console=err_console,
        )
        ensure_scheme_type = effective_scheme_type(mode=mode, resolved_type=scheme_type)

        try:
            scheme_obj = cache.ensure_scheme(
                scheme,
                provider=provider,
                scheme_type=ensure_scheme_type,
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

    if backend.lower() == "nucmer" and threads > 1:
        console.print(
            "[yellow]Warning:[/yellow] nucmer backend may ignore thread settings; "
            "multi-thread speedups are limited."
        )
    # validate novel flags
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

    streamed_output = fmt in {"tsv", "pretty"}
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
        emit_streamed_result(
            result=result,
            fmt=fmt,
            loci=scheme_obj.loci,
            count_same_copy=count_same_copy,
            call_policy=normalized_policy,
            format_st_for_tsv_fn=_format_st_for_tsv,
            format_tsv_row_fn=_format_tsv_row,
            stream_file=stream_file,
        )

    if mode == "cgmlst" and backend.lower() == "kma" and threads == 1:
        console.print(
            "[yellow]Warning:[/yellow] cgMLST with kma is very slow on one thread. "
            "Use [cyan]-t[/cyan] (e.g. 8-16) for large schemes."
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
            with _temp_root_from_output(output):
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
                    force_reindex=force_reindex,
                    threads=threads,
                    count_same_copy=count_same_copy,
                    prefilter_enabled=prefilter_enabled,
                    prefilter_k=prefilter_k,
                    prefilter_top_n=prefilter_top_n,
                    prefilter_min_loci_fraction=prefilter_min_loci_fraction,
                    cds_coordinates_out=cds_coordinates_out,
                    call_policy=normalized_policy,
                    chew_cds_gate=chew_cds_gate,
                    max_workers=max_workers,
                    on_result=_on_result,
                    console=console,
                )
        except Exception as exc:
            err_console.print(f"[red]Error during typing:[/red] {exc}")
            sys.exit(1)

        finalize_novel_typing_outputs(
            results=results,
            allele_writer=allele_writer,
            profile_writer=profile_writer,
            logger=logger,
            console=console,
        )

        # output results
        if emit_final_typing_output(
            results=results,
            fmt=fmt,
            output=output,
            emit_output_json_fn=emit_output_json,
            console=console,
        ):
            return

        if streamed_output:
            announce_stream_output_written(output=output, console=console)
            return

    finally:
        close_stream_output(stream_file)


def _prepare_sample_paths_for_pairing(
    samples: tuple[Path, ...],
) -> list[Path | SampleInput]:
    return prepare_sample_inputs(list(samples))


def _extract_fastq_pair_info(sample_path: Path) -> tuple[str, str] | None:
    return _sample_extract_fastq_pair_info(sample_path)


def _contains_fastq_samples(samples: list[Path | SampleInput]) -> bool:
    for sample in samples:
        if isinstance(sample, SampleInput):
            if sample.input_type == "fastq":
                return True
            continue

        name = sample.name.lower()
        if name.endswith(".fastq") or name.endswith(".fq"):
            return True
        if name.endswith(".fastq.gz") or name.endswith(".fq.gz"):
            return True
    return False


def _fastq_kma_auto_threads() -> int:
    raw = os.getenv("GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS", "8").strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = 8
    if configured <= 1:
        return 1
    cpu_total = os.cpu_count() or configured
    return max(2, min(configured, cpu_total))


@contextmanager
def _temp_root_from_output(output: Path | None) -> Generator[None, None, None]:
    if output is None:
        yield
        return

    output_parent = output.resolve().parent
    previous = os.environ.get("GMLST_TMPDIR")
    os.environ["GMLST_TMPDIR"] = str(output_parent)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("GMLST_TMPDIR", None)
        else:
            os.environ["GMLST_TMPDIR"] = previous


def _infer_typing_mode(
    scheme: str, provider: str | None, cache_dir: Path | None
) -> str:
    cache = DatabaseCache(cache_dir)
    scheme_type = resolve_scheme_type(cache, scheme, provider)
    if scheme_type in {"cgmlst", "wgmlst"}:
        return "cgmlst"
    return "mlst"


def _run_schemefree_typing(
    samples: list[Path],
    hash_strategy: str,
    fmt: str,
    output: Path | None,
    no_header: bool,
    save_scheme_path: Path | None,
    load_scheme_path: Path | None,
    show_stats: bool,
    max_workers: int | None,
    threads: int | None,
    assemble_timeout: float | None,
    error_report_path: Path | None,
    fail_on_error: bool,
    summary_report_path: Path | None,
) -> int:
    config = SchemaFreeConfig()
    config.hash.strategy = hash_strategy
    if max_workers is None and threads is not None:
        max_workers = threads
    if max_workers is not None:
        config.assembly.max_parallel_samples = max_workers
    if threads is not None:
        config.clustering.threads = str(threads)
    if assemble_timeout is not None:
        config.assembly.assemble_timeout_sec = assemble_timeout
    typer = SchemeFreeTyper(config)

    if load_scheme_path:
        typer.load_scheme(load_scheme_path)

    profiles = typer.type_sample_files(samples)
    profile_dicts = [p.to_dict() for p in profiles]

    if save_scheme_path:
        typer.export_scheme(save_scheme_path)

    if fmt == "json":
        output_text = profiles_to_json(profile_dicts)
    elif fmt == "pretty":
        output_text = "\n".join(f"{p.sample_id}: {p.loci_count} loci" for p in profiles)
    else:
        output_text = profiles_to_tsv(profile_dicts, include_header=not no_header)

    wrote_file = emit_output_text(output_text, output)
    if wrote_file and output is not None:
        console.print(f"Results written to [cyan]{output}[/cyan]")

    if error_report_path:
        write_error_report_json(error_report_path, typer.last_run_errors)
        console.print(f"Schemefree errors written to [cyan]{error_report_path}[/cyan]")

    if typer.last_run_errors:
        failed_count = len(typer.last_run_errors)
        console.print(
            f"[yellow]Schemefree warning:[/yellow] {failed_count} sample(s) failed."
        )

    if show_stats:
        emit_output_json(typer.last_run_stats, None)

    exit_code, exit_reason, primary_failed_stage = _schemefree_exit_decision(
        success_count=len(profiles),
        failed_count=len(typer.last_run_errors),
        errors=typer.last_run_errors,
        fail_on_error=fail_on_error,
    )

    if summary_report_path:
        summary_payload = {
            **typer.last_run_stats,
            "exit_code": exit_code,
            "exit_reason": exit_reason,
            "primary_failed_stage": primary_failed_stage,
            "failed_by_stage": _count_errors_by_stage(typer.last_run_errors),
        }
        write_summary_report_json(summary_report_path, summary_payload)
        console.print(
            f"Schemefree summary written to [cyan]{summary_report_path}[/cyan]"
        )

    return exit_code


def _schemefree_exit_decision(
    success_count: int,
    failed_count: int,
    errors: list[dict[str, str]],
    fail_on_error: bool,
) -> tuple[int, str, str | None]:
    if failed_count == 0:
        return 0, "all_succeeded", None

    primary_stage = _primary_failed_stage(errors)
    stage_exit = _stage_exit_code(primary_stage)

    if success_count == 0:
        return stage_exit, f"all_failed_{primary_stage}", primary_stage
    if fail_on_error:
        return (
            stage_exit,
            f"partial_failed_strict_{primary_stage}",
            primary_stage,
        )
    return 0, "partial_failed_allowed", primary_stage


def _count_errors_by_stage(errors: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for error in errors:
        stage = error.get("stage", "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    return counts


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
) -> str:
    return result.format_tsv_row(
        loci,
        include_scheme=True,
        count_same_copy=count_same_copy,
        call_policy=call_policy,
    )


def _primary_failed_stage(errors: list[dict[str, str]]) -> str:
    counts = _count_errors_by_stage(errors)
    if not counts:
        return "unknown"

    priority = {"input": 0, "assembly": 1, "prediction": 2, "unknown": 3}
    return sorted(
        counts.items(),
        key=lambda kv: (-kv[1], priority.get(kv[0], 99), kv[0]),
    )[0][0]


def _stage_exit_code(stage: str) -> int:
    mapping = {
        "input": 2,
        "assembly": 3,
        "prediction": 4,
        "unknown": 5,
    }
    return mapping.get(stage, 5)


_DEFAULT_GENOME_SIZE = 5_000_000
_FASTQ_BYTES_PER_READ = 250


def _maybe_subsample_fastq(
    samples: list[Path | SampleInput],
    max_depth: float,
    console: object,
) -> list[Path | SampleInput]:
    """Subsample FASTQ files when estimated depth exceeds max_depth."""

    result: list[Path | SampleInput] = []
    for sample in samples:
        is_fastq = False
        paths: list[Path] = []
        if isinstance(sample, SampleInput):
            if sample.input_type == "fastq":
                is_fastq = True
                paths = [sample.path]
                if sample.mate_path:
                    paths.append(sample.mate_path)
        elif Path(str(sample)).suffix in (".fastq", ".fq", ".fastq.gz", ".fq.gz"):
            is_fastq = True
            paths = [Path(str(sample))]

        if not is_fastq:
            result.append(sample)
            continue

        total_reads = sum(
            max(p.stat().st_size // _FASTQ_BYTES_PER_READ, 1) for p in paths
        )
        est_depth = total_reads * 150 / _DEFAULT_GENOME_SIZE
        if est_depth <= max_depth:
            result.append(sample)
            continue

        target_reads = int(max_depth * _DEFAULT_GENOME_SIZE / 150)
        console.print(
            f"[yellow]Subsample:[/yellow] "
            f"{sample if isinstance(sample, Path) else sample.sample_id} "
            f"~{est_depth:.0f}x depth → {max_depth:.0f}x "
            f"(target {target_reads} reads)"
        )

        from gmlst.utils import temp_dir

        with temp_dir("gmlst_sub_") as tmp:
            new_paths: list[Path] = []
            for i, p in enumerate(paths):
                out = tmp / f"sub_{i}.fastq.gz"
                _subsample_fastq_file(p, out, target_reads)
                new_paths.append(out)

            if isinstance(sample, SampleInput):
                result.append(
                    SampleInput(
                        path=new_paths[0],
                        mate_path=new_paths[1] if len(new_paths) > 1 else None,
                        sample_id=sample.sample_id,
                    )
                )
            else:
                result.append(new_paths[0])

    return result


def _subsample_fastq_file(
    input_path: Path, output_path: Path, target_reads: int
) -> None:
    """Subsample FASTQ to first *target_reads* reads."""
    import gzip as _gzip

    opener = _gzip.open if input_path.suffix == ".gz" else open
    lines_needed = target_reads * 4
    with opener(input_path, "rb") as fin, _gzip.open(output_path, "wb") as fout:
        for _ in range(lines_needed):
            line = fin.readline()
            if not line:
                break
            fout.write(line)
