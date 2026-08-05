from __future__ import annotations

import sys

from gmlst.commands.scheme_common import _find_catalog_scheme_matches


def resolve_scheme_type(
    cache,
    scheme: str,
    provider: str | None,
) -> str | None:
    matches = _find_catalog_scheme_matches(cache, scheme, include_local=True)
    for prov, info in matches:
        if provider is None or prov == provider:
            stype = info.get("scheme_type")
            if isinstance(stype, str):
                return stype.lower()
    return None


def validate_scheme_mode(
    *,
    scheme: str,
    scheme_type: str | None,
    mode: str,
    err_console,
) -> None:
    if scheme_type is None:
        return

    if mode == "mlst" and scheme_type != "mlst":
        err_console.print(
            f"[red]Error:[/red] Scheme '[cyan]{scheme}[/cyan]' is type "
            f"'[yellow]{scheme_type}[/yellow]'."
        )
        err_console.print(
            f"Use [bold]gmlst typing cgmlst -s {scheme} ...[/bold] "
            "for cgMLST/wgMLST schemes."
        )
        sys.exit(1)

    if mode == "cgmlst" and scheme_type not in {"cgmlst", "wgmlst"}:
        err_console.print(
            f"[red]Error:[/red] Scheme '[cyan]{scheme}[/cyan]' is type "
            f"'[yellow]{scheme_type}[/yellow]'."
        )
        err_console.print(
            f"Use [bold]gmlst typing mlst -s {scheme} ...[/bold] for MLST schemes."
        )
        sys.exit(1)


def effective_scheme_type(mode: str, resolved_type: str | None) -> str:
    if resolved_type in {"mlst", "cgmlst", "wgmlst"}:
        return resolved_type
    return "cgmlst" if mode == "cgmlst" else "mlst"
