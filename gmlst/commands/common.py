"""Shared utilities for CLI commands."""

from __future__ import annotations

import importlib.resources as pkg_resources
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console

# Shared console instances
console = Console()
err_console = Console(stderr=True)


def _load_blocked_schemes() -> dict[str, list[str]]:
    """Load blocked schemes from data/blocked_schemes.json."""
    try:
        blocked_file = pkg_resources.files("gmlst") / "data" / "blocked_schemes.json"
        if blocked_file.exists():
            with open(blocked_file) as f:
                data = json.load(f)
                return {k: v for k, v in data.items() if not k.startswith("_")}
    except (OSError, json.JSONDecodeError) as exc:
        err_console.print(
            f"[yellow]Warning:[/yellow] Failed to load blocked schemes: {exc}"
        )
    return {}


class _DictSchemeInfo:
    """Wrapper to access dict keys as attributes."""

    def __init__(self, data: dict) -> None:
        self._data = data
        # Ensure 'extra' key exists for consistency with SchemeInfo
        if "extra" not in self._data:
            self._data["extra"] = {}

    def __getattr__(self, name: str):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def get(self, key: str, default=None):
        return self._data.get(key, default)


def _natural_sort_key(scheme_name: str):
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
    renderer = renderers.get(output_format)
    if renderer is None:
        supported = ", ".join(sorted(renderers))
        raise ValueError(
            f"Unsupported output format '{output_format}'. Supported: {supported}"
        )
    return renderer()


def emit_output_text(output_text: str, output: Path | None) -> bool:
    payload = output_text if output_text.endswith("\n") else output_text + "\n"
    if output is not None:
        output.write_text(payload)
        return True
    print(payload, end="")
    return False


def emit_output_json(data: Any, output: Path | None) -> bool:
    return emit_output_text(json.dumps(data, indent=2), output)


def render_delimited_rows(
    rows: list[dict[str, Any]],
    columns: list[str],
    delimiter: str,
) -> str:
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
    return emit_output_text(render_delimited_rows(rows, columns, "\t"), output)


def emit_output_csv(
    rows: list[dict[str, Any]],
    columns: list[str],
    output: Path | None,
) -> bool:
    return emit_output_text(render_delimited_rows(rows, columns, ","), output)


def emit_output_table(
    *,
    output: Path | None,
    render_text: Callable[[], str],
    print_table: Callable[[], None],
) -> bool:
    if output is None:
        print_table()
        return False
    output.write_text(render_text())
    return True
