from __future__ import annotations

import math

from gmlst.visual.mst_edmonds import build_edmonds_mst_rootless
from gmlst.visual.mst_shared import (
    DirectedEdge,
    MstNode,
    _asymmetric_profile_difference,
    _profile_difference,
    is_missing,
    normalize_allele,
)


def _edge_sort_key(edge: DirectedEdge) -> tuple[float, int, str, str, int, int]:
    return (
        edge.combined_weight,
        edge.asymmetric_weight,
        edge.source_label.lower(),
        edge.target_label.lower(),
        edge.source,
        edge.target,
    )


def _normalized_asymmetric_distance(
    nodes: list[MstNode],
    loci: list[str],
) -> list[list[float]]:
    n = len(nodes)
    n_total = len(loci)
    dist: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        presence_count = sum(
            0 if is_missing(nodes[i].profile[j]) else 1 for j in range(n_total)
        )
        if presence_count == 0:
            continue
        scale = n_total / presence_count
        for k in range(n):
            if i == k:
                continue
            diffs = 0
            for j in range(n_total):
                left = nodes[i].profile[j]
                right = nodes[k].profile[j]
                if is_missing(left):
                    continue
                if normalize_allele(left) != normalize_allele(right):
                    diffs += 1
            dist[i][k] = diffs * scale
    return dist


def _harmonic_weights(
    dist: list[list[float]],
    group_sizes: list[int],
) -> list[float]:
    n = len(dist)
    if n <= 1:
        return [0.0] * n

    harmonic: list[float] = []
    for i in range(n):
        total_inv = sum(1.0 / (dist[i][j] + 0.1) for j in range(n) if j != i)
        harmonic.append(n / total_inv if total_inv > 0 else float(n))

    indices = sorted(range(n), key=lambda idx: (-group_sizes[idx], harmonic[idx]))
    weights = [0.0] * n
    for rank, idx in enumerate(indices):
        weights[idx] = rank / n
    return weights


def _get_shortcuts(
    dist: list[list[float]],
    weights: list[float],
    n_nodes: int,
) -> list[tuple[int, int]]:
    if n_nodes < 3000:
        cutoff = 2
    elif n_nodes < 10000:
        cutoff = 5
    elif n_nodes < 30000:
        cutoff = 10
    else:
        cutoff = 20

    shortcuts: list[tuple[int, int]] = []
    used_targets: set[int] = set()
    candidates: list[tuple[float, float, int, int]] = []
    for source in range(n_nodes):
        for target in range(n_nodes):
            if source == target:
                continue
            if dist[source][target] < cutoff + 1 and weights[source] < weights[target]:
                candidates.append(
                    (weights[source], dist[source][target], source, target)
                )

    candidates.sort()
    for _, _, source, target in candidates:
        if target in used_targets:
            continue
        shortcuts.append((source, target))
        used_targets.add(target)
    return shortcuts


def _build_gt_v2_edge_lookup(
    nodes: list[MstNode],
    dist: list[list[float]],
    weights: list[float],
    loci: list[str],
    *,
    include_missing: bool,
) -> dict[tuple[int, int], DirectedEdge]:
    edge_lookup: dict[tuple[int, int], DirectedEdge] = {}
    for source, source_node in enumerate(nodes):
        for target, target_node in enumerate(nodes):
            if source == target:
                continue
            rounded = round(dist[source][target])
            symmetric_weight, mismatch_loci = _profile_difference(
                source_node.profile,
                target_node.profile,
                loci,
                include_missing=include_missing,
            )
            asymmetric_weight, asymmetric_loci = _asymmetric_profile_difference(
                source_node.profile,
                target_node.profile,
                loci,
                include_missing=include_missing,
            )
            edge_lookup[(source, target)] = DirectedEdge(
                source=source,
                target=target,
                weight=symmetric_weight,
                asymmetric_weight=asymmetric_weight,
                combined_weight=rounded + weights[source],
                source_label=source_node.label,
                target_label=target_node.label,
                mismatch_loci=tuple(mismatch_loci),
                asymmetric_mismatch_loci=tuple(asymmetric_loci),
            )
    return edge_lookup


def _build_children_map(edges: list[DirectedEdge]) -> dict[int, list[int]]:
    children: dict[int, list[int]] = {}
    for edge in edges:
        children.setdefault(edge.source, []).append(edge.target)
    return children


def _collect_descendants(children: dict[int, list[int]], node: int) -> set[int]:
    descendants = {node}
    stack = list(children.get(node, []))
    while stack:
        current = stack.pop()
        if current in descendants:
            continue
        descendants.add(current)
        stack.extend(children.get(current, []))
    return descendants


def _contemporary(
    asym_forward: float,
    asym_reverse: float,
    candidate_dist: float,
    current_dist: float,
    n_loci: int,
) -> bool:
    if n_loci <= 0 or current_dist <= 0:
        return True

    p = asym_forward / n_loci
    q = asym_reverse / n_loci
    if p <= 0 or p >= 1 or q <= 0 or q >= 1:
        return True

    s1 = 1 - (1 - p) * (1 - q)
    s2 = 1 - q
    if s1 <= 0 or s1 >= 1 or s2 <= 0 or s2 >= 1:
        return True

    null_ll = 0.0
    alt_ll = 0.0
    if candidate_dist > 0:
        null_ll += candidate_dist * math.log(s1) + (n_loci - candidate_dist) * math.log(
            1 - s1
        )
    if current_dist > 0 and candidate_dist > 0:
        alt_ll += current_dist * math.log(s2) + (n_loci - current_dist) * math.log(
            1 - s2
        )
    return null_ll >= alt_ll


def _branch_recraft_v2(
    nodes: list[MstNode],
    selected_edges: list[DirectedEdge],
    edge_lookup: dict[tuple[int, int], DirectedEdge],
    dist: list[list[float]],
    weights: list[float],
    n_loci: int,
) -> list[DirectedEdge]:
    selected_by_target = {edge.target: edge for edge in selected_edges}
    ordered_targets = [
        edge.target
        for edge in sorted(
            selected_edges,
            key=lambda edge: (
                dist[edge.source][edge.target],
                weights[edge.source],
                edge.target_label.lower(),
                edge.target,
            ),
        )
    ]

    for target in ordered_targets:
        current_edge = selected_by_target[target]
        children = _build_children_map(list(selected_by_target.values()))
        descendants = _collect_descendants(children, target)
        current_source = current_edge.source
        current_dist = dist[current_source][target]
        current_rank = (
            weights[current_source],
            current_dist,
            nodes[current_source].label.lower(),
            current_source,
        )

        candidate_sources = [
            source
            for source in range(len(nodes))
            if (
                source != target
                and source != current_source
                and source not in descendants
            )
        ]
        candidate_sources.sort(
            key=lambda source: (
                weights[source],
                dist[source][target],
                nodes[source].label.lower(),
                source,
            )
        )

        for candidate_source in candidate_sources[:3]:
            candidate_dist = dist[candidate_source][target]
            candidate_rank = (
                weights[candidate_source],
                candidate_dist,
                nodes[candidate_source].label.lower(),
                candidate_source,
            )
            if candidate_rank >= current_rank:
                continue
            if current_dist > 0 and candidate_dist >= current_dist * 1.5:
                continue
            if not _contemporary(
                dist[current_source][candidate_source],
                dist[candidate_source][current_source],
                candidate_dist,
                current_dist,
                n_loci,
            ):
                continue
            replacement = edge_lookup.get((candidate_source, target))
            if replacement is None:
                continue
            selected_by_target[target] = replacement
            break

    return sorted(selected_by_target.values(), key=_edge_sort_key)


def _to_payload(edges: list[DirectedEdge]) -> list[dict[str, object]]:
    return [
        {
            "source": edge.source,
            "target": edge.target,
            "weight": edge.weight,
            "asymmetric_weight": edge.asymmetric_weight,
            "source_label": edge.source_label,
            "target_label": edge.target_label,
            "mismatch_count": edge.weight,
            "mismatch_loci": list(edge.mismatch_loci),
            "asymmetric_mismatch_loci": list(edge.asymmetric_mismatch_loci),
        }
        for edge in edges
    ]


def build_grapetree_v2_mst(
    nodes: list[MstNode],
    loci: list[str],
    *,
    include_missing: bool,
) -> list[dict[str, object]]:
    if len(nodes) <= 1:
        return []

    dist = _normalized_asymmetric_distance(nodes, loci)
    group_sizes = [len(node.members) for node in nodes]
    weights = _harmonic_weights(dist, group_sizes)
    shortcuts = _get_shortcuts(dist, weights, len(nodes))
    edge_lookup = _build_gt_v2_edge_lookup(
        nodes,
        dist,
        weights,
        loci,
        include_missing=include_missing,
    )

    shortcut_targets = {target for _, target in shortcuts}
    active_indices = [
        index for index in range(len(nodes)) if index not in shortcut_targets
    ]
    active_position = {
        original: active for active, original in enumerate(active_indices)
    }
    active_nodes = [nodes[index] for index in active_indices]
    active_edges: list[DirectedEdge] = []
    for (source, target), edge in edge_lookup.items():
        if source not in active_position or target not in active_position:
            continue
        active_edges.append(
            DirectedEdge(
                source=active_position[source],
                target=active_position[target],
                weight=edge.weight,
                asymmetric_weight=edge.asymmetric_weight,
                combined_weight=edge.combined_weight,
                source_label=edge.source_label,
                target_label=edge.target_label,
                mismatch_loci=edge.mismatch_loci,
                asymmetric_mismatch_loci=edge.asymmetric_mismatch_loci,
            )
        )

    mst_edges: list[DirectedEdge] = []
    if len(active_nodes) > 1:
        active_mst_edges = build_edmonds_mst_rootless(active_nodes, active_edges)
        for edge in active_mst_edges:
            original_source = active_indices[edge.source]
            original_target = active_indices[edge.target]
            mst_edges.append(edge_lookup[(original_source, original_target)])

    for source, target in shortcuts:
        mst_edges.append(edge_lookup[(source, target)])

    mst_edges = _branch_recraft_v2(
        nodes,
        mst_edges,
        edge_lookup,
        dist,
        weights,
        len(loci),
    )
    return _to_payload(mst_edges)


def _normalized_symmetric_distance(
    nodes: list[MstNode],
    loci: list[str],
) -> list[list[float]]:
    n = len(nodes)
    n_total = len(loci)
    dist: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            comparable = 0
            diffs = 0
            for k in range(n_total):
                left_miss = is_missing(nodes[i].profile[k])
                right_miss = is_missing(nodes[j].profile[k])
                if left_miss or right_miss:
                    continue
                comparable += 1
                if normalize_allele(nodes[i].profile[k]) != normalize_allele(
                    nodes[j].profile[k]
                ):
                    diffs += 1
            if comparable > 0:
                distance = (diffs + 0.01) * n_total / (comparable + 0.01)
            else:
                distance = 0.01 * n_total
            dist[i][j] = distance
            dist[j][i] = distance
    return dist


def _eburst_weights(
    dist: list[list[float]],
    group_sizes: list[int],
) -> list[float]:
    n = len(dist)
    if n <= 1:
        return [0.0] * n

    max_dist = max(int(dist[i][j]) for i in range(n) for j in range(i + 1, n))
    histograms: list[list[int]] = []
    for i in range(n):
        counts = [0] * (max_dist + 2)
        counts[0] = group_sizes[i]
        for j in range(n):
            if i == j:
                continue
            distance = int(dist[i][j])
            if distance <= max_dist:
                counts[distance + 1] += 1
        histograms.append(counts)

    def sort_key(idx: int) -> tuple[int, ...]:
        return tuple([-histograms[idx][k] for k in range(1, max_dist + 2)]) + (
            -histograms[idx][0],
        )

    indices = list(range(n))
    indices.sort(key=sort_key)
    weights = [0.0] * n
    for rank, idx in enumerate(indices):
        weights[idx] = rank / n
    return weights


class _DSU:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a == root_b:
            return False
        if self.rank[root_a] < self.rank[root_b]:
            root_a, root_b = root_b, root_a
        self.parent[root_b] = root_a
        if self.rank[root_a] == self.rank[root_b]:
            self.rank[root_a] += 1
        return True


def _kruskal_mst(
    nodes: list[MstNode],
    dist: list[list[float]],
    weights: list[float],
    loci: list[str],
    *,
    include_missing: bool,
) -> list[dict[str, object]]:
    n = len(nodes)
    if n <= 1:
        return []

    edge_list: list[tuple[float, float, float, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            cost = round(dist[i][j]) + (weights[i] + weights[j]) / 2.0
            edge_list.append((cost, dist[i][j], weights[i], i, j))

    edge_list.sort(
        key=lambda edge: (
            edge[0],
            edge[1],
            edge[2],
            nodes[edge[3]].label.lower(),
            nodes[edge[4]].label.lower(),
            edge[3],
            edge[4],
        )
    )

    dsu = _DSU(n)
    mst_edges: list[dict[str, object]] = []
    for _cost, _raw_dist, _weight, i, j in edge_list:
        if not dsu.union(i, j):
            continue
        sym_weight, sym_loci = _profile_difference(
            nodes[i].profile,
            nodes[j].profile,
            loci,
            include_missing=include_missing,
        )
        asym_weight, asym_loci = _asymmetric_profile_difference(
            nodes[i].profile,
            nodes[j].profile,
            loci,
            include_missing=include_missing,
        )
        mst_edges.append(
            {
                "source": i,
                "target": j,
                "weight": sym_weight,
                "asymmetric_weight": asym_weight,
                "source_label": nodes[i].label,
                "target_label": nodes[j].label,
                "mismatch_count": sym_weight,
                "mismatch_loci": list(sym_loci),
                "asymmetric_mismatch_loci": list(asym_loci),
            }
        )
        if len(mst_edges) == n - 1:
            break

    return mst_edges


def build_grapetree_classic_mst(
    nodes: list[MstNode],
    loci: list[str],
    *,
    include_missing: bool,
) -> list[dict[str, object]]:
    if len(nodes) <= 1:
        return []

    dist = _normalized_symmetric_distance(nodes, loci)
    group_sizes = [len(node.members) for node in nodes]
    weights = _eburst_weights(dist, group_sizes)
    return _kruskal_mst(
        nodes,
        dist,
        weights,
        loci,
        include_missing=include_missing,
    )
