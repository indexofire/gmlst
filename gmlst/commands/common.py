"""Shared utilities for CLI commands."""

from __future__ import annotations

import json
import re
import sys
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

from gmlst.database.cache import _load_blocked_schemes as _load_blocked_schemes

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

# Shared console instances
console = Console()
err_console = Console(stderr=True)


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
    """Create the shared rich progress bar (spinner, bar, M/N, elapsed time)."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
    )


def cache_dir_option(f):
    """Click decorator factory adding the shared ``--cache-dir`` option."""
    return click.option(
        "--cache-dir",
        type=click.Path(path_type=Path),
        help="Override cache directory.",
    )(f)


def exit_with_error(msg: str, hint: str | None = None) -> None:
    """Print error message and exit with code 1."""
    err_console.print(f"[red]Error:[/red] {msg}")
    if hint:
        err_console.print(hint)
    sys.exit(1)


def deprecated_scheme_option(f):
    """Click decorator factory adding the hidden, deprecated ``--scheme`` option."""
    return click.option(
        "--scheme",
        "-s",
        "scheme_opt",
        hidden=True,
        help="[deprecated] Use positional argument instead.",
    )(f)
