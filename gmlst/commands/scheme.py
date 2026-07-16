"""Scheme management commands for gmlst."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import click
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
    _natural_sort_key,
    console,
    emit_output_csv,
    emit_output_json,
    emit_output_table,
    emit_output_text,
    emit_output_tsv,
    err_console,
)
from gmlst.commands.scheme_common import (
    DOWNLOAD_TOOL_CHOICES,
    HELP_SETTINGS,
    _download_tool_choice,
    _exit_scheme_not_found,
    _find_catalog_scheme_matches,
    _load_schemes,
    _provider_choices,
    _reject_if_blocked,
)
from gmlst.commands.scheme_custom import cmd_create, cmd_update_custom
from gmlst.commands.scheme_render import (
    _SCHEME_LIST_COLUMNS,
    _SCHEME_SHOW_COLUMNS,
    _build_scheme_list_table,
    _render_scheme_list_text,
    _render_scheme_show_text,
)
from gmlst.database.cache import DatabaseCache
from gmlst.database.providers import AVAILABLE_PROVIDERS
from gmlst.fasta_io import count_profile_rows
from gmlst.utils import setup_logging


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

    all_schemes = _load_schemes(cache, provider, scheme_type)

    # Filter schemes by name regex if specified
    if name:
        try:
            pattern = re.compile(name, re.IGNORECASE)
            all_schemes = [s for s in all_schemes if pattern.search(s.organism)]
        except re.error as exc:
            err_console.print(f"[red]Invalid regex pattern:[/red] {exc}")
            return

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
                # less not installed — fall through to console.print
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

    all_schemes = _load_schemes(cache, provider, scheme_type)

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

    _reject_if_blocked(scheme, scheme_info, str(scheme_info.get("provider", "")))

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
                n_profiles = count_profile_rows(loaded.profile_file)
        except FileNotFoundError:
            # scheme not downloaded yet — n_profiles stays None
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

    locus_stats: list[dict[str, int | str]] = []
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
            # scheme not fully downloaded — skip locus stats
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

    _reject_if_blocked(scheme, match_info, detected_provider)

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

        _reject_if_blocked(scheme, match_info, provider)

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


scheme_group.add_command(cmd_create)
scheme_group.add_command(cmd_update_custom)
