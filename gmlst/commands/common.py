"""Shared utilities for CLI commands."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

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

from gmlst.aligners import AVAILABLE_BACKENDS
from gmlst.database.cache import _load_blocked_schemes as _load_blocked_schemes

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

# Shared console instances
console = Console()
err_console = Console(stderr=True)
status_console = Console(stderr=True)


def _natural_sort_key(scheme_name: str) -> tuple[str, int]:
    """Extract key for natural sorting.

    Example:
        'acinetobacter_10' -> ('acinetobacter', 10)
        'klebsiella_1' -> ('klebsiella', 1)
    """
    parts = re.split(r"_(\d+)$", scheme_name)
    if len(parts) >= 2:
        # Has a numeric suffix
        return (parts[0].lower(), int(parts[1]))
    else:
        # No numeric suffix
        return (scheme_name.lower(), 0)


def render_from_format[TFormat](
    output_format: str,
    renderers: dict[str, Callable[[], TFormat]],
) -> TFormat:
    """Dispatch to the renderer registered for *output_format*.

    Raises ``ValueError`` listing the supported formats when the key is unknown.
    """
    renderer = renderers.get(output_format)
    if renderer is None:
        supported = ", ".join(sorted(renderers))
        raise ValueError(
            f"Unsupported output format '{output_format}'. Supported: {supported}"
        )
    return renderer()


def emit_output_text(output_text: str, output: Path | None) -> bool:
    """Write *output_text* to *output* (file) or stdout when *output* is None.

    Ensures a trailing newline. Returns True when written to a file,
    False when echoed to stdout.
    """
    payload = output_text if output_text.endswith("\n") else output_text + "\n"
    if output is not None:
        output.write_text(payload)
        return True
    click.echo(payload, nl=False)
    return False


def emit_output_json(data: Any, output: Path | None) -> bool:
    """Serialize *data* as indented JSON and emit via :func:`emit_output_text`."""
    return emit_output_text(json.dumps(data, indent=2), output)


def emit_versioned_json(payload: Any, output: Path | None, schema_version: str) -> bool:
    """Emit *payload* wrapped in a ``{"schema_version", "data"}`` envelope.

    Version constants live in :mod:`gmlst.schema_versions`. Returns the same
    bool semantics as :func:`emit_output_json` (True when written to a file).
    """
    return emit_output_json({"schema_version": schema_version, "data": payload}, output)


def render_delimited_rows(
    rows: list[dict[str, Any]],
    columns: list[str],
    delimiter: str,
) -> str:
    """Render rows as delimited text with a header line.

    Missing keys become empty cells and booleans are coerced to "1"/"0".
    """
    lines = [delimiter.join(columns)]
    for row in rows:
        values: list[str] = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, bool):
                values.append("1" if value else "0")
            else:
                values.append(str(value))
        lines.append(delimiter.join(values))
    return "\n".join(lines)


def emit_output_tsv(
    rows: list[dict[str, Any]],
    columns: list[str],
    output: Path | None,
) -> bool:
    """Render rows as TSV; see :func:`emit_output_text` for destination semantics."""
    return emit_output_text(render_delimited_rows(rows, columns, "\t"), output)


def emit_output_csv(
    rows: list[dict[str, Any]],
    columns: list[str],
    output: Path | None,
) -> bool:
    """Render rows as CSV; see :func:`emit_output_text` for destination semantics."""
    return emit_output_text(render_delimited_rows(rows, columns, ","), output)


def emit_output_table(
    *,
    output: Path | None,
    render_text: Callable[[], str],
    print_table: Callable[[], None],
) -> bool:
    """Emit a table: pretty-print to stdout, or write plain text to *output*.

    Returns True when written to a file, False when printed to stdout.
    """
    if output is None:
        print_table()
        return False
    output.write_text(render_text())
    return True


def make_progress() -> Progress:
    """Create the shared rich progress bar (spinner, bar, M/N, elapsed time).

    Renders on stderr so progress bars never pollute stdout data streams.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=status_console,
    )


def cache_dir_option(f):
    """Click decorator factory adding the shared ``--cache-dir`` option."""
    return click.option(
        "--cache-dir",
        type=click.Path(path_type=Path),
        help="Override cache directory.",
    )(f)


def typing_threshold_options(f):
    """Click decorator factory adding the shared typing threshold options."""
    f = click.option(
        "--minscore",
        "minscore",
        default=0.0,
        show_default=True,
        type=float,
        help=(
            "Minimum sample quality score (0-100) to report; samples below "
            "are dropped from TSV/JSON output. Scores appear in JSON output."
        ),
    )(f)
    f = click.option(
        "--min-join-overlap",
        default=10,
        show_default=True,
        type=click.IntRange(min=0),
        help="Minimum allele-coordinate overlap (bp) required to join contig "
        "fragments of a split gene into one call.",
    )(f)
    f = click.option(
        "--min-depth",
        default=10.0,
        show_default=True,
        help="Min read depth (FASTQ only).",
    )(f)
    f = click.option(
        "--min-cov",
        default=0.95,
        show_default=True,
        help="Minimum allele coverage (0-1).",
    )(f)
    f = click.option(
        "--min-id", default=95.0, show_default=True, help="Minimum percent identity."
    )(f)
    return f


def typing_output_options(f):
    """Click decorator factory adding the shared typing output options.

    Emits ``--format``, ``--output``, ``--cache-dir``, ``--force-reindex``,
    and ``--no-header`` in that help order (shared by mlst/cgmlst).
    """
    f = click.option("--no-header", is_flag=True, help="Suppress TSV header line")(f)
    f = click.option("--force-reindex", is_flag=True, help="Rebuild aligner index.")(f)
    f = cache_dir_option(f)
    f = click.option(
        "--output", "-o", type=click.Path(path_type=Path), help="Write output to file."
    )(f)
    f = click.option(
        "--format",
        "fmt",
        default="tsv",
        show_default=True,
        type=click.Choice(["tsv", "json", "pretty"]),
        help="Output format.",
    )(f)
    return f


def typing_parallel_options(f):
    """Click decorator factory adding the shared typing parallelism options."""
    f = click.option(
        "--max-workers",
        type=click.IntRange(min=1),
        default=1,
        show_default=True,
        help="Number of samples to type in parallel (mlst/cgmlst).",
    )(f)
    f = click.option(
        "--threads",
        "-t",
        default=1,
        show_default=True,
        help="Number of alignment threads (backend-dependent).",
    )(f)
    return f


def novel_data_options(f):
    """Click decorator factory adding the shared novel-data output options."""
    f = click.option(
        "--data-dir",
        "--output-dir",
        "output_dir",
        type=click.Path(path_type=Path),
        help="Directory for novel allele/profile output files (default: cwd).",
    )(f)
    f = click.option(
        "--novel-profile",
        is_flag=True,
        help="Save novel ST profiles to profiles_novel.txt (requires --novel-allele).",
    )(f)
    f = click.option(
        "--novel-allele",
        is_flag=True,
        help="Save novel allele sequences to {locus}_novel.fasta files.",
    )(f)
    return f


def backend_option(default: str):
    """Click decorator factory adding the ``--backend`` option with a custom default."""

    def decorator(f):
        return click.option(
            "--backend",
            "-b",
            default=default,
            show_default=True,
            type=click.Choice(AVAILABLE_BACKENDS, case_sensitive=False),
            help="Alignment backend to use.",
        )(f)

    return decorator


def deprecated_scheme_option(f):
    """Click decorator factory adding the hidden, deprecated ``--scheme`` option."""
    return click.option(
        "--scheme",
        "-s",
        "scheme_opt",
        hidden=True,
        help="[deprecated] Use positional argument instead.",
    )(f)
