from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from gmlst.visual._cli_helpers import (
    emit_json_payload,
    emit_rows_by_format,
    heatmap_rows,
    matrix_rows,
)


def emit_export_payload(
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
        emit_json_payload(envelope, output=output)
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
                        field, ""
                    )
                    for field in metadata_fields
                },
                **{
                    f"target_{field}": node_meta.get(str(edge["target_label"]), {}).get(
                        field, ""
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
        emit_rows_by_format(
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
        rows = matrix_rows(labels, payload["matrix"])
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
        emit_rows_by_format(
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
        rows = heatmap_rows(labels, loci, payload["cells"])
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
        emit_rows_by_format(
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
        emit_rows_by_format(
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
    emit_rows_by_format(
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
