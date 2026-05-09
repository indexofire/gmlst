from __future__ import annotations

import itertools
from typing import cast

import pytest

from gmlst.visual.mst import MstMethod, build_mst_from_tsv
from gmlst.visual.mst_shared import profile_distance

LINEAR_CHAIN_TSV = """FILE\tSCHEME\tST\tL1\tL2\tL3
s1\tvpa\t-\t1\t1\t1
s2\tvpa\t-\t1\t1\t2
s3\tvpa\t-\t1\t2\t2
s4\tvpa\t-\t2\t2\t2
"""

DUPLICATE_PROFILES_TSV = """FILE\tSCHEME\tST\tL1\tL2
A\tvpa\t-\t1\t1
B\tvpa\t-\t1\t1
C\tvpa\t-\t1\t2
"""

MISSING_DATA_TSV = """FILE\tSCHEME\tST\tL1\tL2\tL3
root\tvpa\t-\t1\t1\t1
a\tvpa\t-\tLNF\t1\t2
b\tvpa\t-\t1\t1\t2
c\tvpa\t-\t1\t2\t2
"""

SUBTREE_RECRAFTING_TSV = """FILE\tSCHEME\tST\tL1\tL2\tL3\tL4
a\tvpa\t-\tLNF\t1\t1\t1
b\tvpa\t-\t1\t1\t1\t1
c\tvpa\t-\tLNF\t1\t2\t2
d\tvpa\t-\tLNF\t1\t2\t3
"""

ALL_IDENTICAL_TSV = """FILE\tSCHEME\tST\tL1\tL2\tL3
s1\tvpa\t-\t1\t1\t1
s2\tvpa\t-\t1\t1\t1
s3\tvpa\t-\t1\t1\t1
s4\tvpa\t-\t1\t1\t1
"""

STAR_TOPOLOGY_TSV = """FILE\tSCHEME\tST\tL1\tL2\tL3\tL4\tL5
center\tvpa\t-\t1\t1\t1\t1\t1
leaf1\tvpa\t-\t2\t1\t1\t1\t1
leaf2\tvpa\t-\t1\t2\t1\t1\t1
leaf3\tvpa\t-\t1\t1\t2\t1\t1
leaf4\tvpa\t-\t1\t1\t1\t2\t1
leaf5\tvpa\t-\t1\t1\t1\t1\t2
"""

MEDIUM_DATASET_TSV = """FILE\tSCHEME\tST\tL1\tL2\tL3\tL4\tL5\tL6
s01\tvpa\t-\t1\t1\t1\t1\t1\t1
s02\tvpa\t-\t1\t1\t1\t1\t1\t2
s03\tvpa\t-\t1\t1\t1\t1\t2\t2
s04\tvpa\t-\t1\t1\t1\t2\t2\t2
s05\tvpa\t-\t1\t1\t2\t2\t2\t2
s06\tvpa\t-\t1\t2\t2\t2\t2\t2
s07\tvpa\t-\t2\t2\t2\t2\t2\t2
s08\tvpa\t-\t1\t1\t3\t3\t3\t3
s09\tvpa\t-\t3\t3\t1\t1\t1\t1
s10\tvpa\t-\t2\t3\t2\t3\t2\t3
s11\tvpa\t-\t1\t1\t1\t1\t1\t3
s12\tvpa\t-\t4\t4\t4\t4\t4\t4
"""

WEIGHTED_TIE_TSV = """FILE\tSCHEME\tST\tL1\tL2\tL3\tL4
s1\tvpa\t-\t1\t1\t1\t1
s2\tvpa\t-\t1\t2\t1\t1
s3\tvpa\t-\t1\t1\t2\t1
s4\tvpa\t-\t1\t1\t1\t2
"""

METHODS: list[MstMethod] = ["edmonds", "grapetree_v2", "grapetree_classic"]

DATASETS = [
    ("linear", LINEAR_CHAIN_TSV),
    ("duplicates", DUPLICATE_PROFILES_TSV),
    ("missing", MISSING_DATA_TSV),
    ("subtree", SUBTREE_RECRAFTING_TSV),
    ("identical", ALL_IDENTICAL_TSV),
    ("star", STAR_TOPOLOGY_TSV),
    ("medium", MEDIUM_DATASET_TSV),
    ("ties", WEIGHTED_TIE_TSV),
]


def _extract_edge_set(edges: list[dict[str, object]]) -> set[tuple[str, str, int]]:
    """Extract normalized edge set: (min_label, max_label, weight)."""
    result = set()
    for edge in edges:
        source = str(edge["source_label"])
        target = str(edge["target_label"])
        weight = cast(int, edge["weight"])
        result.add((min(source, target), max(source, target), weight))
    return result


def _total_weight(edges: list[dict[str, object]]) -> int:
    return sum(cast(int, edge["weight"]) for edge in edges)


def _node_id(node: dict[str, object]) -> int:
    return cast(int, node["id"])


def _edge_endpoint(edge: dict[str, object], key: str) -> int:
    return cast(int, edge[key])


def _is_connected(
    nodes: list[dict[str, object]], edges: list[dict[str, object]]
) -> bool:
    if len(nodes) <= 1:
        return True

    adjacency: dict[int, list[int]] = {_node_id(node): [] for node in nodes}
    for edge in edges:
        source = _edge_endpoint(edge, "source")
        target = _edge_endpoint(edge, "target")
        adjacency[source].append(target)
        adjacency[target].append(source)

    visited: set[int] = set()
    stack = [_node_id(nodes[0])]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, []))

    return len(visited) == len(nodes)


def _has_cycle(nodes: list[dict[str, object]], edges: list[dict[str, object]]) -> bool:
    parent: dict[int, int] = {_node_id(node): _node_id(node) for node in nodes}

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for edge in edges:
        source = _edge_endpoint(edge, "source")
        target = _edge_endpoint(edge, "target")
        root_source = find(source)
        root_target = find(target)
        if root_source == root_target:
            return True
        parent[root_target] = root_source
    return False


def _profile_rows(tsv: str) -> list[tuple[str, tuple[str, ...]]]:
    lines = [line for line in tsv.strip().splitlines() if line.strip()]
    header = lines[0].split("\t")
    loci_start = 3
    return [
        (parts[0], tuple(parts[loci_start:]))
        for parts in (line.split("\t") for line in lines[1:])
        if len(parts) == len(header)
    ]


def _minimum_possible_total_weight(tsv: str) -> int:
    rows = _profile_rows(tsv)
    if len(rows) <= 1:
        return 0

    indexed_rows = list(enumerate(rows))
    weighted_edges: list[tuple[int, int, int]] = []
    for (left_index, (_, left_profile)), (
        right_index,
        (_, right_profile),
    ) in itertools.combinations(indexed_rows, 2):
        weighted_edges.append(
            (
                left_index,
                right_index,
                profile_distance(
                    left_profile,
                    right_profile,
                    include_missing=False,
                ),
            )
        )

    weighted_edges.sort(key=lambda edge: edge[2])

    parent = list(range(len(rows)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    total = 0
    edges_used = 0
    for source, target, weight in weighted_edges:
        root_source = find(source)
        root_target = find(target)
        if root_source == root_target:
            continue
        parent[root_target] = root_source
        total += weight
        edges_used += 1
        if edges_used == len(rows) - 1:
            break
    return total


class TestMstStructuralProperties:
    """Validate that each method produces valid MSTs."""

    @pytest.mark.parametrize("method", METHODS)
    @pytest.mark.parametrize(("tsv_name", "tsv"), DATASETS)
    def test_edge_count_is_n_minus_1(
        self, method: MstMethod, tsv_name: str, tsv: str
    ) -> None:
        nodes, edges, _ = build_mst_from_tsv(
            tsv,
            include_missing=False,
            method=method,
        )
        assert len(edges) == len(nodes) - 1, (
            f"{method} on {tsv_name}: expected {len(nodes) - 1} edges, got {len(edges)}"
        )

    @pytest.mark.parametrize("method", METHODS)
    @pytest.mark.parametrize(("tsv_name", "tsv"), DATASETS)
    def test_graph_is_connected(
        self, method: MstMethod, tsv_name: str, tsv: str
    ) -> None:
        nodes, edges, _ = build_mst_from_tsv(
            tsv,
            include_missing=False,
            method=method,
        )
        assert _is_connected(nodes, edges), (
            f"{method} on {tsv_name}: graph is not connected"
        )

    @pytest.mark.parametrize("method", METHODS)
    @pytest.mark.parametrize(("tsv_name", "tsv"), DATASETS)
    def test_graph_has_no_cycles(
        self, method: MstMethod, tsv_name: str, tsv: str
    ) -> None:
        nodes, edges, _ = build_mst_from_tsv(
            tsv,
            include_missing=False,
            method=method,
        )
        assert not _has_cycle(nodes, edges), (
            f"{method} on {tsv_name}: graph contains a cycle"
        )

    @pytest.mark.parametrize("method", METHODS)
    @pytest.mark.parametrize(("tsv_name", "tsv"), DATASETS)
    def test_total_weight_is_minimal(
        self, method: MstMethod, tsv_name: str, tsv: str
    ) -> None:
        _, edges, _ = build_mst_from_tsv(
            tsv,
            include_missing=False,
            method=method,
        )
        assert _total_weight(edges) == _minimum_possible_total_weight(tsv), (
            f"{method} on {tsv_name}: total weight is not minimal"
        )

    @pytest.mark.parametrize("method", METHODS)
    def test_linear_chain_known_topology(self, method: MstMethod) -> None:
        _, edges, _ = build_mst_from_tsv(
            LINEAR_CHAIN_TSV,
            include_missing=False,
            method=method,
        )
        edge_set = _extract_edge_set(edges)
        assert edge_set == {
            ("s1", "s2", 1),
            ("s2", "s3", 1),
            ("s3", "s4", 1),
        }
        assert _total_weight(edges) == 3

    @pytest.mark.parametrize("method", METHODS)
    def test_duplicate_profiles_have_zero_weight_edge(self, method: MstMethod) -> None:
        _, edges, _ = build_mst_from_tsv(
            DUPLICATE_PROFILES_TSV,
            include_missing=False,
            method=method,
        )
        edge_set = _extract_edge_set(edges)
        assert any(weight == 0 for _, _, weight in edge_set)

    @pytest.mark.parametrize("method", METHODS)
    def test_star_topology_minimum_weight(self, method: MstMethod) -> None:
        _, edges, _ = build_mst_from_tsv(
            STAR_TOPOLOGY_TSV,
            include_missing=False,
            method=method,
        )
        assert _total_weight(edges) == 5

    @pytest.mark.parametrize("method", METHODS)
    def test_all_identical_zero_weight(self, method: MstMethod) -> None:
        _, edges, _ = build_mst_from_tsv(
            ALL_IDENTICAL_TSV,
            include_missing=False,
            method=method,
        )
        assert all(cast(int, edge["weight"]) == 0 for edge in edges)


class TestMstCrossMethodComparison:
    """Compare all 3 methods on the same datasets."""

    @pytest.mark.parametrize(
        ("tsv_name", "tsv"),
        [
            ("linear", LINEAR_CHAIN_TSV),
            ("duplicates", DUPLICATE_PROFILES_TSV),
            ("missing", MISSING_DATA_TSV),
            ("subtree", SUBTREE_RECRAFTING_TSV),
            ("identical", ALL_IDENTICAL_TSV),
            ("star", STAR_TOPOLOGY_TSV),
            ("medium", MEDIUM_DATASET_TSV),
        ],
    )
    def test_total_weights_match_across_methods(self, tsv_name: str, tsv: str) -> None:
        results: dict[str, int] = {}
        for method in METHODS:
            _, edges, _ = build_mst_from_tsv(tsv, include_missing=False, method=method)
            results[method] = _total_weight(edges)

        values = list(results.values())
        assert len(set(values)) == 1, f"{tsv_name}: total weights differ: {results}"

    @pytest.mark.parametrize(
        ("tsv_name", "tsv"),
        [
            ("linear", LINEAR_CHAIN_TSV),
            ("identical", ALL_IDENTICAL_TSV),
            ("star", STAR_TOPOLOGY_TSV),
        ],
    )
    def test_topology_matches_when_no_ties(self, tsv_name: str, tsv: str) -> None:
        edge_sets: dict[str, set[tuple[str, str, int]]] = {}
        for method in METHODS:
            _, edges, _ = build_mst_from_tsv(tsv, include_missing=False, method=method)
            edge_sets[method] = _extract_edge_set(edges)

        reference = edge_sets[METHODS[0]]
        for method in METHODS[1:]:
            assert edge_sets[method] == reference, (
                f"{tsv_name}: {method} topology differs from {METHODS[0]}"
            )
