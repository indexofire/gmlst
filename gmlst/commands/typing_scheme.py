from __future__ import annotations

import sys


def resolve_scheme_type(
    cache,
    scheme: str,
    provider: str | None,
) -> str | None:
    if provider:
        catalogs = [provider]
    else:
        from gmlst.database.providers import AVAILABLE_PROVIDERS

        catalogs = AVAILABLE_PROVIDERS + ["local"]

    for prov in catalogs:
        scheme_dicts = cache.load_catalog(prov)
        if not scheme_dicts:
            continue
        for item in scheme_dicts:
            if item.get("scheme_name") == scheme:
                stype = item.get("scheme_type")
                if isinstance(stype, str):
                    return stype.lower()
                return None
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


def detect_provider(cache, scheme: str) -> str | None:
    return cache.detect_provider(scheme)
