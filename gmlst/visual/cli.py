from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from typing import Any

import click

from gmlst.visual._cli_export import emit_export_payload
from gmlst.visual._cli_helpers import (
    emit_json_payload,
    emit_rows_by_format,
    heatmap_rows,
    matrix_rows,
    maybe_validate_tsv_scale,
    read_input_text,
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
    tsv_text = read_input_text(input_path, label="input")
    maybe_validate_tsv_scale(ctx, tsv_text)
    metadata_text = (
        read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    nodes, edges, metadata_fields = build_mst_from_tsv(
        tsv_text,
        include_missing=include_missing,
        aggregate_profiles=aggregate_profiles,
        metadata_text=metadata_text,
        method=method,
    )
    if output_format.lower() == "json":
        emit_json_payload(
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
    emit_rows_by_format(
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
    tsv_text = read_input_text(input_path, label="input")
    maybe_validate_tsv_scale(ctx, tsv_text)
    metadata_text = (
        read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    labels, matrix, nodes, metadata_fields = build_distance_matrix_from_tsv(
        tsv_text,
        include_missing=include_missing,
        aggregate_profiles=aggregate_profiles,
        metadata_text=metadata_text,
    )
    if output_format.lower() == "json":
        emit_json_payload(
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

    rows = matrix_rows(labels, matrix)
    emit_rows_by_format(
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
    tsv_text = read_input_text(input_path, label="input")
    maybe_validate_tsv_scale(ctx, tsv_text)
    metadata_text = (
        read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    labels, loci, cells, nodes, metadata_fields = build_allele_heatmap_from_tsv(
        tsv_text,
        aggregate_profiles=aggregate_profiles,
        metadata_text=metadata_text,
    )
    if output_format.lower() == "json":
        emit_json_payload(
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

    rows = heatmap_rows(labels, loci, cells)
    emit_rows_by_format(
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
    left_tsv = read_input_text(left_path, label="left")
    right_tsv = read_input_text(right_path, label="right")
    maybe_validate_tsv_scale(ctx, left_tsv)
    maybe_validate_tsv_scale(ctx, right_tsv)
    comparison = build_result_comparison_from_tsv(left_tsv, right_tsv)
    if output_format.lower() == "json":
        emit_json_payload(comparison, output=output_path)
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
    emit_rows_by_format(
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
    tsv_text = read_input_text(input_path, label="input")
    maybe_validate_tsv_scale(ctx, tsv_text)
    metadata_text = (
        read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    diff = build_locus_diff_from_tsv(
        tsv_text,
        left_label=left_label,
        right_label=right_label,
        include_missing=include_missing,
        metadata_text=metadata_text,
    )
    if output_format.lower() == "json":
        emit_json_payload(diff, output=output_path)
        return

    emit_rows_by_format(
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
        read_input_text(metadata, label="metadata") if metadata is not None else None
    )
    payload: dict[str, Any]

    if kind == "compare":
        if left_path is None or right_path is None:
            raise click.UsageError("--left and --right are required for kind=compare")
        left_tsv = read_input_text(left_path, label="left")
        right_tsv = read_input_text(right_path, label="right")
        maybe_validate_tsv_scale(ctx, left_tsv)
        maybe_validate_tsv_scale(ctx, right_tsv)
        payload = build_result_comparison_from_tsv(left_tsv, right_tsv)
    else:
        if input_path is None:
            raise click.UsageError("--input is required for this export kind")
        tsv_text = read_input_text(input_path, label="input")
        maybe_validate_tsv_scale(ctx, tsv_text)
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

    emit_export_payload(
        kind=kind,
        payload=payload,
        output=output_path,
        output_format=output_format,
        schema_version=schema_version,
        include_meta=include_meta,
        columns_spec=columns_spec,
    )
