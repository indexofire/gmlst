from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from gmlst.commands.common import (
    emit_output_json,
    emit_output_text,
    render_delimited_rows,
)
from gmlst.visual.mst_shared import validate_tsv_scale


def maybe_validate_tsv_scale(ctx: click.Context, tsv_text: str) -> None:
    if ctx.parent is not None and ctx.parent.params.get("force_large"):
        click.echo(
            "Warning: bypassing TSV scale limits because --force-large is active.",
            err=True,
        )
        return
    try:
        validate_tsv_scale(tsv_text)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc


def read_input_text(path: Path, *, label: str) -> str:
    try:
        return path.read_text()
    except OSError as exc:
        raise click.UsageError(f"Failed to read {label} file: {path}") from exc


def emit_json_payload(payload: dict[str, Any], *, output: Path | None) -> None:
    try:
        wrote_file = emit_output_json(payload, output)
    except OSError as exc:
        raise click.UsageError(f"Failed to write output file: {output}") from exc
    if wrote_file and output is not None:
        click.echo(f"Results written to {output}")


def render_simple_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "(no rows)"
    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(str(row.get(column, ""))))

    def _line(values: list[str]) -> str:
        return " | ".join(
            value.ljust(widths[column])
            for value, column in zip(values, columns, strict=True)
        )

    header = _line(columns)
    sep = "-+-".join("-" * widths[column] for column in columns)
    body = [_line([str(row.get(column, "")) for column in columns]) for row in rows]
    return "\n".join([header, sep, *body])


def emit_rows_by_format(
    *,
    rows: list[dict[str, Any]],
    columns: list[str],
    output: Path | None,
    output_format: str,
    summary_lines: list[str] | None = None,
) -> None:
    normalized_format = output_format.lower()
    if normalized_format == "json":
        payload: dict[str, Any] = {"rows": rows}
        if summary_lines:
            payload["summary"] = summary_lines
        emit_json_payload(payload, output=output)
        return

    if normalized_format == "tsv":
        tsv_payload = render_delimited_rows(rows, columns, "\t")
        try:
            wrote_file = emit_output_text(tsv_payload, output)
        except OSError as exc:
            raise click.UsageError(f"Failed to write output file: {output}") from exc
        if wrote_file and output is not None:
            click.echo(f"Results written to {output}")
        return

    table_text = render_simple_table(rows, columns)
    if summary_lines:
        table_text = "\n".join([*summary_lines, "", table_text])
    try:
        wrote_file = emit_output_text(table_text, output)
    except OSError as exc:
        raise click.UsageError(f"Failed to write output file: {output}") from exc
    if wrote_file and output is not None:
        click.echo(f"Results written to {output}")


def matrix_rows(labels: list[str], matrix: list[list[int]]) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": row_label,
            **{label: value for label, value in zip(labels, row, strict=True)},
        }
        for row_label, row in zip(labels, matrix, strict=True)
    ]


def heatmap_rows(
    labels: list[str],
    loci: list[str],
    cells: list[list[dict[str, str]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, row_cells in zip(labels, cells, strict=True):
        row = {"sample_id": label}
        for cell_index, cell in enumerate(row_cells):
            row[str(loci[cell_index])] = str(cell["value"])
        rows.append(row)
    return rows
