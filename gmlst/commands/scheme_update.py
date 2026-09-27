"""``gmlst scheme update``: refresh catalogs and downloaded schemes."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.table import Table

from gmlst.commands.common import (
    HELP_SETTINGS,
    cache_dir_option,
    console,
    emit_versioned_json,
    err_console,
    make_progress,
    status_console,
)
from gmlst.commands.scheme_common import (
    DOWNLOAD_TOOL_CHOICES,
    _download_tool_choice,
    refresh_all_catalogs,
    resolve_scheme_or_exit,
)
from gmlst.database.cache import DatabaseCache
from gmlst.database.providers import AVAILABLE_PROVIDERS
from gmlst.schema_versions import SCHEME_OP_V1


@click.command("update", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.option("--scheme", "-s", help="Update a specific cached scheme.")
@click.option(
    "--all",
    "-a",
    "update_all_schemes",
    is_flag=True,
    help="Update all cached scheme databases.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt when updating all schemes.",
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
    "--format",
    "output_format",
    default="text",
    show_default=True,
    type=click.Choice(["text", "json"], case_sensitive=False),
    help="Output format for completion summary.",
)
@cache_dir_option
def cmd_update(
    scheme: str | None,
    update_all_schemes: bool,
    yes: bool,
    force: bool,
    token: str | None,
    download_tool: str,
    connections: int | None,
    output_format: str,
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
            status_console.print(
                "Refreshing provider catalogs before scheme update ..."
            )
            refresh_all_catalogs(cache, token=token)

        provider, match_info = resolve_scheme_or_exit(cache, scheme)
        scheme_type = match_info.scheme_type or "mlst"

        status_console.print(
            f"Checking updates for [cyan]{scheme}[/cyan] "
            f"from [bold]{provider}[/bold] ..."
        )
        try:
            with status_console.status(
                f"[bold green]Updating {scheme}...", spinner="dots"
            ):
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
                status_console.print(
                    f"[green]Updated.[/green] Cached at [dim]{dest}[/dim]"
                )
            else:
                status_console.print(
                    f"[green]Up to date.[/green] Cached at [dim]{dest}[/dim]"
                )
            if output_format == "json":
                emit_versioned_json(
                    {
                        "scheme": scheme,
                        "provider": provider,
                        "changed": bool(changed),
                    },
                    None,
                    SCHEME_OP_V1,
                )
        except FileNotFoundError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            err_console.print(f"Run [bold]gmlst scheme download {scheme}[/bold] first.")
            sys.exit(1)
        except Exception as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            err_console.print(
                "[dim]Hint: check network connectivity to the provider, "
                "or try again later.[/dim]"
            )
            sys.exit(1)
    elif update_all_schemes:
        cached_schemes = cache.list_cached()
        if not cached_schemes:
            status_console.print("[yellow]No cached schemes found.[/yellow]")
            status_console.print(
                "Run [bold]gmlst scheme download <scheme_name>[/bold] to download."
            )
            return

        if force:
            status_console.print(
                "Refreshing provider catalogs before updating cached schemes ..."
            )
            refresh_all_catalogs(cache, token=token)

        if not yes:
            status_console.print(
                f"\n[bold]Cached schemes to update ({len(cached_schemes)}):[/bold]"
            )
            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("Scheme", style="cyan")
            table.add_column("Provider", style="dim")
            table.add_column("Type", style="dim")
            table.add_column("Downloaded", style="dim")
            for item in cached_schemes:
                table.add_row(
                    str(item["scheme"]),
                    str(item["provider"]),
                    str(item.get("scheme_type", "?")),
                    str(item.get("downloaded_at", "?"))[:10] or "?",
                )
            status_console.print(table)
            status_console.print(
                "\n[dim]Each scheme requires a network check and may download data. "
                "This can take several minutes.[/dim]"
            )
            if not click.confirm("Proceed with updating all cached schemes?"):
                status_console.print("[yellow]Aborted.[/yellow]")
                return

        status_console.print(
            f"Updating {len(cached_schemes)} cached scheme database(s) ..."
        )
        changed_count = 0
        failed_count = 0
        results: list[dict[str, object]] = []
        progress = make_progress()
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
                    results.append(
                        {
                            "scheme": scheme_name,
                            "provider": provider,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
                    progress.console.print(
                        f"  [red]✗ {scheme_name}[/red] [dim]({provider})[/dim] — {exc}"
                    )
                    progress.advance(task)
                    continue
                if changed:
                    changed_count += 1
                    results.append(
                        {
                            "scheme": scheme_name,
                            "provider": provider,
                            "status": "updated",
                            "error": None,
                        }
                    )
                else:
                    results.append(
                        {
                            "scheme": scheme_name,
                            "provider": provider,
                            "status": "unchanged",
                            "error": None,
                        }
                    )
                progress.advance(task)
        if output_format == "json":
            emit_versioned_json(
                {
                    "total": len(cached_schemes),
                    "updated": changed_count,
                    "unchanged": len(cached_schemes) - changed_count - failed_count,
                    "failed": failed_count,
                    "results": results,
                },
                None,
                SCHEME_OP_V1,
            )
        else:
            status_console.print(
                f"[green]Done.[/green] Updated: {changed_count}; "
                f"unchanged: {len(cached_schemes) - changed_count - failed_count}; "
                f"failed: {failed_count}"
            )
        if failed_count:
            sys.exit(1)
    else:
        # Update all catalogs
        if force:
            status_console.print("Force refreshing all catalogs ...")
        else:
            status_console.print("Updating all catalogs ...")
        total = 0
        failed_providers = 0
        providers_list = list(AVAILABLE_PROVIDERS)
        progress = make_progress()
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
                    failed_providers += 1
                    progress.console.print(f"  [red]{prov}:[/red] {exc}")
                progress.advance(task)
        console.print(f"[green]Done.[/green] Total: {total} schemes")
        if failed_providers:
            sys.exit(1)
