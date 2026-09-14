"""Compact MST summary for agent/direct-context consumption.

The full MST JSON for n samples is ~750 bytes/sample (~191K tokens for
1000 samples) — too large to read into an LLM context window. This module
condenses it to ~3 bytes/sample (~1K tokens) while preserving every
analytical conclusion an agent needs:

* cluster detection (connected components via low-weight edges)
* per-cluster metadata composition (which clade/source/year dominates)
* edge-weight distribution statistics
* high-frequency variable loci (candidate typing markers)
* outlier nodes (high-weight edges, likely divergent/imported strains)
* actionable analysis suggestions

Agents should use the summary for reasoning and drop to tool-based
processing of the full JSON only when per-sample or per-edge detail is
needed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

_CLUSTER_EDGE_THRESHOLD = 15
_OUTLIER_WEIGHT = 50
_MAX_CLUSTERS = 20
_MAX_VARIABLE_LOCI = 10
_MAX_OUTLIERS = 10


def summarize_mst_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Condense a full MST payload into an agent-readable summary.

    Parameters
    ----------
    payload:
        The dict produced by ``build_mst_from_tsv`` (nodes, edges,
        metadata_fields, …).

    Returns
    -------
    dict[str, Any]
        A JSON-serializable summary of at most a few KB.
    """
    nodes: list[dict[str, Any]] = payload.get("nodes", [])
    edges: list[dict[str, Any]] = payload.get("edges", [])
    metadata_fields: list[str] = [str(f) for f in payload.get("metadata_fields", [])]

    node_map = {str(n["label"]): n for n in nodes}
    adjacency: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for edge in edges:
        weight = int(edge.get("weight", 0))
        src = str(edge.get("source_label", ""))
        tgt = str(edge.get("target_label", ""))
        adjacency[src].append((tgt, weight))
        adjacency[tgt].append((src, weight))

    return {
        "sample_count": len(nodes),
        "mst_summary": _weight_stats(edges),
        "clusters": _detect_clusters(nodes, adjacency, node_map, metadata_fields),
        "top_variable_loci": _variable_loci(edges),
        "outliers": _outliers(edges),
        "metadata_fields": metadata_fields,
        "suggested_analysis": _suggestions(edges, nodes),
    }


def _weight_stats(edges: list[dict[str, Any]]) -> dict[str, Any]:
    if not edges:
        return {"edges": 0}
    weights = sorted(int(e.get("weight", 0)) for e in edges)
    n = len(weights)
    return {
        "edges": n,
        "weight_min": weights[0],
        "weight_median": weights[n // 2],
        "weight_max": weights[-1],
        "zero_weight_pairs": sum(1 for w in weights if w == 0),
    }


def _detect_clusters(
    nodes: list[dict[str, Any]],
    adjacency: dict[str, list[tuple[str, int]]],
    node_map: dict[str, dict[str, Any]],
    metadata_fields: list[str],
) -> list[dict[str, Any]]:
    """Find connected components joined by edges ≤ threshold."""
    visited: set[str] = set()
    clusters: list[dict[str, Any]] = []

    for node in nodes:
        label = str(node["label"])
        if label in visited:
            continue
        component: set[str] = set()
        stack = [label]
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            for neighbor, weight in adjacency.get(current, []):
                if weight <= _CLUSTER_EDGE_THRESHOLD and neighbor not in component:
                    stack.append(neighbor)
        visited |= component

        if len(component) < 5:
            continue

        meta_counts: dict[str, Counter[str]] = {
            field: Counter() for field in metadata_fields
        }
        for sample in component:
            meta = node_map.get(sample, {}).get("meta", {})
            for field in metadata_fields:
                meta_counts[field][str(meta.get(field, "unknown"))] += 1

        cluster_info: dict[str, Any] = {
            "id": f"C{len(clusters) + 1}",
            "size": len(component),
        }
        for field in metadata_fields:
            top, count = meta_counts[field].most_common(1)[0]
            cluster_info[f"{field}_dominant"] = top
            cluster_info[f"{field}_purity"] = round(count / len(component), 2)
            if len(meta_counts[field]) > 1:
                cluster_info[f"{field}_composition"] = dict(
                    meta_counts[field].most_common(5)
                )
        clusters.append(cluster_info)
        if len(clusters) >= _MAX_CLUSTERS:
            break

    clusters.sort(key=lambda c: -c["size"])
    return clusters


def _variable_loci(edges: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for edge in edges:
        for locus in edge.get("mismatch_loci", []):
            counter[str(locus)] += 1
    return counter.most_common(_MAX_VARIABLE_LOCI)


def _outliers(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_max: dict[str, int] = {}
    for edge in edges:
        weight = int(edge.get("weight", 0))
        for key in ("source_label", "target_label"):
            label = str(edge.get(key, ""))
            node_max[label] = max(node_max.get(label, 0), weight)
    ranked = sorted(
        (
            {"node": label, "max_edge_weight": weight}
            for label, weight in node_max.items()
            if weight > _OUTLIER_WEIGHT
        ),
        key=lambda x: -int(x["max_edge_weight"]),
    )
    return ranked[:_MAX_OUTLIERS]


def _suggestions(edges: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> list[str]:
    suggestions: list[str] = []
    weights = [int(e.get("weight", 0)) for e in edges]
    outliers = [w for w in weights if w > _OUTLIER_WEIGHT]
    if outliers:
        suggestions.append(
            f"{len(outliers)} edges exceed weight {_OUTLIER_WEIGHT}; "
            "check those nodes for imported/divergent strains or data quality issues"
        )
    suggestions.append(
        "Compare metadata composition across clusters to identify "
        "transmission links (e.g. same source, overlapping years)"
    )
    suggestions.append(
        "top_variable_loci are candidate discriminant markers for "
        "rapid assay design (high-frequency mismatch across the tree)"
    )
    return suggestions
