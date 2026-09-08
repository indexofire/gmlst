"""Rendering helpers for `scheme list` / `scheme show` output (tables and text)."""

from __future__ import annotations

from rich import box
from rich.table import Table

from gmlst.database.cache import DatabaseCache
from gmlst.database.providers.base import SchemeInfo


def _build_scheme_list_table(
    schemes: list[SchemeInfo],
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


def render_scheme_show_table(
    payload: dict[str, object],
    scheme: str,
    locus_stats: list[dict[str, int | str]],
) -> Table:
    """Build rich Table for `scheme show` output."""
    table = Table(title=str(payload["display_name"]), show_lines=False, padding=(0, 1))
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
    is_downloaded = bool(payload.get("downloaded"))
    scheme_dir = str(payload.get("scheme_dir") or "")
    if is_downloaded and scheme_dir:
        table.add_row("Status", f"Downloaded -> {scheme_dir}")
    else:
        table.add_row("Status", "Not downloaded")
        table.add_row("Run", f"gmlst scheme download {scheme}")
    return table


def render_locus_stats_table(locus_stats: list[dict[str, int | str]]) -> Table:
    """Build rich Table for per-locus allele statistics."""
    locus_table = Table(
        title="Allele Statistics",
        box=box.MINIMAL_HEAVY_HEAD,
        expand=True,
        padding=(0, 1),
    )
    locus_table.add_column("Locus", style="cyan", no_wrap=True)
    locus_table.add_column("Alleles", justify="right", style="green")
    locus_table.add_column("Min bp", justify="right", style="dim")
    locus_table.add_column("Max bp", justify="right", style="dim")
    locus_table.add_column("Avg bp", justify="right", style="dim")
    for stat in locus_stats:
        locus_table.add_row(
            str(stat["locus"]),
            str(stat["alleles"]),
            str(stat["min_len"]),
            str(stat["max_len"]),
            str(stat["avg_len"]),
        )
    return locus_table
