"""``gmlst scheme update-fingerprints``: build the species fingerprint DB."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from gmlst.commands.common import (
    HELP_SETTINGS,
    cache_dir_option,
    err_console,
    status_console,
)
from gmlst.commands.scheme_common import build_fingerprints_with_progress
from gmlst.core import species_id
from gmlst.database.cache import DatabaseCache


@click.command("update-fingerprints", context_settings=HELP_SETTINGS)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip overwrite confirmation when the fingerprint database exists.",
)
@click.option(
    "--organisms",
    "-o",
    "organisms",
    default=None,
    help="Comma-separated organisms to fingerprint (default: all catalog organisms).",
)
@click.option(
    "--connections",
    "-x",
    type=click.IntRange(1, 128),
    default=4,
    show_default=True,
    help="Maximum concurrent downloads for scheme downloads.",
)
@click.option(
    "--missing-only",
    is_flag=True,
    help=(
        "Only build organisms absent from the existing database (local, or "
        "the bundled one) and merge them in; existing entries are kept."
    ),
)
@cache_dir_option
def cmd_update_fingerprints(
    yes: bool,
    organisms: str | None,
    connections: int,
    missing_only: bool,
    cache_dir: Path | None,
) -> None:
    """Build the local species fingerprint database for auto-detection.

    Downloads one (usually small) scheme per catalog organism and sketches
    its allele sequences; expect a long run on first use.
    """
    cache = DatabaseCache(cache_dir)
    fingerprints_file = species_id.fingerprints_path(cache)

    selected: set[str] | None = None
    if organisms:
        selected = {item.strip() for item in organisms.split(",") if item.strip()}

    if missing_only:
        _update_missing_fingerprints(
            cache, fingerprints_file, selected=selected, connections=connections
        )
        return

    if (
        fingerprints_file.exists()
        and not yes
        and not click.confirm(
            f"Overwrite existing fingerprint database at {fingerprints_file}?"
        )
    ):
        status_console.print("[yellow]Aborted.[/yellow]")
        return

    status_console.print("Building species fingerprint database ...")
    payload, counts = build_fingerprints_with_progress(
        cache, organisms=selected, max_connections=connections
    )
    species_id.save_fingerprints(payload, fingerprints_file)

    skipped = counts["skip"]
    if counts["sketch"] == 0:
        err_console.print(
            "[red]Error:[/red] No organism fingerprints were built"
            + (
                f" for: {', '.join(sorted(selected))}"
                if selected
                else "; catalogs may be empty"
            )
            + "."
        )
        sys.exit(1)
    status_console.print(
        f"[green]Done.[/green] Organisms sketched: {counts['sketch']}; "
        f"schemes downloaded: {counts['download']}; skipped: {skipped}"
    )
    status_console.print(f"Fingerprints written to [cyan]{fingerprints_file}[/cyan]")


def _update_missing_fingerprints(
    cache: DatabaseCache,
    fingerprints_file: Path,
    *,
    selected: set[str] | None,
    connections: int,
) -> None:
    """Sketch only organisms missing from the current database, then merge."""
    base_file = (
        fingerprints_file
        if fingerprints_file.exists()
        else species_id.bundled_fingerprints_path()
    )
    if base_file is None:
        base: dict = {
            "version": 1,
            "k": species_id.FINGERPRINT_K,
            "sample_rate": species_id.FINGERPRINT_SAMPLE_RATE,
            "fingerprints": [],
        }
    else:
        base = species_id.load_fingerprints(base_file)
    known = {str(f.get("organism", "")) for f in base.get("fingerprints", [])}

    status_console.print(
        f"Building missing fingerprints ({len(known)} organisms already present) ..."
    )
    payload, counts = build_fingerprints_with_progress(
        cache, organisms=selected, exclude=known, max_connections=connections
    )
    if counts["sketch"] == 0:
        status_console.print(
            "[green]Done.[/green] Every catalog organism already has a fingerprint"
            + (f"; skipped: {counts['skip']}" if counts["skip"] else "")
            + "."
        )
        return
    try:
        merged = species_id.merge_fingerprints(base, payload)
    except ValueError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        err_console.print("Rebuild the full database without --missing-only.")
        sys.exit(1)
    species_id.save_fingerprints(merged, fingerprints_file)
    status_console.print(
        f"[green]Done.[/green] Organisms added: {counts['sketch']}; "
        f"schemes downloaded: {counts['download']}; skipped: {counts['skip']}"
    )
    status_console.print(f"Fingerprints written to [cyan]{fingerprints_file}[/cyan]")
