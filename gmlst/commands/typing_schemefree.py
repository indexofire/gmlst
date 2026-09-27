"""tgmlst (scheme-free) typing runner behind ``gmlst typing tgmlst``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from gmlst.commands.common import (
    HELP_SETTINGS,
    emit_output_text,
    err_console,
    status_console,
)
from gmlst.commands.typing_schemefree_exit import (
    count_errors_by_stage,
    schemefree_exit_decision,
)
from gmlst.genbank_io import ensure_fasta_samples
from gmlst.schema_versions import TGMLST_PROFILES_V1, TGMLST_STATS_V1
from gmlst.schemefree import (
    SchemaFreeConfig,
    SchemeFreeTyper,
    profiles_to_tsv,
    write_error_report_json,
    write_summary_report_json,
)
from gmlst.utils import setup_logging


def _normalize_allele_call(locus: str, call: object) -> str:
    """Normalize one allele call to the schemefree JSON string form.

    Mirrors ``gmlst.schemefree.io_handler._normalize_allele_call`` so the
    CLI can build the JSON payload in memory without a dumps/loads
    round-trip through the engine module.
    """
    if call is None:
        return "0"
    if isinstance(call, int):
        return str(call)

    call_str = str(call).strip()
    if call_str in {"", "-"}:
        return "0"
    if call_str.isdigit():
        return call_str

    prefix = f"{locus}_"
    if call_str.startswith(prefix):
        suffix = call_str[len(prefix) :]
        if suffix.isdigit():
            return suffix

    return call_str


def _normalize_profile_dicts(
    profile_dicts: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Apply the schemefree ``profiles_to_json`` normalization in memory.

    Equivalence is locked by ``test_typing_serialization_round_trip``.
    """
    normalized: list[dict[str, object]] = []
    for profile in profile_dicts:
        profile_copy = dict(profile)
        calls_map = profile_copy.get("profile")
        if isinstance(calls_map, dict):
            profile_copy["profile"] = {
                locus: _normalize_allele_call(locus, call)
                for locus, call in calls_map.items()
            }
        normalized.append(profile_copy)
    return normalized


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
        try:
            typer.load_scheme(load_scheme_path)
        except Exception as exc:
            err_console.print(
                f"[red]Error:[/red] Failed to load scheme from "
                f"'{load_scheme_path}': {exc}"
            )
            sys.exit(1)

    profiles = typer.type_sample_files(samples)

    if save_scheme_path:
        typer.export_scheme(save_scheme_path)

    if fmt == "pretty":
        output_text = "\n".join(f"{p.sample_id}: {p.loci_count} loci" for p in profiles)
    else:
        profile_dicts = [p.to_dict() for p in profiles]
        if fmt == "json":
            # Wrap at the CLI boundary: schemefree io_handler stays a pure engine.
            output_text = json.dumps(
                {
                    "schema_version": TGMLST_PROFILES_V1,
                    "data": _normalize_profile_dicts(profile_dicts),
                },
                indent=2,
            )
        else:
            output_text = profiles_to_tsv(profile_dicts, include_header=not no_header)

    wrote_file = emit_output_text(output_text, output)
    if wrote_file and output is not None:
        status_console.print(f"Results written to [cyan]{output}[/cyan]")

    if error_report_path:
        write_error_report_json(error_report_path, typer.last_run_errors)
        status_console.print(
            f"Schemefree errors written to [cyan]{error_report_path}[/cyan]"
        )

    if typer.last_run_errors:
        failed_count = len(typer.last_run_errors)
        status_console.print(
            f"[yellow]Schemefree warning:[/yellow] {failed_count} sample(s) failed."
        )

    if show_stats:
        # Stats go to stderr so stdout carries exactly one parseable document.
        stats_envelope = {
            "schema_version": TGMLST_STATS_V1,
            "data": typer.last_run_stats,
        }
        click.echo(json.dumps(stats_envelope, indent=2), err=True)

    exit_code, exit_reason, primary_failed_stage = schemefree_exit_decision(
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
            "failed_by_stage": count_errors_by_stage(typer.last_run_errors),
        }
        write_summary_report_json(summary_report_path, summary_payload)
        status_console.print(
            f"Schemefree summary written to [cyan]{summary_report_path}[/cyan]"
        )

    return exit_code


@click.command("tgmlst", context_settings=HELP_SETTINGS, no_args_is_help=True)
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
    help="Print pipeline run stats to stderr.",
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

    with ensure_fasta_samples(samples) as samples_fasta:
        exit_code = _run_schemefree_typing(
            samples=list(samples_fasta),
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
