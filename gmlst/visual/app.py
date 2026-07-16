from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from gmlst.visual.mst import (
    VALID_MST_METHODS,
    build_allele_heatmap_from_tsv,
    build_distance_matrix_from_tsv,
    build_locus_diff_from_tsv,
    build_mst_from_tsv,
    build_result_comparison_from_tsv,
)
from gmlst.visual.mst_shared import validate_tsv_scale

EXPORT_SCHEMA_VERSION = "gmlst-visual-v1"
_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}

_WELL_KNOWN_PREFIX = "/.well-known/"
_MAX_CONTENT_LENGTH = 32 * 1024 * 1024


class _QuietNotFoundFilter(logging.Filter):
    """Suppress Werkzeug request logs for well-known browser probes and 404s."""

    def filter(self, record: logging.LogRecord) -> bool:
        return _WELL_KNOWN_PREFIX not in record.getMessage()


def _require_payload_dict() -> dict[str, Any]:
    try:
        payload = request.get_json(silent=False)
    except HTTPException as exc:
        raise ValueError(f"Invalid JSON body: {exc}") from exc
    if payload is None:
        raise ValueError("JSON body is required")
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


def _parse_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a string")
    return value


def _parse_bool(payload: dict[str, Any], key: str, *, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _BOOL_TRUE:
            return True
        if normalized in _BOOL_FALSE:
            return False
    raise ValueError(f"'{key}' must be a boolean")


def _parse_non_negative_int(payload: dict[str, Any], key: str, *, default: int) -> int:
    value = payload.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{key}' must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"'{key}' must be >= 0")
    return parsed


def _build_adjacency(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[int, list[tuple[int, int]]]:
    adjacency = {int(node["id"]): [] for node in nodes}
    for edge in edges:
        source = int(edge["source"])
        target = int(edge["target"])
        weight = int(edge["weight"])
        adjacency.setdefault(source, []).append((target, weight))
        adjacency.setdefault(target, []).append((source, weight))
    return adjacency


def _choose_root_id(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> int | None:
    if not nodes:
        return None
    if len(nodes) == 1:
        return int(nodes[0]["id"])

    adjacency = _build_adjacency(nodes, edges)
    member_counts = {
        int(node["id"]): int(node.get("member_count", 1)) for node in nodes
    }
    labels = {int(node["id"]): str(node.get("label", "")) for node in nodes}
    node_ids = [int(node["id"]) for node in nodes]
    n = len(node_ids)

    def _dfs_dist(start: int) -> dict[int, int]:
        dist: dict[int, int] = {start: 0}
        stack = [(start, -1, 0)]
        while stack:
            current, parent, d = stack.pop()
            for nxt, weight in adjacency.get(current, []):
                if nxt == parent:
                    continue
                dist[nxt] = d + weight
                stack.append((nxt, current, d + weight))
        return dist

    dist_a = _dfs_dist(node_ids[0])
    end1 = max(dist_a, key=lambda k: dist_a[k])
    dist1 = _dfs_dist(end1)
    end2 = max(dist1, key=lambda k: dist1[k])
    dist2 = _dfs_dist(end2)

    eccentricity = {nid: max(dist1.get(nid, 0), dist2.get(nid, 0)) for nid in node_ids}

    root = node_ids[0]
    parent_of: dict[int, int] = {}
    subtree_size: dict[int, int] = {}
    order: list[int] = []
    stack = [(root, -1)]
    while stack:
        node_id, par = stack.pop()
        parent_of[node_id] = par
        order.append(node_id)
        for nxt, _weight in adjacency.get(node_id, []):
            if nxt != par:
                stack.append((nxt, node_id))

    for nid in node_ids:
        subtree_size[nid] = 1
    for nid in reversed(order):
        par = parent_of[nid]
        if par != -1:
            subtree_size[par] += subtree_size[nid]

    total_dist: dict[int, int] = {root: sum(dist_a.values())}
    for nid in order:
        for child, weight in adjacency.get(nid, []):
            if child == parent_of.get(nid):
                continue
            total_dist[child] = total_dist[nid] + weight * (n - 2 * subtree_size[child])

    scores: list[tuple[int, int, int, str, int]] = []
    for nid in node_ids:
        scores.append(
            (
                eccentricity[nid],
                total_dist.get(nid, 0),
                -member_counts[nid],
                labels[nid].lower(),
                nid,
            )
        )

    return min(scores)[-1]


def _color_field_preference(field: str) -> tuple[int, str]:
    normalized = field.strip().lower()
    preferred = [
        "country",
        "location",
        "region",
        "source",
        "host",
        "year",
        "date",
        "serotype",
        "lineage",
        "clade",
        "st",
        "scheme",
    ]
    for index, prefix in enumerate(preferred):
        if normalized == prefix or normalized.startswith(prefix):
            return index, normalized
    return len(preferred), normalized


def _suggest_color_fields(
    nodes: list[dict[str, Any]],
    metadata_fields: list[str],
) -> tuple[list[str], str | None]:
    candidates: list[tuple[tuple[int, int, str], str]] = []
    for field in metadata_fields:
        distinct_values = sorted(
            {
                str(node.get("meta", {}).get(field, "")).strip()
                for node in nodes
                if str(node.get("meta", {}).get(field, "")).strip()
            }
        )
        distinct_count = len(distinct_values)
        if distinct_count <= 1:
            continue
        preferred_rank, normalized = _color_field_preference(field)
        candidates.append(((preferred_rank, distinct_count, normalized), field))

    candidates.sort(key=lambda item: item[0])
    suggested = [field for _score, field in candidates[:5]]
    default_field = suggested[0] if suggested else None
    return suggested, default_field


def _build_table_rows(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in nodes:
        members = [str(member) for member in node.get("members", [])]
        rows.append(
            {
                "id": int(node["id"]),
                "sample_id": members[0] if members else str(node.get("label", "")),
                "label": str(node.get("label", "")),
                "member_count": int(node.get("member_count", 1)),
                "members": members,
                "profile_key": str(node.get("profile_key", "")),
                "cluster_id": int(node.get("cluster_id", -1)),
                "meta": dict(node.get("meta", {})),
            }
        )
    return rows


def _cluster_nodes(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    threshold: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes_by_id = {int(node["id"]): node for node in nodes}
    adjacency = {int(node["id"]): [] for node in nodes}
    for edge in edges:
        weight = int(edge["weight"])
        if weight > threshold:
            continue
        source = int(edge["source"])
        target = int(edge["target"])
        adjacency[source].append(target)
        adjacency[target].append(source)

    cluster_by_node: dict[int, int] = {}
    cluster_summary: list[dict[str, Any]] = []
    next_cluster_id = 0
    for node in nodes:
        node_id = int(node["id"])
        if node_id in cluster_by_node:
            continue
        stack = [node_id]
        members: list[dict[str, Any]] = []
        while stack:
            current = stack.pop()
            if current in cluster_by_node:
                continue
            cluster_by_node[current] = next_cluster_id
            current_node = nodes_by_id[current]
            members.append(current_node)
            stack.extend(
                neighbor
                for neighbor in adjacency[current]
                if neighbor not in cluster_by_node
            )

        member_names = [
            str(member)
            for node_entry in members
            for member in node_entry.get("members", [])
        ]
        cluster_summary.append(
            {
                "cluster_id": next_cluster_id,
                "node_count": len(members),
                "sample_count": len(member_names),
                "members": member_names,
            }
        )
        next_cluster_id += 1

    clustered_nodes = []
    for node in nodes:
        clustered_node = dict(node)
        clustered_node["cluster_id"] = cluster_by_node[int(node["id"])]
        clustered_nodes.append(clustered_node)
    return clustered_nodes, cluster_summary


def _cluster_nodes_by_matrix(
    nodes: list[dict[str, Any]],
    matrix: list[list[int]],
    *,
    threshold: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes_by_id = {int(node["id"]): node for node in nodes}
    adjacency = {int(node["id"]): [] for node in nodes}
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            if row_index == col_index or value > threshold:
                continue
            adjacency[row_index].append(col_index)

    cluster_by_node: dict[int, int] = {}
    cluster_summary: list[dict[str, Any]] = []
    next_cluster_id = 0
    for node in nodes:
        node_id = int(node["id"])
        if node_id in cluster_by_node:
            continue
        stack = [node_id]
        members: list[dict[str, Any]] = []
        while stack:
            current = stack.pop()
            if current in cluster_by_node:
                continue
            cluster_by_node[current] = next_cluster_id
            current_node = nodes_by_id[current]
            members.append(current_node)
            stack.extend(
                neighbor
                for neighbor in adjacency[current]
                if neighbor not in cluster_by_node
            )

        member_names = [
            str(member)
            for node_entry in members
            for member in node_entry.get("members", [])
        ]
        cluster_summary.append(
            {
                "cluster_id": next_cluster_id,
                "node_count": len(members),
                "sample_count": len(member_names),
                "members": member_names,
            }
        )
        next_cluster_id += 1

    clustered_nodes = []
    for node in nodes:
        clustered_node = dict(node)
        clustered_node["cluster_id"] = cluster_by_node[int(node["id"])]
        clustered_nodes.append(clustered_node)
    return clustered_nodes, cluster_summary


def create_visual_app(*, title: str) -> Flask:
    web_root = Path(__file__).resolve().parents[1] / "web"
    app = Flask(
        "gmlst_visual",
        template_folder=str(web_root / "templates"),
        static_folder=str(web_root / "static"),
        static_url_path="/static",
    )
    app.config["GMLST_VISUAL_TITLE"] = title
    app.config["MAX_CONTENT_LENGTH"] = _MAX_CONTENT_LENGTH
    app.config["SECRET_KEY"] = secrets.token_urlsafe(32)

    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.addFilter(_QuietNotFoundFilter())

    @app.before_request
    def _enforce_same_origin() -> tuple[Any, int] | None:
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return None
        origin = request.headers.get("Origin")
        referer = request.headers.get("Referer")
        host_url = request.host_url.rstrip("/")
        if origin is not None and origin.rstrip("/") != host_url:
            return jsonify({"error": "Cross-origin requests are not allowed"}), 403
        if origin is None and referer is not None:
            parsed = urlparse(referer)
            if f"{parsed.scheme}://{parsed.netloc}" != host_url:
                return jsonify({"error": "Cross-origin requests are not allowed"}), 403
        return None

    @app.after_request
    def _set_security_headers(response: Any) -> Any:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.get("/")
    def index() -> str:
        return render_template(
            "visual/index.html",
            title=app.config["GMLST_VISUAL_TITLE"],
        )

    @app.route("/.well-known/<path:subpath>")
    def well_known_catch(subpath: str) -> tuple[str, int]:
        return "", 204

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        return {"status": "ok"}, 200

    @app.post("/api/mst")
    def api_mst() -> tuple[Any, int]:
        try:
            payload = _require_payload_dict()
            validate_tsv_scale(payload.get("tsv", "") or "")
            tsv_text = _parse_text(payload, "tsv")
            metadata_text = _parse_text(payload, "metadata_tsv")
            method = _parse_text(payload, "method") or "edmonds"
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
            app.logger.exception("MST generation failed", exc_info=exc)
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

    @app.post("/api/distance-matrix")
    def api_distance_matrix() -> tuple[Any, int]:
        try:
            payload = _require_payload_dict()
            validate_tsv_scale(payload.get("tsv", "") or "")
            tsv_text = _parse_text(payload, "tsv")
            metadata_text = _parse_text(payload, "metadata_tsv")
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
            app.logger.exception("Distance matrix generation failed", exc_info=exc)
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

    @app.post("/api/locus-diff")
    def api_locus_diff() -> tuple[Any, int]:
        try:
            payload = _require_payload_dict()
            validate_tsv_scale(payload.get("tsv", "") or "")
            tsv_text = _parse_text(payload, "tsv")
            metadata_text = _parse_text(payload, "metadata_tsv")
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
            app.logger.exception("Locus diff generation failed", exc_info=exc)
            return jsonify({"error": "Locus diff generation failed"}), 500

        return jsonify(diff), 200

    @app.post("/api/allele-heatmap")
    def api_allele_heatmap() -> tuple[Any, int]:
        try:
            payload = _require_payload_dict()
            validate_tsv_scale(payload.get("tsv", "") or "")
            tsv_text = _parse_text(payload, "tsv")
            metadata_text = _parse_text(payload, "metadata_tsv")
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
            app.logger.exception("Allele heatmap generation failed", exc_info=exc)
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

    @app.post("/api/compare-results")
    def api_compare_results() -> tuple[Any, int]:
        try:
            payload = _require_payload_dict()
            validate_tsv_scale(payload.get("left_tsv", "") or "")
            validate_tsv_scale(payload.get("right_tsv", "") or "")
            left_tsv = _parse_text(payload, "left_tsv")
            right_tsv = _parse_text(payload, "right_tsv")
            comparison = build_result_comparison_from_tsv(left_tsv, right_tsv)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Result comparison failed", exc_info=exc)
            return jsonify({"error": "Result comparison failed"}), 500

        return jsonify(comparison), 200

    return app
