from __future__ import annotations

from collections import deque

from gmlst.visual.mst_shared import (
    DirectedEdge,
    MstNode,
    _asymmetric_profile_difference,
    _profile_difference,
    _resolved_allele_count,
    asymmetric_profile_distance,
    profile_distance,
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


def _build_directed_edges(
    nodes: list[MstNode],
    loci: list[str],
    *,
    include_missing: bool,
) -> list[DirectedEdge]:
    max_symmetric = max(1, len(loci))
    edges: list[DirectedEdge] = []
    for source, source_node in enumerate(nodes):
        for target, target_node in enumerate(nodes):
            if source == target:
                continue
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
            combined_weight = asymmetric_weight * (max_symmetric + 1) + symmetric_weight
            edges.append(
                DirectedEdge(
                    source=source,
                    target=target,
                    weight=symmetric_weight,
                    asymmetric_weight=asymmetric_weight,
                    combined_weight=combined_weight,
                    source_label=source_node.label,
                    target_label=target_node.label,
                    mismatch_loci=tuple(mismatch_loci),
                    asymmetric_mismatch_loci=tuple(asymmetric_loci),
                )
            )
    return edges


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


def _build_parent_map(edges: list[DirectedEdge]) -> dict[int, int]:
    return {edge.target: edge.source for edge in edges}


def _collect_ancestors(parents: dict[int, int], node: int) -> set[int]:
    ancestors: set[int] = set()
    current = node
    while current in parents:
        current = parents[current]
        if current in ancestors:
            break
        ancestors.add(current)
    return ancestors


def _recraft_candidate_score(
    nodes: list[MstNode],
    edge: DirectedEdge,
    subtree_nodes: set[int],
) -> tuple[int, int, float, int, int, int, str, int]:
    parent_resolved = _resolved_allele_count(nodes[edge.source].profile)
    child_resolved = _resolved_allele_count(nodes[edge.target].profile)
    resolution_gap = max(0, child_resolved - parent_resolved)
    subtree_resolution_gap = sum(
        max(0, _resolved_allele_count(nodes[node_id].profile) - parent_resolved)
        for node_id in subtree_nodes
    )
    return (
        subtree_resolution_gap,
        resolution_gap,
        edge.combined_weight,
        edge.asymmetric_weight,
        -parent_resolved,
        edge.weight,
        edge.source_label.lower(),
        edge.source,
    )


def _subtree_recraft_cost(
    nodes: list[MstNode],
    parent_profile: tuple[str, ...],
    subtree_nodes: set[int],
    loci_count: int,
    *,
    include_missing: bool,
) -> tuple[int, int]:
    max_symmetric = max(1, loci_count)
    combined_total = 0
    asymmetric_total = 0
    for node_id in subtree_nodes:
        child_profile = nodes[node_id].profile
        symmetric_weight = profile_distance(
            parent_profile,
            child_profile,
            include_missing=include_missing,
        )
        asymmetric_weight = asymmetric_profile_distance(
            parent_profile,
            child_profile,
            include_missing=include_missing,
        )
        combined_total += asymmetric_weight * (max_symmetric + 1) + symmetric_weight
        asymmetric_total += asymmetric_weight
    return combined_total, asymmetric_total


def _recraft_branching(
    nodes: list[MstNode],
    directed_edges: list[DirectedEdge],
    selected_edges: list[DirectedEdge],
    *,
    include_missing: bool,
    loci_count: int,
) -> list[DirectedEdge]:
    directed_by_target: dict[int, list[DirectedEdge]] = {}
    for edge in directed_edges:
        directed_by_target.setdefault(edge.target, []).append(edge)

    selected = list(selected_edges)
    pending = deque(range(len(nodes)))
    while pending:
        incoming = {edge.target: edge for edge in selected}
        children = _build_children_map(selected)
        parents = _build_parent_map(selected)
        target = pending.popleft()
        current_edge = incoming.get(target)
        if current_edge is None:
            continue

        descendants = _collect_descendants(children, target)
        current_subtree_cost = _subtree_recraft_cost(
            nodes,
            nodes[current_edge.source].profile,
            descendants,
            loci_count,
            include_missing=include_missing,
        )
        candidates = []
        for candidate in directed_by_target.get(target, []):
            if (
                candidate.source in descendants
                or candidate.source == current_edge.source
            ):
                continue
            if candidate.combined_weight > current_edge.combined_weight + 1:
                continue
            if (
                candidate.combined_weight > current_edge.combined_weight
                and current_edge.weight == 0
            ):
                continue
            if candidate.asymmetric_weight > current_edge.asymmetric_weight:
                continue
            candidate_subtree_cost = _subtree_recraft_cost(
                nodes,
                nodes[candidate.source].profile,
                descendants,
                loci_count,
                include_missing=include_missing,
            )
            if candidate_subtree_cost > current_subtree_cost:
                continue
            candidates.append(candidate)

        if not candidates:
            continue

        best_candidate = min(
            [current_edge, *candidates],
            key=lambda edge: _recraft_candidate_score(nodes, edge, descendants),
        )
        if best_candidate == current_edge:
            continue

        old_parent = current_edge.source
        new_parent = best_candidate.source
        selected = [
            best_candidate if edge.target == target else edge for edge in selected
        ]

        affected = set(descendants)
        affected.add(target)
        affected.add(old_parent)
        affected.add(new_parent)
        affected.update(children.get(old_parent, []))
        affected.update(children.get(new_parent, []))
        affected.update(_collect_ancestors(parents, old_parent))
        affected.update(_collect_ancestors(parents, new_parent))
        for node_id in sorted(affected):
            pending.append(node_id)

    return selected


def _find_directed_cycle(selected: dict[int, DirectedEdge]) -> list[int] | None:
    visited: set[int] = set()
    for start in selected:
        if start in visited:
            continue
        path: list[int] = []
        position: dict[int, int] = {}
        current = start
        while current in selected:
            if current in position:
                return path[position[current] :]
            if current in visited:
                break
            position[current] = len(path)
            path.append(current)
            current = selected[current].source
        visited.update(path)
    return None


def _select_min_incoming(
    node_ids: set[int],
    edges: list[DirectedEdge],
    root: int,
) -> dict[int, DirectedEdge]:
    incoming: dict[int, DirectedEdge] = {}
    for edge in edges:
        if (
            edge.target == root
            or edge.target not in node_ids
            or edge.source not in node_ids
        ):
            continue
        previous = incoming.get(edge.target)
        if previous is None or _edge_sort_key(edge) < _edge_sort_key(previous):
            incoming[edge.target] = edge
    return incoming


def _minimum_arborescence(
    node_ids: set[int],
    edges: list[DirectedEdge],
    root: int,
    *,
    next_id: int,
) -> tuple[list[DirectedEdge], int]:
    selected = _select_min_incoming(node_ids, edges, root)
    cycle = _find_directed_cycle(selected)
    if cycle is None:
        return list(selected.values()), next_id

    cycle_set = set(cycle)
    cycle_incoming = {node: selected[node] for node in cycle}
    supernode = next_id
    next_id += 1

    contracted_nodes = {node for node in node_ids if node not in cycle_set}
    contracted_nodes.add(supernode)

    contracted_edges: list[DirectedEdge] = []
    enter_map: dict[tuple[int, int], tuple[DirectedEdge, int]] = {}
    leave_map: dict[tuple[int, int], DirectedEdge] = {}

    for edge in edges:
        source_in_cycle = edge.source in cycle_set
        target_in_cycle = edge.target in cycle_set
        if source_in_cycle and target_in_cycle:
            continue
        if not source_in_cycle and not target_in_cycle:
            contracted_edges.append(edge)
            continue
        if not source_in_cycle and target_in_cycle:
            adjusted_weight = (
                edge.combined_weight - cycle_incoming[edge.target].combined_weight
            )
            adjusted = DirectedEdge(
                source=edge.source,
                target=supernode,
                weight=edge.weight,
                asymmetric_weight=edge.asymmetric_weight,
                combined_weight=adjusted_weight,
                source_label=edge.source_label,
                target_label=edge.target_label,
                mismatch_loci=edge.mismatch_loci,
                asymmetric_mismatch_loci=edge.asymmetric_mismatch_loci,
            )
            key = (adjusted.source, adjusted.target)
            previous = enter_map.get(key)
            if previous is None or _edge_sort_key(adjusted) < _edge_sort_key(
                previous[0]
            ):
                enter_map[key] = (adjusted, edge.target)
            continue
        if source_in_cycle and not target_in_cycle:
            adjusted = DirectedEdge(
                source=supernode,
                target=edge.target,
                weight=edge.weight,
                asymmetric_weight=edge.asymmetric_weight,
                combined_weight=edge.combined_weight,
                source_label=edge.source_label,
                target_label=edge.target_label,
                mismatch_loci=edge.mismatch_loci,
                asymmetric_mismatch_loci=edge.asymmetric_mismatch_loci,
            )
            key = (adjusted.source, adjusted.target)
            previous = leave_map.get(key)
            if previous is None or _edge_sort_key(adjusted) < _edge_sort_key(previous):
                leave_map[key] = edge

    contracted_edges.extend(adjusted for adjusted, _target in enter_map.values())
    contracted_edges.extend(
        DirectedEdge(
            source=adjusted.source,
            target=adjusted.target,
            weight=adjusted.weight,
            asymmetric_weight=adjusted.asymmetric_weight,
            combined_weight=adjusted.combined_weight,
            source_label=adjusted.source_label,
            target_label=adjusted.target_label,
            mismatch_loci=adjusted.mismatch_loci,
            asymmetric_mismatch_loci=adjusted.asymmetric_mismatch_loci,
        )
        for adjusted in (
            DirectedEdge(
                source=supernode,
                target=edge.target,
                weight=edge.weight,
                asymmetric_weight=edge.asymmetric_weight,
                combined_weight=edge.combined_weight,
                source_label=edge.source_label,
                target_label=edge.target_label,
                mismatch_loci=edge.mismatch_loci,
                asymmetric_mismatch_loci=edge.asymmetric_mismatch_loci,
            )
            for edge in leave_map.values()
        )
    )

    contracted_root = supernode if root in cycle_set else root
    contracted_solution, next_id = _minimum_arborescence(
        contracted_nodes,
        contracted_edges,
        contracted_root,
        next_id=next_id,
    )

    expanded: list[DirectedEdge] = []
    replaced_target: int | None = None
    for edge in contracted_solution:
        if edge.target == supernode:
            original_adjusted, original_target = enter_map[(edge.source, edge.target)]
            replaced_target = original_target
            expanded.append(
                next(
                    original
                    for original in edges
                    if original.source == edge.source
                    and original.target == original_target
                )
            )
        elif edge.source == supernode:
            expanded.append(leave_map[(edge.source, edge.target)])
        else:
            expanded.append(edge)

    skip_target = root if root in cycle_set else replaced_target
    for node in cycle:
        if node != skip_target:
            expanded.append(cycle_incoming[node])
    return expanded, next_id


def _build_mst_edges(
    nodes: list[MstNode],
    loci: list[str],
    *,
    include_missing: bool,
) -> list[dict[str, object]]:
    node_count = len(nodes)
    if node_count <= 1:
        return []

    directed_edges = _build_directed_edges(
        nodes,
        loci,
        include_missing=include_missing,
    )
    best_edges: list[DirectedEdge] | None = None
    best_score: tuple[float, int, str, int] | None = None
    next_id = node_count
    for root in range(node_count):
        candidate_edges, next_id = _minimum_arborescence(
            set(range(node_count)),
            directed_edges,
            root,
            next_id=next_id,
        )
        combined_total = sum(edge.combined_weight for edge in candidate_edges)
        asymmetric_total = sum(edge.asymmetric_weight for edge in candidate_edges)
        candidate_score = (
            combined_total,
            asymmetric_total,
            nodes[root].label.lower(),
            root,
        )
        if best_score is None or candidate_score < best_score:
            best_score = candidate_score
            best_edges = candidate_edges

    assert best_edges is not None
    best_edges = _recraft_branching(
        nodes,
        directed_edges,
        best_edges,
        include_missing=include_missing,
        loci_count=len(loci),
    )
    best_edges.sort(key=_edge_sort_key)
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
        for edge in best_edges
    ]


def build_edmonds_mst(
    nodes: list[MstNode],
    loci: list[str],
    *,
    include_missing: bool,
) -> list[dict[str, object]]:
    return _build_mst_edges(nodes, loci, include_missing=include_missing)


def build_edmonds_mst_rootless(
    nodes: list[MstNode],
    edges: list[DirectedEdge],
) -> list[DirectedEdge]:
    """Find minimum spanning arborescence without a pre-specified root.

    Uses a synthetic super-root with zero-cost edges to all real nodes.
    Run Edmonds' algorithm once, then remove the super-root edge.
    """
    if len(nodes) <= 1:
        return []

    super_root = len(nodes)
    extended_edges = list(edges)
    for i in range(len(nodes)):
        extended_edges.append(
            DirectedEdge(
                source=super_root,
                target=i,
                weight=0,
                asymmetric_weight=0,
                combined_weight=-1.0,
                source_label="__super_root__",
                target_label=nodes[i].label,
                mismatch_loci=(),
                asymmetric_mismatch_loci=(),
            )
        )

    node_ids = set(range(len(nodes))) | {super_root}
    result_edges, _ = _minimum_arborescence(
        node_ids,
        extended_edges,
        super_root,
        next_id=super_root + 1,
    )

    return [
        edge
        for edge in result_edges
        if edge.source != super_root and edge.target != super_root
    ]
