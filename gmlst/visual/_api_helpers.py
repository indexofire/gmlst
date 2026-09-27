"""Request parsing and clustering helpers for the visualization JSON API."""

from __future__ import annotations

from typing import Any

from flask import request
from werkzeug.exceptions import HTTPException

EXPORT_SCHEMA_VERSION = "gmlst-visual-export-v1"
_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}


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
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"'{key}' must be an integer")
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
    """Pick the layout root node for the tree view.

    Prefers nodes minimizing (weighted eccentricity, total distance to all
    nodes, then larger member groups, then label) — approximated via double
    DFS from a tree end plus rerooting sums. Returns None for empty input.
    """
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


def _cluster_by_adjacency(
    nodes: list[dict[str, Any]],
    adjacency: dict[int, list[int]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes_by_id = {int(node["id"]): node for node in nodes}
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


def _cluster_nodes(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    threshold: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Group nodes into clusters connected by edges of weight <= threshold.

    Returns nodes annotated with ``cluster_id`` plus a per-cluster summary.
    """
    adjacency = {int(node["id"]): [] for node in nodes}
    for edge in edges:
        weight = int(edge["weight"])
        if weight > threshold:
            continue
        source = int(edge["source"])
        target = int(edge["target"])
        adjacency[source].append(target)
        adjacency[target].append(source)
    return _cluster_by_adjacency(nodes, adjacency)


def _cluster_nodes_by_matrix(
    nodes: list[dict[str, Any]],
    matrix: list[list[int]],
    *,
    threshold: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Cluster nodes from a full distance matrix using the same threshold rule."""
    adjacency = {int(node["id"]): [] for node in nodes}
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            if row_index == col_index or value > threshold:
                continue
            adjacency[row_index].append(col_index)
    return _cluster_by_adjacency(nodes, adjacency)
