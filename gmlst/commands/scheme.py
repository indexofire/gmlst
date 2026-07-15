"""Scheme management commands for gmlst."""

from __future__ import annotations

import contextlib
import csv
import fcntl
import json
import logging
import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

import click
from rich import box
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from gmlst.commands.common import (
    _DictSchemeInfo,
    _load_blocked_schemes,
    _natural_sort_key,
    console,
    emit_output_csv,
    emit_output_json,
    emit_output_table,
    emit_output_text,
    emit_output_tsv,
    err_console,
)
from gmlst.database.cache import DatabaseCache
from gmlst.database.download import DownloadTool
from gmlst.database.providers import AVAILABLE_PROVIDERS
from gmlst.fasta_io import write_wrapped_sequence
from gmlst.novel.service import (
    build_custom_scheme_metadata,
    merge_custom_scheme_update_metadata,
)
from gmlst.novel.service import (
    last_allele_numbers as _service_last_allele_numbers,
)
from gmlst.utils import setup_logging


@contextlib.contextmanager
def _locked_local_catalog(cache: DatabaseCache) -> Iterator[None]:
    catalog_path = cache._catalog_path("local")
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = catalog_path.with_suffix(".lock")
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

logger = logging.getLogger("gmlst.commands.scheme")
DOWNLOAD_TOOL_CHOICES: tuple[DownloadTool, ...] = (
    "auto",
    "aria2c",
    "curl",
    "wget",
    "httpx",
    "requests",
)


def _download_tool_choice(value: str) -> DownloadTool:
    lowered = value.lower()
    if lowered == "auto":
        return "auto"
    if lowered == "aria2c":
        return "aria2c"
    if lowered == "curl":
        return "curl"
    if lowered == "wget":
        return "wget"
    if lowered == "httpx":
        return "httpx"
    if lowered == "requests":
        return "requests"
    raise ValueError(f"Unsupported download tool: {value}")


def _provider_choices(
    *, include_local: bool = True, include_all: bool = True
) -> list[str]:
    choices = list(AVAILABLE_PROVIDERS)
    if include_local and "local" not in choices:
        choices.append("local")
    if include_all and "all" not in choices:
        choices.append("all")
    return choices


def _catalog_providers(*, include_local: bool = False) -> list[str]:
    providers = list(AVAILABLE_PROVIDERS)
    if include_local:
        providers.append("local")
    return providers


def _find_catalog_scheme_matches(
    cache: DatabaseCache,
    scheme_name: str,
    *,
    include_local: bool = False,
    ignore_catalog_errors: bool = False,
) -> list[tuple[str, _DictSchemeInfo]]:
    matches: list[tuple[str, _DictSchemeInfo]] = []
    for prov in _catalog_providers(include_local=include_local):
        try:
            scheme_dicts = cache.load_catalog(prov)
        except (OSError, json.JSONDecodeError) as exc:
            if ignore_catalog_errors:
                logger.debug("Skipping catalog for provider '%s': %s", prov, exc)
                continue
            raise
        if not scheme_dicts:
            continue
        for item in scheme_dicts:
            if item.get("scheme_name") == scheme_name:
                normalized = dict(item)
                normalized.setdefault("provider", prov)
                matches.append((prov, _DictSchemeInfo(normalized)))
                break
    return matches


def _exit_scheme_not_found(scheme_name: str) -> None:
    err_console.print(f"[red]Error:[/red] Scheme '{scheme_name}' not found in catalog.")
    err_console.print("Run [bold]gmlst scheme list[/bold] to see available schemes.")
    sys.exit(1)


def _exit_no_novel_data(*, show_expected_hint: bool) -> None:
    err_console.print("[red]Error:[/red] No novel data found in directory.")
    if show_expected_hint:
        err_console.print("Expected: *_novel.fasta and/or profiles_novel.txt")
    sys.exit(1)


def _exit_validation_errors(errors: list[str]) -> None:
    if not errors:
        return
    err_console.print("[red]Validation errors:[/red]")
    for error in errors:
        err_console.print(f"  - {error}")
    sys.exit(1)


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _last_allele_numbers(
    novel_alleles: dict[str, list],
) -> dict[str, int]:
    return _service_last_allele_numbers(novel_alleles)


def _write_wrapped_sequence(handle: TextIO, sequence: str, *, width: int = 60) -> None:
    write_wrapped_sequence(handle, sequence, width=width)


@click.group(
    "scheme",
    context_settings=HELP_SETTINGS,
    no_args_is_help=True,
)
def scheme_group() -> None:
    """Manage MLST, cgMLST, and wgMLST schemes and providers."""
    pass


@scheme_group.command("list", context_settings=HELP_SETTINGS, no_args_is_help=False)
@click.option(
    "--provider",
    "-p",
    default="all",
    show_default=True,
    type=click.Choice(_provider_choices(), case_sensitive=False),
    help="Filter by provider (registered provider/local/all).",
)
@click.option(
    "--type",
    "-t",
    "scheme_type",
    default="all",
    show_default=True,
    type=click.Choice(
        ["mlst", "cgmlst", "wgmlst", "rmlst", "other", "all"],
        case_sensitive=False,
    ),
    help="Scheme type filter.",
)
@click.option(
    "--name",
    "-n",
    help="Filter Organism by regex pattern (case-insensitive).",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    default="table",
    show_default=True,
    type=click.Choice(["text", "table", "csv", "tsv", "json"], case_sensitive=False),
    help="Output format.",
)
@click.option(
    "--available",
    "-a",
    is_flag=True,
    help="Only show schemes that are already downloaded/cached.",
)
@click.option(
    "--pager",
    is_flag=True,
    help="Send output through a pager (less).",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_list(
    provider: str,
    scheme_type: str,
    name: str | None,
    output_format: str,
    available: bool,
    pager: bool,
    cache_dir: Path | None,
) -> None:
    """List available schemes from providers."""
    cache = DatabaseCache(cache_dir)

    providers_to_check = AVAILABLE_PROVIDERS if provider == "all" else [provider]

    all_schemes = []

    for prov in providers_to_check:
        scheme_dicts = cache.load_catalog(prov)
        if scheme_dicts:
            schemes = [_DictSchemeInfo(d) for d in scheme_dicts]
            all_schemes.extend(schemes)

    # Filter by type if specified
    if scheme_type != "all":
        target_type = scheme_type.lower()
        all_schemes = [s for s in all_schemes if s.scheme_type.lower() == target_type]
    else:
        all_schemes = [
            s
            for s in all_schemes
            if s.scheme_type.lower() in ("mlst", "cgmlst", "wgmlst", "rmlst")
        ]

    # Filter schemes by name regex if specified
    if name:
        try:
            pattern = re.compile(name, re.IGNORECASE)
            all_schemes = [s for s in all_schemes if pattern.search(s.organism)]
        except re.error as exc:
            err_console.print(f"[red]Invalid regex pattern:[/red] {exc}")
            return

    # Filter out blocked schemes
    blocked_schemes = _load_blocked_schemes()
    if blocked_schemes:
        all_schemes = [
            s
            for s in all_schemes
            if s.scheme_name not in blocked_schemes.get(s.provider, [])
            and s.extra.get("directory", "") not in blocked_schemes.get(s.provider, [])
        ]

    # Filter to only show downloaded/cached schemes if --available flag is set
    if available:
        all_schemes = [
            s for s in all_schemes if cache.is_downloaded(s.scheme_name, s.provider)
        ]
        if not all_schemes:
            console.print("[yellow]No downloaded schemes found.[/yellow]")
            console.print(
                "Run [bold]gmlst scheme download <scheme_name>[/bold] to download."
            )
            return

    # Sort schemes by name (natural sort: _1, _2, _10 instead of _1, _10, _2)
    all_schemes.sort(
        key=lambda s: (
            not cache.is_downloaded(s.scheme_name, s.provider),
            _natural_sort_key(s.scheme_name),
        )
    )

    payload = [
        {
            "scheme_name": s.scheme_name,
            "organism": s.organism,
            "scheme_type": s.scheme_type,
            "n_loci": s.n_loci,
            "provider": s.provider,
            "display_name": s.display_name,
            "extra": s.extra,
            "downloaded": cache.is_downloaded(s.scheme_name, s.provider),
        }
        for s in all_schemes
    ]

    output_mode = output_format.lower()
    if output_mode == "json":
        emit_output_json(payload, None)
        return

    if output_mode == "tsv":
        emit_output_tsv(payload, _SCHEME_LIST_COLUMNS, None)
        return

    if output_mode == "csv":
        emit_output_csv(payload, _SCHEME_LIST_COLUMNS, None)
        return

    if output_mode == "text":
        emit_output_text(_render_scheme_list_text(payload), None)
        return

    if not all_schemes:
        console.print("[yellow]No schemes found.[/yellow]")
        return

    title = f"Available Schemes ({len(all_schemes)} total)"
    if provider != "all":
        title += f" - Provider: {provider}"
    if scheme_type != "all":
        title += f" - Type: {scheme_type.upper()}"

    table = _build_scheme_list_table(all_schemes, cache, title, console.size.width)

    def _print_table() -> None:
        if pager:
            import io
            import subprocess

            buf = io.StringIO()
            pager_console = Console(
                file=buf,
                force_terminal=True,
                width=console.width,
            )
            pager_console.print(table)
            pager_console.print(
                "\nDownload: [bold]gmlst scheme download <scheme_name>[/bold]"
            )
            try:
                proc = subprocess.Popen(["less", "-RFX"], stdin=subprocess.PIPE)
                proc.communicate(buf.getvalue().encode())
                return
            except (OSError, FileNotFoundError):
                pass
        console.print(table)
        console.print("\nDownload: [bold]gmlst scheme download <scheme_name>[/bold]")

    emit_output_table(
        output=None,
        render_text=lambda: _render_scheme_list_text(payload),
        print_table=_print_table,
    )


@scheme_group.command("search", context_settings=HELP_SETTINGS)
@click.argument("pattern", required=True)
@click.option(
    "-p",
    "--provider",
    default="all",
    show_default=True,
    type=click.Choice(list(AVAILABLE_PROVIDERS) + ["all"], case_sensitive=False),
    help="Filter by provider.",
)
@click.option(
    "-t",
    "--type",
    "scheme_type",
    default="all",
    show_default=True,
    type=click.Choice(["mlst", "cgmlst", "wgmlst", "all"], case_sensitive=False),
    help="Filter by scheme type.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_search(
    pattern: str,
    provider: str,
    scheme_type: str,
    cache_dir: Path | None,
) -> None:
    """Search schemes by name, organism, description, or provider.

    PATTERN is a case-insensitive substring to search for.
    """
    cache = DatabaseCache(cache_dir)

    providers_to_check = AVAILABLE_PROVIDERS if provider == "all" else [provider]
    all_schemes = []
    for prov in providers_to_check:
        scheme_dicts = cache.load_catalog(prov)
        if scheme_dicts:
            schemes = [_DictSchemeInfo(d) for d in scheme_dicts]
            all_schemes.extend(schemes)

    if scheme_type != "all":
        target_type = scheme_type.lower()
        all_schemes = [s for s in all_schemes if s.scheme_type.lower() == target_type]
    else:
        all_schemes = [
            s
            for s in all_schemes
            if s.scheme_type.lower() in ("mlst", "cgmlst", "wgmlst", "rmlst")
        ]

    blocked_schemes = _load_blocked_schemes()
    if blocked_schemes:
        all_schemes = [
            s
            for s in all_schemes
            if s.scheme_name not in blocked_schemes.get(s.provider, [])
            and s.extra.get("directory", "") not in blocked_schemes.get(s.provider, [])
        ]

    needle = pattern.lower()
    matches = [
        s
        for s in all_schemes
        if needle in s.scheme_name.lower()
        or needle in (s.organism or "").lower()
        or needle in (s.display_name or "").lower()
        or needle in s.provider.lower()
    ]

    matches.sort(
        key=lambda s: (
            not cache.is_downloaded(s.scheme_name, s.provider),
            _natural_sort_key(s.scheme_name),
        )
    )

    if not matches:
        console.print(f"[yellow]No schemes matching '{pattern}'.[/yellow]")
        return

    title = f"Search: '{pattern}' ({len(matches)} matches)"
    table = _build_scheme_list_table(matches, cache, title, console.size.width)
    console.print(table)
    console.print("\nDownload: [bold]gmlst scheme download <scheme_name>[/bold]")


def _build_scheme_list_table(
    schemes: list[_DictSchemeInfo],
    cache: DatabaseCache,
    title: str,
    terminal_width: int,
) -> Table:
    table = Table(
        title=title,
        box=box.SQUARE,
        show_header=True,
        header_style="bold cyan",
        expand=True,
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("Status", justify="center", no_wrap=True, width=3)
    table.add_column("Scheme", style="cyan", overflow="fold", ratio=3, min_width=10)
    if terminal_width >= 100:
        table.add_column("Organism", overflow="fold", ratio=3)
    table.add_column("Type", style="dim", no_wrap=True, width=7)
    table.add_column("Loci", justify="right", style="dim", no_wrap=True, width=6)
    table.add_column("Provider", style="blue", no_wrap=True, width=10)
    if terminal_width >= 80:
        table.add_column("Description", style="dim", overflow="fold", ratio=4)

    for scheme in schemes:
        auth_note = (
            " [yellow](token required)[/yellow]"
            if scheme.extra.get("auth_required")
            else ""
        )
        is_dl = cache.is_downloaded(scheme.scheme_name, scheme.provider)
        status = "[bold green]✓[/bold green]" if is_dl else "[dim]-[/dim]"
        row = [
            status,
            scheme.scheme_name if not is_dl else f"[bold]{scheme.scheme_name}[/bold]",
        ]
        if terminal_width >= 100:
            row.append(scheme.organism)
        row.extend(
            [
                scheme.scheme_type,
                str(scheme.n_loci) if scheme.n_loci else "?",
                scheme.provider,
            ]
        )
        if terminal_width >= 80:
            row.append(scheme.display_name + auth_note)
        table.add_row(
            *row,
            style="on rgb(40,40,40)" if is_dl else None,
        )
    return table


_SCHEME_LIST_COLUMNS = [
    "downloaded",
    "scheme_name",
    "organism",
    "scheme_type",
    "n_loci",
    "provider",
    "display_name",
]

_SCHEME_SHOW_COLUMNS = [
    "scheme_name",
    "organism",
    "scheme_type",
    "n_loci",
    "n_profiles",
    "provider",
    "display_name",
    "downloaded",
    "scheme_dir",
    "downloaded_at",
    "updated_at",
]


def _count_profile_rows(path: Path) -> int:
    count = 0
    with path.open() as handle:
        for line in handle:
            if line.strip():
                count += 1
    return max(count - 1, 0)


def _render_scheme_list_text(payload: list[dict[str, object]]) -> str:
    if not payload:
        return "No schemes found."

    lines: list[str] = []
    for item in payload:
        status = "downloaded" if bool(item.get("downloaded")) else "not-downloaded"
        lines.append(
            " | ".join(
                [
                    str(item.get("scheme_name", "")),
                    str(item.get("organism", "")),
                    str(item.get("scheme_type", "")),
                    f"loci={item.get('n_loci', '')}",
                    str(item.get("provider", "")),
                    status,
                ]
            )
        )
    return "\n".join(lines)


def _render_scheme_show_text(payload: dict[str, object]) -> str:
    lines = [
        str(payload.get("display_name", "")),
        f"Name: {payload.get('scheme_name', '')}",
        f"Organism: {payload.get('organism', '')}",
        f"Type: {payload.get('scheme_type', '')}",
        f"Loci: {payload.get('n_loci', '')}",
    ]
    n_profiles = payload.get("n_profiles")
    if n_profiles is not None:
        lines.append(f"Profiles: {n_profiles}")
    lines.append(f"Provider: {payload.get('provider', '')}")
    if payload.get("downloaded_at"):
        lines.append(f"Downloaded: {payload.get('downloaded_at')}")
    if payload.get("updated_at"):
        lines.append(f"Updated: {payload.get('updated_at')}")
    if bool(payload.get("downloaded")):
        lines.append(f"Status: Downloaded -> {payload.get('scheme_dir', '')}")
    else:
        lines.append("Status: Not downloaded")
        lines.append(f"Run: gmlst scheme download {payload.get('scheme_name', '')}")
    return "\n".join(lines)


@scheme_group.command("show", context_settings=HELP_SETTINGS)
@click.argument("scheme", required=False)
@click.option(
    "--scheme",
    "-s",
    "scheme_opt",
    hidden=True,
    help="[deprecated] Use positional argument instead.",
)
@click.option(
    "-a",
    "--all",
    "show_all",
    is_flag=True,
    help="Show per-locus allele statistics (requires downloaded scheme).",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    default="table",
    show_default=True,
    type=click.Choice(["text", "table", "csv", "tsv", "json"], case_sensitive=False),
    help="Output format.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
@click.pass_context
def cmd_show(
    ctx: click.Context,
    scheme: str | None,
    scheme_opt: str | None,
    show_all: bool,
    output_format: str,
    cache_dir: Path | None,
) -> None:
    """Show detailed information about a specific scheme.

    SCHEME is the scheme name, e.g. 'saureus_1'.
    """
    scheme = scheme or scheme_opt
    if not scheme:
        console.print(
            "[yellow]No scheme specified.[/yellow] "
            "Use [bold]-s/--scheme[/bold] for details."
        )
        console.print(
            "Showing scheme list. For details: "
            "[bold]gmlst scheme show -s <scheme_name>[/bold]"
        )
        ctx.invoke(
            cmd_list,
            provider="all",
            scheme_type="all",
            name=None,
            output_format=output_format,
            available=False,
            cache_dir=cache_dir,
        )
        return

    cache = DatabaseCache(cache_dir)

    matches = _find_catalog_scheme_matches(cache, scheme)
    if not matches:
        _exit_scheme_not_found(scheme)
    _, scheme_info = matches[0]

    blocked_schemes = _load_blocked_schemes()
    provider_blocked = blocked_schemes.get(str(scheme_info.get("provider", "")), set())
    scheme_dir = scheme_info.get("extra", {}).get("directory", "")
    if scheme in provider_blocked or scheme_dir in provider_blocked:
        err_console.print(
            f"[red]Error:[/red] Scheme '{scheme}' is blocked for provider "
            f"'{scheme_info.provider}'."
        )
        sys.exit(1)

    is_downloaded = cache.is_downloaded(scheme, scheme_info.provider)
    scheme_dir = (
        str(cache.scheme_dir(scheme, scheme_info.provider)) if is_downloaded else None
    )
    scheme_meta = cache.get_scheme_metadata(scheme, scheme_info.provider)
    n_profiles: int | None = None
    if is_downloaded:
        try:
            loaded = cache.load_scheme(scheme, scheme_info.provider)
            if loaded.profile_file is not None and loaded.profile_file.exists():
                n_profiles = _count_profile_rows(loaded.profile_file)
        except FileNotFoundError:
            pass
    payload = {
        "scheme_name": scheme_info.scheme_name,
        "organism": scheme_info.organism,
        "scheme_type": scheme_info.scheme_type,
        "n_loci": scheme_info.n_loci,
        "n_profiles": n_profiles,
        "provider": scheme_info.provider,
        "display_name": scheme_info.display_name,
        "extra": scheme_info.extra,
        "downloaded": is_downloaded,
        "scheme_dir": scheme_dir,
        "downloaded_at": scheme_meta.get("downloaded_at", ""),
        "updated_at": scheme_meta.get("updated_at", ""),
    }

    locus_stats: list[dict[str, object]] = []
    if show_all and is_downloaded:
        try:
            loaded = cache.load_scheme(scheme, scheme_info.provider)
            from gmlst.fasta_io import iter_fasta_records

            for locus, tfa_path in sorted(loaded.allele_files.items()):
                lengths: list[int] = []
                for _header, seq in iter_fasta_records(tfa_path):
                    lengths.append(len(seq))
                if lengths:
                    locus_stats.append(
                        {
                            "locus": locus,
                            "alleles": len(lengths),
                            "min_len": min(lengths),
                            "max_len": max(lengths),
                            "avg_len": round(sum(lengths) / len(lengths)),
                        }
                    )
        except (FileNotFoundError, OSError):
            pass
        payload["locus_stats"] = locus_stats

    output_mode = output_format.lower()
    if output_mode == "json":
        emit_output_json(payload, None)
        return

    if output_mode == "tsv":
        emit_output_tsv([payload], _SCHEME_SHOW_COLUMNS, None)
        return

    if output_mode == "csv":
        emit_output_csv([payload], _SCHEME_SHOW_COLUMNS, None)
        return

    if output_mode == "text":
        emit_output_text(_render_scheme_show_text(payload), None)
        return
    table = Table(title=scheme_info.display_name, show_lines=False, padding=(0, 1))
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_row("Name", str(payload["scheme_name"]))
    table.add_row("Organism", str(payload["organism"]))
    table.add_row("Type", str(payload["scheme_type"]))
    table.add_row("Loci", str(payload["n_loci"]))
    n_profiles = payload.get("n_profiles")
    if n_profiles is not None:
        table.add_row("Profiles", str(n_profiles))
    table.add_row("Provider", str(payload["provider"]))
    downloaded_at = str(payload.get("downloaded_at", ""))
    updated_at = str(payload.get("updated_at", ""))
    if downloaded_at:
        table.add_row("Downloaded", downloaded_at)
    if updated_at:
        table.add_row("Updated", updated_at)
    if is_downloaded and scheme_dir is not None:
        table.add_row("Status", f"Downloaded -> {scheme_dir}")
    else:
        table.add_row("Status", "Not downloaded")
        table.add_row("Run", f"gmlst scheme download {scheme}")

    emit_output_table(
        output=None,
        render_text=lambda: _render_scheme_show_text(payload),
        print_table=lambda: console.print(table),
    )

    if show_all:
        if not is_downloaded:
            console.print(
                "\n[yellow]Scheme not downloaded."
                " Use [bold]gmlst scheme download[/bold] first.[/yellow]"
            )
            return
        if not locus_stats:
            console.print("\n[dim]No allele files found.[/dim]")
            return

        from rich.box import MINIMAL_HEAVY_HEAD as _MINIMAL

        locus_table = Table(
            title="Allele Statistics",
            box=_MINIMAL,
            expand=True,
            padding=(0, 1),
        )
        locus_table.add_column("Locus", style="cyan", no_wrap=True)
        locus_table.add_column("Alleles", justify="right", style="green")
        locus_table.add_column("Min bp", justify="right", style="dim")
        locus_table.add_column("Max bp", justify="right", style="dim")
        locus_table.add_column("Avg bp", justify="right", style="dim")

        total_alleles = 0
        for stat in locus_stats:
            locus_table.add_row(
                str(stat["locus"]),
                str(stat["alleles"]),
                str(stat["min_len"]),
                str(stat["max_len"]),
                str(stat["avg_len"]),
            )
            total_alleles += int(stat["alleles"])

        console.print(locus_table)
        console.print(f"\nTotal: {len(locus_stats)} loci, {total_alleles} alleles")


@scheme_group.command("download", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.argument("scheme", required=False)
@click.option(
    "--scheme",
    "-s",
    "scheme_opt",
    hidden=True,
    help="[deprecated] Use positional argument instead.",
)
@click.option("--force", is_flag=True, help="Re-download even if cached.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error logging.")
@click.option(
    "--download-tool",
    "download_tool",
    default="auto",
    show_default=True,
    type=click.Choice(DOWNLOAD_TOOL_CHOICES, case_sensitive=False),
    help="Download backend selection.",
)
@click.option(
    "--connections",
    "-x",
    type=click.IntRange(1, 128),
    default=4,
    show_default=True,
    help="Maximum concurrent downloads for scheme download.",
)
@click.option("--token", envvar="ENTEROBASE_TOKEN", help="API token (Enterobase only).")
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_download(
    scheme: str | None,
    scheme_opt: str | None,
    force: bool,
    quiet: bool,
    download_tool: str,
    connections: int,
    token: str | None,
    cache_dir: Path | None,
) -> None:
    """Download MLST/cgMLST scheme data from catalog.

    SCHEME is the scheme name, e.g. 'saureus_1'.
    """
    scheme = scheme or scheme_opt
    if not scheme:
        raise click.UsageError("Scheme name is required.")
    if quiet:
        setup_logging(verbose=False, quiet=True)

    cache = DatabaseCache(cache_dir)

    matches = _find_catalog_scheme_matches(cache, scheme, include_local=True)
    if not matches:
        _exit_scheme_not_found(scheme)

    detected_provider, match_info = matches[0]
    detected_type = str(match_info.get("scheme_type", "mlst"))

    blocked_schemes = _load_blocked_schemes()
    provider_blocked = blocked_schemes.get(detected_provider, set())
    scheme_dir = match_info.get("extra", {}).get("directory", "")
    if scheme in provider_blocked or scheme_dir in provider_blocked:
        err_console.print(
            f"[red]Error:[/red] Scheme '{scheme}' is blocked for provider "
            f"'{detected_provider}'."
        )
        sys.exit(1)

    if cache.is_downloaded(scheme, detected_provider) and not force:
        console.print(
            f"Scheme [cyan]{scheme}[/cyan] "
            f"(provider: [cyan]{detected_provider}[/cyan]) "
            "already cached. Use [bold]--force[/bold] to re-download."
        )
        return

    console.print(
        f"Downloading [cyan]{scheme}[/cyan] ({detected_type}) "
        f"from [bold]{detected_provider}[/bold] ..."
    )
    try:
        with console.status(f"[bold green]Downloading {scheme}...", spinner="dots"):
            cache.ensure_scheme(
                scheme,
                provider=detected_provider,
                scheme_type=detected_type,
                force=force,
                token=token,
                download_tool=_download_tool_choice(download_tool),
                max_connections=connections,
            )
        dest = cache.scheme_dir(scheme, detected_provider)
        console.print(f"[green]Done.[/green] Cached at [dim]{dest}[/dim]")
    except Exception as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


@scheme_group.command("update", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.option("--scheme", "-s", help="Update a specific cached scheme.")
@click.option(
    "--all",
    "-a",
    "update_all_schemes",
    is_flag=True,
    help="Update all cached scheme databases.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force refresh catalogs from providers before update actions.",
)
@click.option("--token", envvar="ENTEROBASE_TOKEN", help="API token (Enterobase).")
@click.option(
    "--download-tool",
    "download_tool",
    default="auto",
    show_default=True,
    type=click.Choice(DOWNLOAD_TOOL_CHOICES, case_sensitive=False),
    help="Download backend selection for scheme refresh.",
)
@click.option(
    "--connections",
    "-x",
    type=click.IntRange(1, 128),
    default=4,
    help="Maximum concurrent downloads for scheme update.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_update(
    scheme: str | None,
    update_all_schemes: bool,
    force: bool,
    token: str | None,
    download_tool: str,
    connections: int | None,
    cache_dir: Path | None,
) -> None:
    """Update local catalogs or refresh a specific cached scheme."""
    cache = DatabaseCache(cache_dir)
    selected_download_tool = _download_tool_choice(download_tool)

    if scheme and update_all_schemes:
        err_console.print("[red]Error:[/red] Use either --scheme or --all, not both.")
        sys.exit(1)

    if scheme:
        if force:
            console.print("Refreshing provider catalogs before scheme update ...")
            for prov in AVAILABLE_PROVIDERS:
                try:
                    cache.update_catalog(prov, scheme_type="all", token=token)
                except (OSError, ValueError):
                    continue

        matches = _find_catalog_scheme_matches(cache, scheme)
        if not matches:
            err_console.print(
                f"[red]Error:[/red] Could not determine provider for '{scheme}'. "
                "Scheme may not exist in any catalog."
            )
            sys.exit(1)
        provider, match_info = matches[0]
        scheme_type = str(match_info.get("scheme_type", "mlst"))

        blocked_schemes = _load_blocked_schemes()
        provider_blocked = blocked_schemes.get(provider, set())
        scheme_dir = match_info.get("extra", {}).get("directory", "")
        if scheme in provider_blocked or scheme_dir in provider_blocked:
            err_console.print(
                f"[red]Error:[/red] Scheme '{scheme}' is blocked for provider "
                f"'{provider}'."
            )
            sys.exit(1)

        console.print(
            f"Checking updates for [cyan]{scheme}[/cyan] "
            f"from [bold]{provider}[/bold] ..."
        )
        try:
            with console.status(f"[bold green]Updating {scheme}...", spinner="dots"):
                _, changed = cache.update_scheme(
                    scheme,
                    provider=provider,
                    scheme_type=scheme_type,
                    token=token,
                    download_tool=selected_download_tool,
                    max_connections=connections,
                )
            dest = cache.scheme_dir(scheme, provider)
            if changed:
                console.print(f"[green]Updated.[/green] Cached at [dim]{dest}[/dim]")
            else:
                console.print(f"[green]Up to date.[/green] Cached at [dim]{dest}[/dim]")
        except FileNotFoundError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            err_console.print(f"Run [bold]gmlst scheme download {scheme}[/bold] first.")
            sys.exit(1)
        except Exception as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            sys.exit(1)
    elif update_all_schemes:
        cached_schemes = cache.list_cached()
        if not cached_schemes:
            console.print("[yellow]No cached schemes found.[/yellow]")
            console.print(
                "Run [bold]gmlst scheme download <scheme_name>[/bold] to download."
            )
            return

        if force:
            console.print(
                "Refreshing provider catalogs before updating cached schemes ..."
            )
            for prov in AVAILABLE_PROVIDERS:
                try:
                    cache.update_catalog(prov, scheme_type="all", token=token)
                except (OSError, ValueError):
                    continue

        console.print(f"Updating {len(cached_schemes)} cached scheme database(s) ...")
        changed_count = 0
        failed_count = 0
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            transient=False,
        )
        with progress:
            task = progress.add_task("Updating schemes", total=len(cached_schemes))
            for item in cached_schemes:
                scheme_name = str(item["scheme"])
                provider = str(item["provider"])
                scheme_type = str(item.get("scheme_type", "mlst"))
                progress.update(
                    task,
                    description=f"Updating {scheme_name}",
                )
                try:
                    _, changed = cache.update_scheme(
                        scheme_name,
                        provider=provider,
                        scheme_type=scheme_type,
                        token=token,
                        download_tool=selected_download_tool,
                        max_connections=connections,
                    )
                except Exception as exc:
                    failed_count += 1
                    progress.console.print(
                        f"  [red]{scheme_name} ({provider}):[/red] {exc}"
                    )
                    progress.advance(task)
                    continue
                if changed:
                    changed_count += 1
                progress.advance(task)
        console.print(
            f"[green]Done.[/green] Updated: {changed_count}; "
            f"unchanged: {len(cached_schemes) - changed_count - failed_count}; "
            f"failed: {failed_count}"
        )
        if failed_count:
            sys.exit(1)
    else:
        # Update all catalogs
        if force:
            console.print("Force refreshing all catalogs ...")
        else:
            console.print("Updating all catalogs ...")
        total = 0
        providers_list = list(AVAILABLE_PROVIDERS)
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            transient=False,
        )
        with progress:
            task = progress.add_task("Refreshing catalogs", total=len(providers_list))
            for prov in providers_list:
                progress.update(task, description=f"Fetching {prov}")
                try:
                    schemes = cache.update_catalog(prov, scheme_type="all", token=token)
                    total += len(schemes)
                    progress.console.print(
                        f"  [green]{prov}:[/green] {len(schemes)} schemes"
                    )
                except Exception as exc:
                    progress.console.print(f"  [red]{prov}:[/red] {exc}")
                progress.advance(task)
        console.print(f"[green]Done.[/green] Total: {total} schemes")


@scheme_group.command("create", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.option(
    "--type",
    "-t",
    "scheme_type",
    required=True,
    type=click.Choice(["mlst"], case_sensitive=False),
    help="Scheme type (only mlst supported currently).",
)
@click.option(
    "--source",
    "-s",
    required=True,
    help="Source scheme to extend (e.g., saureus_1, ecoli_1).",
)
@click.option(
    "--data-dir",
    "--datadir",
    "data_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing *_novel.fasta and profiles_novel.txt.",
)
@click.option(
    "--desc",
    default="",
    help="Description for the custom scheme.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_create(
    scheme_type: str,
    source: str,
    data_dir: Path,
    desc: str,
    cache_dir: Path | None,
) -> None:
    """Create a custom scheme by merging public scheme with novel data.

    The custom scheme will be named automatically (custom_1, custom_2, ...).
    """
    from gmlst.novel import NovelDataReader

    cache = DatabaseCache(cache_dir)

    source_matches = _find_catalog_scheme_matches(
        cache,
        source,
        ignore_catalog_errors=True,
    )
    source_provider = source_matches[0][0] if source_matches else None

    if not source_provider:
        err_console.print(f"[red]Error:[/red] Source scheme '{source}' not found.")
        err_console.print("Run 'gmlst scheme list' to see available schemes.")
        sys.exit(1)

    # Ensure source scheme is cached
    try:
        source_scheme = cache.ensure_scheme(source, provider=source_provider)
    except Exception as exc:
        err_console.print(f"[red]Error:[/red] Could not load source scheme: {exc}")
        sys.exit(1)

    # Read novel data
    reader = NovelDataReader(data_dir)
    novel_alleles, novel_profiles = reader.read_all()

    if not novel_alleles and not novel_profiles:
        _exit_no_novel_data(show_expected_hint=True)

    # Validate novel data against source scheme
    errors = reader.validate_against_scheme(
        novel_alleles, novel_profiles, source_scheme.loci
    )
    _exit_validation_errors(errors)

    with _locked_local_catalog(cache):
        # Get next custom scheme number
        custom_id = _get_next_custom_id(cache)
        custom_name = f"custom_{custom_id}"

        console.print(
            f"Creating [cyan]{custom_name}[/cyan] based on [cyan]{source}[/cyan]..."
        )

        # Create custom scheme directory
        custom_dir = cache.scheme_dir(custom_name, provider="local")
        custom_dir.mkdir(parents=True, exist_ok=True)

        # Merge allele files
        for locus in source_scheme.loci:
            source_file = source_scheme.allele_files.get(locus)
            if not source_file:
                continue

            target_file = custom_dir / f"{locus}.tfa"

            # Copy original alleles
            with open(target_file, "w") as out:
                # Write original alleles
                if source_file.exists():
                    with open(source_file) as f:
                        out.write(f.read())

                # Append novel alleles for this locus
                if locus in novel_alleles:
                    for allele in novel_alleles[locus]:
                        samples_str = " ".join(allele.samples)
                        out.write(f">{locus}_{allele.allele_id} sample={samples_str}\n")
                        _write_wrapped_sequence(out, allele.sequence)

        # Merge profiles
        source_profile = source_scheme.profile_file
        target_profile = custom_dir / f"{custom_name}.txt"

        with open(target_profile, "w") as out:
            # Write header
            header = "ST\t" + "\t".join(source_scheme.loci) + "\n"
            out.write(header)

            # Copy original profiles
            if source_profile and source_profile.exists():
                with open(source_profile) as f:
                    reader_csv = csv.DictReader(f, delimiter="\t")
                    for row in reader_csv:
                        st = row.get("ST", "")
                        parts = [st]
                        for locus in source_scheme.loci:
                            parts.append(row.get(locus, "-"))
                        out.write("\t".join(parts) + "\n")

            # Append novel profiles
            for profile in novel_profiles:
                parts = [profile.st]
                for locus in source_scheme.loci:
                    parts.append(profile.allele_calls.get(locus, "-"))
                out.write("\t".join(parts) + "\n")

        # Write metadata
        meta = build_custom_scheme_metadata(
            custom_name=custom_name,
            scheme_type=scheme_type,
            source=source,
            source_provider=source_provider,
            description=desc,
            created_at=_utc_now_iso(),
            loci=source_scheme.loci,
            novel_alleles=novel_alleles,
            novel_profiles=novel_profiles,
        )

        meta_file = custom_dir / ".meta.json"
        emit_output_json(meta, meta_file)

        # Update local catalog
        _update_local_catalog(cache, custom_name, source, desc, len(source_scheme.loci))

    console.print(f"[green]Created custom scheme:[/green] {custom_name}")
    console.print(f"  Location: {custom_dir}")
    console.print(f"  Based on: {source} ({source_provider})")
    console.print(f"  Novel alleles: {sum(len(a) for a in novel_alleles.values())}")
    console.print(f"  Novel profiles: {len(novel_profiles)}")


def _get_next_custom_id(cache: DatabaseCache) -> int:
    """Get the next available custom scheme ID."""
    catalog_path = cache._catalog_path("local")

    if not catalog_path.exists():
        return 1

    try:
        data = json.loads(catalog_path.read_text())
        schemes = data.get("schemes", [])

        max_id = 0
        for scheme in schemes:
            name = scheme.get("scheme_name", "")
            if name.startswith("custom_"):
                try:
                    num = int(name.split("_")[1])
                    max_id = max(max_id, num)
                except (IndexError, ValueError):
                    continue

        return max_id + 1
    except (OSError, json.JSONDecodeError) as exc:
        logging.getLogger(__name__).warning(
            "Failed to read local catalog for custom ID: %s", exc
        )
        return 1


def _update_local_catalog(
    cache: DatabaseCache,
    scheme_name: str,
    based_on: str,
    description: str,
    n_loci: int,
) -> None:
    """Add custom scheme to local catalog."""
    catalog_path = cache._catalog_path("local")

    schemes: list[dict[str, object]] = []
    if catalog_path.exists():
        try:
            data = json.loads(catalog_path.read_text())
            schemes = data.get("schemes", [])
        except (OSError, json.JSONDecodeError) as exc:
            logging.getLogger(__name__).warning(
                "Failed to read local catalog for update: %s", exc
            )

    # Check if scheme already exists
    existing = next((s for s in schemes if s.get("scheme_name") == scheme_name), None)

    scheme_info = {
        "scheme_name": scheme_name,
        "display_name": description or scheme_name,
        "organism": f"Custom ({based_on})",
        "scheme_type": "mlst",
        "n_loci": n_loci,
        "provider": "local",
        "extra": {"based_on": based_on, "custom": True},
    }

    if existing:
        # Update existing
        existing.update(scheme_info)
    else:
        schemes.append(scheme_info)

    payload = {
        "provider": "local",
        "scheme_type": "mlst",
        "updated_at": _utc_now_iso(),
        "count": len(schemes),
        "schemes": schemes,
    }

    emit_output_json(payload, catalog_path)


@scheme_group.command(
    "update-custom",
    context_settings=HELP_SETTINGS,
    no_args_is_help=True,
)
@click.argument("scheme", required=False)
@click.option(
    "--scheme",
    "-s",
    "scheme_opt",
    hidden=True,
    help="[deprecated] Use positional argument instead.",
)
@click.option(
    "--data-dir",
    "--datadir",
    "data_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing new *_novel.fasta and profiles_novel.txt.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_update_custom(
    scheme: str | None,
    scheme_opt: str | None,
    data_dir: Path,
    cache_dir: Path | None,
) -> None:
    """Update a custom scheme with additional novel data.

    SCHEME is the custom scheme name (e.g., custom_1).
    Only works with local (custom) schemes. The novel data will be merged
    with the existing scheme, continuing the numbering from where it left off.
    """
    scheme = scheme or scheme_opt
    if not scheme:
        raise click.UsageError("Scheme name is required.")
    from gmlst.novel import NovelDataReader

    cache = DatabaseCache(cache_dir)

    # Verify this is a local scheme
    if not scheme.startswith("custom_"):
        err_console.print(
            f"[red]Error:[/red] Scheme '{scheme}' is not a custom scheme. "
            "Only custom schemes (custom_*) can be updated."
        )
        sys.exit(1)

    scheme_dir = cache.scheme_dir(scheme, provider="local")
    if not scheme_dir.exists():
        err_console.print(f"[red]Error:[/red] Custom scheme '{scheme}' not found.")
        sys.exit(1)

    # Load existing metadata
    meta_file = scheme_dir / ".meta.json"
    if not meta_file.exists():
        err_console.print(
            f"[red]Error:[/red] Scheme metadata not found for '{scheme}'."
        )
        sys.exit(1)

    meta = json.loads(meta_file.read_text())
    loci = meta.get("loci", [])

    # Read new novel data
    reader = NovelDataReader(data_dir)
    novel_alleles, novel_profiles = reader.read_all()

    if not novel_alleles and not novel_profiles:
        _exit_no_novel_data(show_expected_hint=False)

    # Validate against scheme
    errors = reader.validate_against_scheme(novel_alleles, novel_profiles, loci)
    _exit_validation_errors(errors)

    # Get current allele numbers for each locus
    last_allele_nums = meta.get("last_allele_number", {})
    current_st_num = 0
    for st_str in meta.get("novel_profiles", []):
        try:
            num = int(st_str.replace("N", ""))
            current_st_num = max(current_st_num, num)
        except ValueError:
            pass

    console.print(f"Updating [cyan]{scheme}[/cyan]...")

    # Renumber new alleles and append to .tfa files
    allele_mapping = {}  # Maps old allele IDs to new ones

    for locus in loci:
        if locus not in novel_alleles:
            continue

        last_num = last_allele_nums.get(locus, 0)

        # Renumber new alleles
        for allele in novel_alleles[locus]:
            last_num += 1
            new_id = f"n{last_num}"
            old_id = allele.allele_id
            allele_mapping[f"{locus}_{old_id}"] = f"{locus}_{new_id}"
            allele.allele_id = new_id

        last_allele_nums[locus] = last_num

        # Append to .tfa file
        tfa_file = scheme_dir / f"{locus}.tfa"
        with open(tfa_file, "a") as f:
            for allele in novel_alleles[locus]:
                samples_str = " ".join(allele.samples)
                f.write(f">{locus}_{allele.allele_id} sample={samples_str}\n")
                _write_wrapped_sequence(f, allele.sequence)

    # Renumber new profiles and append
    profile_file = scheme_dir / f"{scheme}.txt"

    with open(profile_file, "a") as f:
        for profile in novel_profiles:
            current_st_num += 1
            st = f"N{current_st_num}"

            # Replace allele IDs using mapping
            parts = [st]
            for locus in loci:
                allele = profile.allele_calls.get(locus, "-")
                # Check if this allele needs remapping
                mapped_key = f"{locus}_{allele}"
                if mapped_key in allele_mapping:
                    # Extract just the nX part
                    allele = allele_mapping[mapped_key].split("_")[1]
                parts.append(allele)

            f.write("\t".join(parts) + "\n")

    # Update metadata
    meta = merge_custom_scheme_update_metadata(
        meta,
        last_allele_numbers=last_allele_nums,
        current_st_num=current_st_num,
        novel_alleles=novel_alleles,
        updated_at=_utc_now_iso(),
    )
    emit_output_json(meta, meta_file)

    console.print(f"[green]Updated custom scheme:[/green] {scheme}")
    console.print(f"  New alleles added: {sum(len(a) for a in novel_alleles.values())}")
    console.print(f"  New profiles added: {len(novel_profiles)}")


@scheme_group.command("export", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.argument("scheme", required=False)
@click.option(
    "--scheme",
    "-s",
    "scheme_opt",
    hidden=True,
    help="[deprecated] Use positional argument instead.",
)
@click.option(
    "--format",
    required=True,
    type=click.Choice(["grapetree", "original"], case_sensitive=False),
    help="Export format.",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Output file path.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_export(
    scheme: str | None,
    scheme_opt: str | None,
    format: str,
    output: Path,
    cache_dir: Path | None,
) -> None:
    """Export a scheme profile data to various formats.

    SCHEME is the scheme name (e.g., custom_1).
    GrapeTree format: TSV with ST column, compatible with GrapeTree MST visualization.
    Original format: Copy of the scheme's profile file.
    """
    scheme = scheme or scheme_opt
    if not scheme:
        raise click.UsageError("Scheme name is required.")
    cache = DatabaseCache(cache_dir)

    # Try to find scheme in any provider
    scheme_obj = None
    provider = None

    for prov in list(AVAILABLE_PROVIDERS) + ["local"]:
        try:
            s = cache.load_scheme(scheme, provider=prov)
            scheme_obj = s
            provider = prov
            break
        except (OSError, ValueError, KeyError):
            continue

    if not scheme_obj:
        err_console.print(f"[red]Error:[/red] Scheme '{scheme}' not found.")
        sys.exit(1)

    if not scheme_obj.profile_file or not scheme_obj.profile_file.exists():
        err_console.print(f"[red]Error:[/red] No profile file found for '{scheme}'.")
        sys.exit(1)

    console.print(f"Exporting [cyan]{scheme}[/cyan] to {format} format...")

    if format.lower() == "original":
        # Simple copy
        import shutil

        shutil.copy(scheme_obj.profile_file, output)

    elif format.lower() == "grapetree":
        # GrapeTree format: TSV with header starting with #
        # First column is strain ID, ST column is optional
        with open(scheme_obj.profile_file) as f_in:
            reader = csv.DictReader(f_in, delimiter="\t")

            with open(output, "w") as f_out:
                # Write header with # prefix (GrapeTree convention)
                header = ["Strain"] + scheme_obj.loci
                f_out.write("#" + "\t".join(header) + "\n")

                # Write data rows
                for row in reader:
                    st = row.get("ST", "-")
                    # Use ST as strain ID prefix
                    strain_id = f"ST{st}" if st != "-" else "Unknown"

                    parts = [strain_id]
                    for locus in scheme_obj.loci:
                        allele = row.get(locus, "-")
                        parts.append(allele)

                    f_out.write("\t".join(parts) + "\n")

    console.print(f"[green]Exported to:[/green] {output}")
    console.print(f"  Format: {format}")
    console.print(f"  Provider: {provider}")
    console.print(f"  Profiles: exported from {scheme_obj.profile_file}")
