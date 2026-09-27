"""Unattended mixed-species typing runner behind ``--guess``."""

from __future__ import annotations

from pathlib import Path

from gmlst.commands.common import err_console, status_console
from gmlst.commands.typing_options import TypingOptions
from gmlst.commands.typing_output import emit_final_typing_output
from gmlst.core import species_id


def _run_guess_typing(
    *,
    mode: str,
    samples: tuple[Path, ...],
    backend: str,
    cgmlst_mode: str,
    min_id: float,
    min_cov: float,
    min_depth: float,
    min_join_overlap: int,
    minscore: float,
    fmt: str,
    output: Path | None,
    cache_dir: Path | None,
    force_reindex: bool,
    no_header: bool,
    threads: int,
    max_workers: int,
    count_same_copy: bool,
    quiet: bool,
    detail: bool,
) -> int:
    """Type a mixed-species batch unattended (--guess).

    Detects each assembly's species, picks one scheme per organism
    (preference list → lone cached candidate → natural order), downloads
    missing schemes without asking, and runs the typing engine once per
    scheme group. Skipped samples are reported on stderr; the exit code
    is 0 when at least one sample typed, 1 otherwise.
    """
    # Resolved through gmlst.commands.typing at call time: that module
    # imports this one, and tests patch run_typing/DatabaseCache there.
    from gmlst.commands import typing as typing_cmd
    from gmlst.commands.scheme_common import build_fingerprints_with_progress
    from gmlst.commands.typing_guess import resolve_guess_routes
    from gmlst.commands.typing_output import (
        announce_stream_output_written,
        close_stream_output,
        open_stream_output,
        stream_header_if_needed,
        stream_write,
    )
    from gmlst.commands.typing_species import _scheme_types_for_mode
    from gmlst.database.scheme_prefs import load_scheme_preferences

    cache = typing_cmd.DatabaseCache(cache_dir)
    fingerprints_file = species_id.fingerprints_path(cache)
    if fingerprints_file.exists():
        payload = species_id.load_fingerprints(fingerprints_file)
    else:
        bundled = species_id.bundled_fingerprints_path()
        if bundled is not None:
            payload = species_id.load_fingerprints(bundled)
        else:
            status_console.print(
                "[yellow]guess:[/yellow] building fingerprint database…"
            )
            payload, _counts = build_fingerprints_with_progress(cache)
            species_id.save_fingerprints(payload, fingerprints_file)

    type_set, _type_label = _scheme_types_for_mode(mode)
    plan = resolve_guess_routes(
        samples,
        type_set=type_set,
        cache=cache,
        fingerprints=payload,
        preferences=load_scheme_preferences(),
    )

    for sample, reason in plan.skipped:
        err_console.print(f"[yellow]skip:[/yellow] {sample.name}: {reason}")

    if not plan.routes:
        err_console.print("[red]Error:[/red] no samples resolved to a scheme.")
        return 1

    options = TypingOptions(
        mode=mode,
        backend=backend,
        cgmlst_mode=cgmlst_mode,
        min_id=min_id,
        min_cov=min_cov,
        min_depth=min_depth,
        min_join_overlap=min_join_overlap,
        minscore=minscore,
        fmt=fmt,
        cache_dir=cache_dir,
        force_reindex=force_reindex,
        no_header=no_header,
        threads=threads,
        max_workers=max_workers,
        count_same_copy=count_same_copy,
        quiet=quiet,
        detail=detail,
    )

    results_by_scheme: dict[str, list] = {}
    route_order: list[str] = []
    for route in plan.routes:
        status_console.print(f"[guess] {route.scheme}: {len(route.samples)} sample(s)")
        sink: list = []
        options.run_scheme(
            samples=tuple(route.samples),
            scheme=route.scheme,
            provider=route.provider,
            result_sink=sink,
        )
        results_by_scheme[route.scheme] = sink
        route_order.append(route.scheme)

    typed = sum(len(rows) for rows in results_by_scheme.values())
    stream_file = open_stream_output(fmt=fmt, output=output)
    try:
        if fmt == "json":
            emit_final_typing_output(
                results=[
                    r for route in plan.routes for r in results_by_scheme[route.scheme]
                ],
                fmt=fmt,
                output=output,
                emit_output_json_fn=typing_cmd._emit_typing_results_json,
            )
        elif fmt in {"tsv", "pretty"}:
            for route in plan.routes:
                scheme_obj = cache.ensure_scheme(route.scheme, provider=route.provider)
                scheme = route.scheme
                if fmt == "tsv":
                    stream_header_if_needed(
                        fmt=fmt,
                        no_header=no_header,
                        loci=scheme_obj.loci,
                        stream_file=stream_file,
                    )
                for result in results_by_scheme[scheme]:
                    if fmt == "pretty":
                        st_label = typing_cmd._format_st_for_tsv(result)
                        stream_write(
                            f"{result.sample_id}: ST={st_label}",
                            stream_file=stream_file,
                        )
                    else:
                        stream_write(
                            typing_cmd._format_tsv_row(
                                result,
                                scheme_obj.loci,
                                count_same_copy,
                                call_policy="default",
                                detail=detail,
                            ),
                            stream_file=stream_file,
                        )
            announce_stream_output_written(output=output)
    finally:
        close_stream_output(stream_file)

    status_console.print(
        f"[guess] typed {typed} sample(s) across {len(route_order)} scheme(s); "
        f"skipped {len(plan.skipped)}"
    )
    return 0 if typed > 0 else 1
