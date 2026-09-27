"""JSON API routes (/api/*) for the visualization app, as a Flask Blueprint.

Errors: 400 for invalid input (ValueError), 500 with a generic message on
internal failure (full traceback goes to the app logger only).
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify

from gmlst.visual._api_helpers import (
    EXPORT_SCHEMA_VERSION,
    _build_table_rows,
    _choose_root_id,
    _cluster_nodes,
    _cluster_nodes_by_matrix,
    _parse_bool,
    _parse_non_negative_int,
    _parse_text,
    _require_payload_dict,
    _suggest_color_fields,
)
from gmlst.visual.mst import (
    VALID_MST_METHODS,
    build_allele_heatmap_from_tsv,
    build_distance_matrix_from_tsv,
    build_locus_diff_from_tsv,
    build_mst_from_tsv,
    build_result_comparison_from_tsv,
)
from gmlst.visual.mst_shared import validate_tsv_scale

api_bp = Blueprint("api", __name__, url_prefix="")


@api_bp.post("/api/mst")
def api_mst() -> tuple[Any, int]:
    """POST ``{tsv, metadata_tsv?, method?, include_missing?,
    aggregate_profiles?, cluster_threshold?}``.

    Builds the MST and responds with nodes, edges, table rows, cluster
    summary, layout hints (root id), and suggested color fields.
    Errors: 400 for invalid input, 500 on internal failure.
    """
    try:
        payload = _require_payload_dict()
        tsv_text = _parse_text(payload, "tsv")
        validate_tsv_scale(tsv_text)
        metadata_text = _parse_text(payload, "metadata_tsv")
        if metadata_text:
            validate_tsv_scale(metadata_text)
        method = _parse_text(payload, "method") or "grapetree_classic"
        include_missing = _parse_bool(payload, "include_missing", default=False)
        aggregate_profiles = _parse_bool(
            payload,
            "aggregate_profiles",
            default=True,
        )
        if method not in VALID_MST_METHODS:
            raise ValueError(
                f"Unknown MST method: {method!r}. Choose from {VALID_MST_METHODS}"
            )
        cluster_threshold = _parse_non_negative_int(
            payload,
            "cluster_threshold",
            default=1,
        )
        nodes, edges, metadata_fields = build_mst_from_tsv(
            tsv_text,
            include_missing=include_missing,
            aggregate_profiles=aggregate_profiles,
            metadata_text=metadata_text,
            method=method,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("MST generation failed", exc_info=exc)
        return jsonify({"error": "MST generation failed"}), 500

    nodes, cluster_summary = _cluster_nodes(
        nodes,
        edges,
        threshold=cluster_threshold,
    )
    sample_count = sum(int(node.get("member_count", 1)) for node in nodes)
    root_id = _choose_root_id(nodes, edges)
    suggested_color_fields, default_color_field = _suggest_color_fields(
        nodes,
        metadata_fields,
    )

    return (
        jsonify(
            {
                "nodes": nodes,
                "edges": edges,
                "table_rows": _build_table_rows(nodes),
                "cluster_summary": cluster_summary,
                "metadata_fields": metadata_fields,
                "sample_count": sample_count,
                "node_count": len(nodes),
                "edge_count": len(edges),
                "aggregate_profiles": aggregate_profiles,
                "layout": {
                    "root_id": root_id,
                    "mode": "cluster-aware-tree",
                    "node_size_metric": "member_count",
                },
                "export": {
                    "schema_version": EXPORT_SCHEMA_VERSION,
                    "formats": ["graph-json", "session-json"],
                },
                "suggested_color_fields": suggested_color_fields,
                "default_color_field": default_color_field,
            }
        ),
        200,
    )


@api_bp.post("/api/distance-matrix")
def api_distance_matrix() -> tuple[Any, int]:
    """POST ``{tsv, metadata_tsv?, include_missing?,
    aggregate_profiles?, cluster_threshold?}``.

    Responds with ``{labels, matrix, table_rows, cluster_summary,
    metadata_fields, export}``; error semantics match /api/mst.
    """
    try:
        payload = _require_payload_dict()
        tsv_text = _parse_text(payload, "tsv")
        validate_tsv_scale(tsv_text)
        metadata_text = _parse_text(payload, "metadata_tsv")
        if metadata_text:
            validate_tsv_scale(metadata_text)
        include_missing = _parse_bool(payload, "include_missing", default=False)
        aggregate_profiles = _parse_bool(
            payload,
            "aggregate_profiles",
            default=True,
        )
        cluster_threshold = _parse_non_negative_int(
            payload,
            "cluster_threshold",
            default=1,
        )
        labels, matrix, nodes, metadata_fields = build_distance_matrix_from_tsv(
            tsv_text,
            include_missing=include_missing,
            aggregate_profiles=aggregate_profiles,
            metadata_text=metadata_text,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Distance matrix generation failed", exc_info=exc)
        return jsonify({"error": "Distance matrix generation failed"}), 500

    nodes, cluster_summary = _cluster_nodes_by_matrix(
        nodes,
        matrix,
        threshold=cluster_threshold,
    )

    return (
        jsonify(
            {
                "labels": labels,
                "matrix": matrix,
                "table_rows": _build_table_rows(nodes),
                "cluster_summary": cluster_summary,
                "metadata_fields": metadata_fields,
                "aggregate_profiles": aggregate_profiles,
                "export": {
                    "schema_version": EXPORT_SCHEMA_VERSION,
                    "formats": ["matrix-json"],
                },
            }
        ),
        200,
    )


@api_bp.post("/api/locus-diff")
def api_locus_diff() -> tuple[Any, int]:
    """POST ``{tsv, left_label, right_label, include_missing?, metadata_tsv?}``.

    Responds with the per-locus comparison payload from
    :func:`build_locus_diff_from_tsv`.
    """
    try:
        payload = _require_payload_dict()
        tsv_text = _parse_text(payload, "tsv")
        validate_tsv_scale(tsv_text)
        metadata_text = _parse_text(payload, "metadata_tsv")
        if metadata_text:
            validate_tsv_scale(metadata_text)
        left_label = _parse_text(payload, "left_label")
        right_label = _parse_text(payload, "right_label")
        include_missing = _parse_bool(payload, "include_missing", default=False)
        diff = build_locus_diff_from_tsv(
            tsv_text,
            left_label=left_label,
            right_label=right_label,
            include_missing=include_missing,
            metadata_text=metadata_text,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Locus diff generation failed", exc_info=exc)
        return jsonify({"error": "Locus diff generation failed"}), 500

    return jsonify(diff), 200


@api_bp.post("/api/allele-heatmap")
def api_allele_heatmap() -> tuple[Any, int]:
    """POST ``{tsv, metadata_tsv?, aggregate_profiles?}``.

    Responds with ``{labels, loci, cells, table_rows,
    metadata_fields, export}`` where each cell carries its allele value
    and missing/present state.
    """
    try:
        payload = _require_payload_dict()
        tsv_text = _parse_text(payload, "tsv")
        validate_tsv_scale(tsv_text)
        metadata_text = _parse_text(payload, "metadata_tsv")
        if metadata_text:
            validate_tsv_scale(metadata_text)
        aggregate_profiles = _parse_bool(
            payload,
            "aggregate_profiles",
            default=True,
        )
        labels, loci, cells, nodes, metadata_fields = build_allele_heatmap_from_tsv(
            tsv_text,
            aggregate_profiles=aggregate_profiles,
            metadata_text=metadata_text,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Allele heatmap generation failed", exc_info=exc)
        return jsonify({"error": "Allele heatmap generation failed"}), 500

    return (
        jsonify(
            {
                "labels": labels,
                "loci": loci,
                "cells": cells,
                "table_rows": _build_table_rows(nodes),
                "metadata_fields": metadata_fields,
                "aggregate_profiles": aggregate_profiles,
                "export": {
                    "schema_version": EXPORT_SCHEMA_VERSION,
                    "formats": ["heatmap-json"],
                },
            }
        ),
        200,
    )


@api_bp.post("/api/compare-results")
def api_compare_results() -> tuple[Any, int]:
    """POST ``{left_tsv, right_tsv}`` — two typing result tables.

    Responds with the sample-level comparison payload from
    :func:`build_result_comparison_from_tsv`.
    """
    try:
        payload = _require_payload_dict()
        left_tsv = _parse_text(payload, "left_tsv")
        right_tsv = _parse_text(payload, "right_tsv")
        validate_tsv_scale(left_tsv)
        validate_tsv_scale(right_tsv)
        comparison = build_result_comparison_from_tsv(left_tsv, right_tsv)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.exception("Result comparison failed", exc_info=exc)
        return jsonify({"error": "Result comparison failed"}), 500

    return jsonify(comparison), 200
