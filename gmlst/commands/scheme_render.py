from __future__ import annotations

from rich import box
from rich.table import Table

from gmlst.commands.common import _DictSchemeInfo
from gmlst.database.cache import DatabaseCache


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
