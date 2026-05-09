from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from typing import Any

import click

from gmlst.commands.common import (
    emit_output_json,
    emit_output_text,
    render_delimited_rows,
)
from gmlst.visual.app import create_visual_app
from gmlst.visual.mst import (
    VALID_MST_METHODS,
    build_allele_heatmap_from_tsv,
    build_distance_matrix_from_tsv,
    build_locus_diff_from_tsv,
    build_mst_from_tsv,
    build_result_comparison_from_tsv,
)
from gmlst.visual.mst_shared import validate_tsv_scale

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}
TABULAR_FORMATS = click.Choice(["json", "tsv", "table"], case_sensitive=False)
EXPORT_SCHEMA_VERSION = "gmlst-visual-export-v1"


@click.group(
    "visual",
    context_settings=HELP_SETTINGS,
    short_help="Interactive visualization tools.",
)
@click.option(
    "--force-large",
    is_flag=True,
    default=False,
    help="Bypass input scale limits.",
)
@click.pass_context
def visual_group(ctx: click.Context, force_large: bool) -> None:
    """Launch interactive visualization tools for MST/profile exploration."""
    ctx.ensure_object(dict)
    _ = force_large


def _maybe_validate_tsv_scale(ctx: click.Context, tsv_text: str) -> None:
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


def _read_input_text(path: Path, *, label: str) -> str:
    try:
        return path.read_text()
    except OSError as exc:
        raise click.UsageError(f"Failed to read {label} file: {path}") from exc


def _emit_json_payload(payload: dict[str, Any], *, output: Path | None) -> None:
    try:
        wrote_file = emit_output_json(payload, output)
    except OSError as exc:
        raise click.UsageError(f"Failed to write output file: {output}") from exc
    if wrote_file and output is not None:
        click.echo(f"Results written to {output}")


def _render_simple_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
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


def _emit_rows_by_format(
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
        _emit_json_payload(payload, output=output)
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

    table_text = _render_simple_table(rows, columns)
    if summary_lines:
        table_text = "\n".join([*summary_lines, "", table_text])
    try:
        wrote_file = emit_output_text(table_text, output)
    except OSError as exc:
        raise click.UsageError(f"Failed to write output file: {output}") from exc
    if wrote_file and output is not None:
        click.echo(f"Results written to {output}")


def _matrix_rows(labels: list[str], matrix: list[list[int]]) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": row_label,
            **{label: value for label, value in zip(labels, row, strict=True)},
        }
        for row_label, row in zip(labels, matrix, strict=True)
    ]


def _heatmap_rows(
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


def _emit_export_payload(
    *,
    kind: str,
    payload: dict[str, Any],
    output: Path | None,
    output_format: str,
    schema_version: str,
    include_meta: bool,
    columns_spec: str | None,
) -> None:
    def _selected_columns(rows: list[dict[str, Any]], defaults: list[str]) -> list[str]:
        if not columns_spec:
            return defaults
        selected = [part.strip() for part in columns_spec.split(",") if part.strip()]
        if not selected:
            raise click.UsageError("--columns must include at least one column name")
        available = set(defaults)
        for row in rows:
            available.update(str(key) for key in row)
        missing = [column for column in selected if column not in available]
        if missing:
            raise click.UsageError(
                f"Unknown column(s) in --columns: {', '.join(missing)}"
            )
        return selected

    def _meta_map() -> tuple[dict[str, dict[str, Any]], list[str]]:
        if not include_meta:
            return {}, []
        metadata_fields = [str(name) for name in payload.get("metadata_fields", [])]
        node_meta = {
            str(node["label"]): dict(node.get("meta", {}))
            for node in payload.get("nodes", [])
        }
        return node_meta, metadata_fields

    normalized_format = output_format.lower()
    if normalized_format == "json":
        envelope = {
            "schema_version": schema_version,
            "kind": kind,
            "payload": payload,
        }
        _emit_json_payload(envelope, output=output)
        return

    if kind == "mst":
        node_meta, metadata_fields = _meta_map()
        rows = [
            {
                "source_label": edge["source_label"],
                "target_label": edge["target_label"],
                "weight": edge["weight"],
                "asymmetric_weight": edge["asymmetric_weight"],
                **{
                    f"source_{field}": node_meta.get(str(edge["source_label"]), {}).get(
                        field,
                        "",
                    )
                    for field in metadata_fields
                },
                **{
                    f"target_{field}": node_meta.get(str(edge["target_label"]), {}).get(
                        field,
                        "",
                    )
                    for field in metadata_fields
                },
            }
            for edge in payload["edges"]
        ]
        columns = ["source_label", "target_label", "weight", "asymmetric_weight"]
        if include_meta:
            columns.extend([f"source_{field}" for field in metadata_fields])
            columns.extend([f"target_{field}" for field in metadata_fields])
        _emit_rows_by_format(
            rows=rows,
            columns=_selected_columns(rows, columns),
            output=output,
            output_format=output_format,
            summary_lines=[
                f"schema_version: {schema_version}",
                f"kind: {kind}",
                f"nodes: {len(payload['nodes'])}",
                f"edges: {len(payload['edges'])}",
                f"aggregate_profiles: {payload['aggregate_profiles']}",
            ],
        )
        return

    if kind == "matrix":
        labels = payload["labels"]
        rows = _matrix_rows(labels, payload["matrix"])
        node_meta, metadata_fields = _meta_map()
        if include_meta:
            for row in rows:
                sample_id = str(row["sample_id"])
                row.update(
                    {
                        field: node_meta.get(sample_id, {}).get(field, "")
                        for field in metadata_fields
                    }
                )
        columns = ["sample_id", *labels]
        if include_meta:
            columns.extend(metadata_fields)
        _emit_rows_by_format(
            rows=rows,
            columns=_selected_columns(rows, columns),
            output=output,
            output_format=output_format,
            summary_lines=[
                f"schema_version: {schema_version}",
                f"kind: {kind}",
                f"samples: {len(labels)}",
                f"aggregate_profiles: {payload['aggregate_profiles']}",
            ],
        )
        return

    if kind == "heatmap":
        labels = payload["labels"]
        loci = payload["loci"]
        rows = _heatmap_rows(labels, loci, payload["cells"])
        node_meta, metadata_fields = _meta_map()
        if include_meta:
            for row in rows:
                sample_id = str(row["sample_id"])
                row.update(
                    {
                        field: node_meta.get(sample_id, {}).get(field, "")
                        for field in metadata_fields
                    }
                )
        columns = ["sample_id", *loci]
        if include_meta:
            columns.extend(metadata_fields)
        _emit_rows_by_format(
            rows=rows,
            columns=_selected_columns(rows, columns),
            output=output,
            output_format=output_format,
            summary_lines=[
                f"schema_version: {schema_version}",
                f"kind: {kind}",
                f"samples: {len(labels)}",
                f"loci: {len(loci)}",
                f"aggregate_profiles: {payload['aggregate_profiles']}",
            ],
        )
        return

    if kind == "compare":
        summary = payload["summary"]
        rows = payload["rows"]
        columns = [
            "sample_id",
            "left_st",
            "right_st",
            "status",
            "differing_loci_count",
        ]
        _emit_rows_by_format(
            rows=rows,
            columns=_selected_columns(rows, columns),
            output=output,
            output_format=output_format,
            summary_lines=[
                f"schema_version: {schema_version}",
                f"kind: {kind}",
                f"matched_samples: {summary['matched_samples']}",
                f"same_st: {summary['same_st']}",
                f"different_st: {summary['different_st']}",
                (
                    "samples_with_locus_differences: "
                    f"{summary['samples_with_locus_differences']}"
                ),
                f"left_only: {summary['left_only']}",
                f"right_only: {summary['right_only']}",
            ],
        )
        return

    rows = payload["differences"]
    _emit_rows_by_format(
        rows=rows,
        columns=_selected_columns(rows, ["locus", "left", "right", "type"]),
        output=output,
        output_format=output_format,
        summary_lines=[
            f"schema_version: {schema_version}",
            f"kind: {kind}",
            f"left_label: {payload['left_label']}",
            f"right_label: {payload['right_label']}",
            f"distance: {payload['distance']}",
        ],
    )


@visual_group.command(
    "web",
    context_settings=HELP_SETTINGS,
    short_help="Start the local MST web app.",
)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=click.IntRange(1, 65535), default=8787, show_default=True)
@click.option("--open-browser", is_flag=True, help="Open browser automatically.")
def cmd_visual_web(host: str, port: int, open_browser: bool) -> None:
    """Run the local web UI for Grapetree-style MST visualization."""
    app = create_visual_app(title="gmlst visual web")
    click.echo(f"Serving MST web app on http://{host}:{port}")
    if open_browser:
        threading.Timer(0.2, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    app.run(host=host, port=port, threaded=True, use_reloader=False)


@visual_group.command(
    "mst",
    context_settings=HELP_SETTINGS,
    short_help="Build MST data from profile TSV/CSV.",
)
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Profile TSV/CSV input file.",
)
@click.option(
    "--metadata",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional metadata TSV/CSV input file.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Write output JSON to file.",
)
@click.option(
    "--format",
    "output_format",
    type=TABULAR_FORMATS,
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--include-missing/--no-include-missing",
    default=False,
    show_default=True,
    help="Count asymmetric missing-token mismatches.",
)
@click.option(
    "--aggregate-profiles/--no-aggregate-profiles",
    default=True,
    show_default=True,
    help="Collapse duplicate profiles before tree building.",
)
@click.option(
    "--method",
    type=click.Choice(VALID_MST_METHODS, case_sensitive=False),
    default="edmonds",
    show_default=True,
    help="MST algorithm method.",
)
@click.pass_context
def cmd_visual_mst(
    ctx: click.Context,
    input_path: Path,
    metadata: Path | None,
    output_path: Path | None,
    output_format: str,
    include_missing: bool,
    aggregate_profiles: bool,
    method: str,
) -> None:
    """Generate MST node/edge payload without starting the web server."""
    tsv_text = _read_input_text(input_path, label="input")
    _maybe_validate_tsv_scale(ctx, tsv_text)
    metadata_text = (
        _read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    nodes, edges, metadata_fields = build_mst_from_tsv(
        tsv_text,
        include_missing=include_missing,
        aggregate_profiles=aggregate_profiles,
        metadata_text=metadata_text,
        method=method,
    )
    if output_format.lower() == "json":
        _emit_json_payload(
            {
                "nodes": nodes,
                "edges": edges,
                "metadata_fields": metadata_fields,
                "aggregate_profiles": aggregate_profiles,
            },
            output=output_path,
        )
        return

    rows = [
        {
            "source_label": edge["source_label"],
            "target_label": edge["target_label"],
            "weight": edge["weight"],
            "asymmetric_weight": edge["asymmetric_weight"],
        }
        for edge in edges
    ]
    _emit_rows_by_format(
        rows=rows,
        columns=["source_label", "target_label", "weight", "asymmetric_weight"],
        output=output_path,
        output_format=output_format,
        summary_lines=[
            f"nodes: {len(nodes)}",
            f"edges: {len(edges)}",
            f"aggregate_profiles: {aggregate_profiles}",
        ],
    )


@visual_group.command(
    "matrix",
    context_settings=HELP_SETTINGS,
    short_help="Build pairwise distance matrix from profile TSV/CSV.",
)
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Profile TSV/CSV input file.",
)
@click.option(
    "--metadata",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional metadata TSV/CSV input file.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Write output JSON to file.",
)
@click.option(
    "--format",
    "output_format",
    type=TABULAR_FORMATS,
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--include-missing/--no-include-missing",
    default=False,
    show_default=True,
    help="Count asymmetric missing-token mismatches.",
)
@click.option(
    "--aggregate-profiles/--no-aggregate-profiles",
    default=True,
    show_default=True,
    help="Collapse duplicate profiles before distance calculation.",
)
@click.pass_context
def cmd_visual_matrix(
    ctx: click.Context,
    input_path: Path,
    metadata: Path | None,
    output_path: Path | None,
    output_format: str,
    include_missing: bool,
    aggregate_profiles: bool,
) -> None:
    """Generate a full pairwise allele distance matrix payload."""
    tsv_text = _read_input_text(input_path, label="input")
    _maybe_validate_tsv_scale(ctx, tsv_text)
    metadata_text = (
        _read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    labels, matrix, nodes, metadata_fields = build_distance_matrix_from_tsv(
        tsv_text,
        include_missing=include_missing,
        aggregate_profiles=aggregate_profiles,
        metadata_text=metadata_text,
    )
    if output_format.lower() == "json":
        _emit_json_payload(
            {
                "labels": labels,
                "matrix": matrix,
                "nodes": nodes,
                "metadata_fields": metadata_fields,
                "aggregate_profiles": aggregate_profiles,
            },
            output=output_path,
        )
        return

    rows = _matrix_rows(labels, matrix)
    _emit_rows_by_format(
        rows=rows,
        columns=["sample_id", *labels],
        output=output_path,
        output_format=output_format,
        summary_lines=[
            f"samples: {len(labels)}",
            f"aggregate_profiles: {aggregate_profiles}",
        ],
    )


@visual_group.command(
    "heatmap",
    context_settings=HELP_SETTINGS,
    short_help="Build allele heatmap payload from profile TSV/CSV.",
)
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Profile TSV/CSV input file.",
)
@click.option(
    "--metadata",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional metadata TSV/CSV input file.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Write output JSON to file.",
)
@click.option(
    "--format",
    "output_format",
    type=TABULAR_FORMATS,
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--aggregate-profiles/--no-aggregate-profiles",
    default=True,
    show_default=True,
    help="Collapse duplicate profiles before heatmap generation.",
)
@click.pass_context
def cmd_visual_heatmap(
    ctx: click.Context,
    input_path: Path,
    metadata: Path | None,
    output_path: Path | None,
    output_format: str,
    aggregate_profiles: bool,
) -> None:
    """Generate allele heatmap rows/cells without web startup."""
    tsv_text = _read_input_text(input_path, label="input")
    _maybe_validate_tsv_scale(ctx, tsv_text)
    metadata_text = (
        _read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    labels, loci, cells, nodes, metadata_fields = build_allele_heatmap_from_tsv(
        tsv_text,
        aggregate_profiles=aggregate_profiles,
        metadata_text=metadata_text,
    )
    if output_format.lower() == "json":
        _emit_json_payload(
            {
                "labels": labels,
                "loci": loci,
                "cells": cells,
                "nodes": nodes,
                "metadata_fields": metadata_fields,
                "aggregate_profiles": aggregate_profiles,
            },
            output=output_path,
        )
        return

    rows = _heatmap_rows(labels, loci, cells)
    _emit_rows_by_format(
        rows=rows,
        columns=["sample_id", *loci],
        output=output_path,
        output_format=output_format,
        summary_lines=[
            f"samples: {len(labels)}",
            f"loci: {len(loci)}",
            f"aggregate_profiles: {aggregate_profiles}",
        ],
    )


@visual_group.command(
    "compare",
    context_settings=HELP_SETTINGS,
    short_help="Compare two typing result TSV/CSV files.",
)
@click.option(
    "--left",
    "left_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Left typing result TSV/CSV file.",
)
@click.option(
    "--right",
    "right_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Right typing result TSV/CSV file.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Write output JSON to file.",
)
@click.option(
    "--format",
    "output_format",
    type=TABULAR_FORMATS,
    default="json",
    show_default=True,
    help="Output format.",
)
@click.pass_context
def cmd_visual_compare(
    ctx: click.Context,
    left_path: Path,
    right_path: Path,
    output_path: Path | None,
    output_format: str,
) -> None:
    """Compare ST and locus-level differences between two result sets."""
    left_tsv = _read_input_text(left_path, label="left")
    right_tsv = _read_input_text(right_path, label="right")
    _maybe_validate_tsv_scale(ctx, left_tsv)
    _maybe_validate_tsv_scale(ctx, right_tsv)
    comparison = build_result_comparison_from_tsv(left_tsv, right_tsv)
    if output_format.lower() == "json":
        _emit_json_payload(comparison, output=output_path)
        return

    summary = comparison["summary"]
    summary_lines = [
        f"matched_samples: {summary['matched_samples']}",
        f"same_st: {summary['same_st']}",
        f"different_st: {summary['different_st']}",
        f"samples_with_locus_differences: {summary['samples_with_locus_differences']}",
        f"left_only: {summary['left_only']}",
        f"right_only: {summary['right_only']}",
    ]
    _emit_rows_by_format(
        rows=comparison["rows"],
        columns=["sample_id", "left_st", "right_st", "status", "differing_loci_count"],
        output=output_path,
        output_format=output_format,
        summary_lines=summary_lines,
    )


@visual_group.command(
    "locus-diff",
    context_settings=HELP_SETTINGS,
    short_help="Compare locus-level differences between two samples.",
)
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Profile TSV/CSV input file.",
)
@click.option(
    "--metadata",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional metadata TSV/CSV input file.",
)
@click.option("--left-label", required=True, help="Left sample label.")
@click.option("--right-label", required=True, help="Right sample label.")
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Write output JSON to file.",
)
@click.option(
    "--format",
    "output_format",
    type=TABULAR_FORMATS,
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--include-missing/--no-include-missing",
    default=False,
    show_default=True,
    help="Count asymmetric missing-token mismatches.",
)
@click.pass_context
def cmd_visual_locus_diff(
    ctx: click.Context,
    input_path: Path,
    metadata: Path | None,
    left_label: str,
    right_label: str,
    output_path: Path | None,
    output_format: str,
    include_missing: bool,
) -> None:
    """Generate pairwise locus diff payload for two sample labels."""
    tsv_text = _read_input_text(input_path, label="input")
    _maybe_validate_tsv_scale(ctx, tsv_text)
    metadata_text = (
        _read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    diff = build_locus_diff_from_tsv(
        tsv_text,
        left_label=left_label,
        right_label=right_label,
        include_missing=include_missing,
        metadata_text=metadata_text,
    )
    if output_format.lower() == "json":
        _emit_json_payload(diff, output=output_path)
        return

    _emit_rows_by_format(
        rows=diff["differences"],
        columns=["locus", "left", "right", "type"],
        output=output_path,
        output_format=output_format,
        summary_lines=[
            f"left_label: {diff['left_label']}",
            f"right_label: {diff['right_label']}",
            f"distance: {diff['distance']}",
        ],
    )


@visual_group.command(
    "export",
    context_settings=HELP_SETTINGS,
    short_help="Export visual payload in one command.",
)
@click.option(
    "--kind",
    type=click.Choice(["mst", "matrix", "heatmap", "compare", "locus-diff"]),
    required=True,
    help="Payload type to export.",
)
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Profile TSV/CSV input file.",
)
@click.option(
    "--metadata",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional metadata TSV/CSV input file.",
)
@click.option(
    "--left",
    "left_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Left typing result TSV/CSV file (compare kind).",
)
@click.option(
    "--right",
    "right_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Right typing result TSV/CSV file (compare kind).",
)
@click.option("--left-label", help="Left sample label (locus-diff kind).")
@click.option("--right-label", help="Right sample label (locus-diff kind).")
@click.option(
    "--include-missing/--no-include-missing",
    default=False,
    show_default=True,
    help="Count asymmetric missing-token mismatches.",
)
@click.option(
    "--aggregate-profiles/--no-aggregate-profiles",
    default=True,
    show_default=True,
    help="Collapse duplicate profiles where applicable.",
)
@click.option(
    "--method",
    type=click.Choice(VALID_MST_METHODS, case_sensitive=False),
    default="edmonds",
    show_default=True,
    help="MST algorithm method for kind=mst.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Write output to file.",
)
@click.option(
    "--format",
    "output_format",
    type=TABULAR_FORMATS,
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--schema-version",
    default=EXPORT_SCHEMA_VERSION,
    show_default=True,
    help="Schema version to embed in export output.",
)
@click.option(
    "--include-meta/--no-include-meta",
    default=False,
    show_default=True,
    help="Include metadata columns in tabular exports when available.",
)
@click.option(
    "--columns",
    "columns_spec",
    help="Comma-separated column list for tabular export formats.",
)
@click.pass_context
def cmd_visual_export(
    ctx: click.Context,
    kind: str,
    input_path: Path | None,
    metadata: Path | None,
    left_path: Path | None,
    right_path: Path | None,
    left_label: str | None,
    right_label: str | None,
    include_missing: bool,
    aggregate_profiles: bool,
    method: str,
    output_path: Path | None,
    output_format: str,
    schema_version: str,
    include_meta: bool,
    columns_spec: str | None,
) -> None:
    """Export visual payload without choosing a specific generation subcommand."""
    metadata_text = (
        _read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    payload: dict[str, Any]

    if kind == "compare":
        if left_path is None or right_path is None:
            raise click.UsageError("--left and --right are required for kind=compare")
        left_tsv = _read_input_text(left_path, label="left")
        right_tsv = _read_input_text(right_path, label="right")
        _maybe_validate_tsv_scale(ctx, left_tsv)
        _maybe_validate_tsv_scale(ctx, right_tsv)
        payload = build_result_comparison_from_tsv(left_tsv, right_tsv)
    else:
        if input_path is None:
            raise click.UsageError("--input is required for this export kind")
        tsv_text = _read_input_text(input_path, label="input")
        _maybe_validate_tsv_scale(ctx, tsv_text)
        if kind == "mst":
            nodes, edges, metadata_fields = build_mst_from_tsv(
                tsv_text,
                include_missing=include_missing,
                aggregate_profiles=aggregate_profiles,
                metadata_text=metadata_text,
                method=method,
            )
            payload = {
                "nodes": nodes,
                "edges": edges,
                "metadata_fields": metadata_fields,
                "aggregate_profiles": aggregate_profiles,
            }
        elif kind == "matrix":
            labels, matrix, nodes, metadata_fields = build_distance_matrix_from_tsv(
                tsv_text,
                include_missing=include_missing,
                aggregate_profiles=aggregate_profiles,
                metadata_text=metadata_text,
            )
            payload = {
                "labels": labels,
                "matrix": matrix,
                "nodes": nodes,
                "metadata_fields": metadata_fields,
                "aggregate_profiles": aggregate_profiles,
            }
        elif kind == "heatmap":
            labels, loci, cells, nodes, metadata_fields = build_allele_heatmap_from_tsv(
                tsv_text,
                aggregate_profiles=aggregate_profiles,
                metadata_text=metadata_text,
            )
            payload = {
                "labels": labels,
                "loci": loci,
                "cells": cells,
                "nodes": nodes,
                "metadata_fields": metadata_fields,
                "aggregate_profiles": aggregate_profiles,
            }
        else:
            if not left_label or not right_label:
                raise click.UsageError(
                    "--left-label and --right-label are required for kind=locus-diff"
                )
            payload = build_locus_diff_from_tsv(
                tsv_text,
                left_label=left_label,
                right_label=right_label,
                include_missing=include_missing,
                metadata_text=metadata_text,
            )

    _emit_export_payload(
        kind=kind,
        payload=payload,
        output=output_path,
        output_format=output_format,
        schema_version=schema_version,
        include_meta=include_meta,
        columns_spec=columns_spec,
    )
