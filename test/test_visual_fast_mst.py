"""Tests for the packed numpy/numba fast MST path."""

from __future__ import annotations

import random

import numpy as np
import pytest

from gmlst.visual import fast_mst
from gmlst.visual.fast_mst import build_fast_mst, parse_packed_table
from gmlst.visual.mst import build_mst_from_tsv
from gmlst.visual.mst_shared import (
    _aggregate_profiles,
    _parse_metadata_text,
    _parse_rows,
    _profile_difference,
    is_missing,
)


def _make_tsv(
    rows: int,
    loci: int,
    *,
    seed: int = 7,
    missing_rate: float = 0.1,
) -> str:
    rng = random.Random(seed)
    header = "FILE\tSCHEME\tST\t" + "\t".join(f"L{i}" for i in range(loci))
    lines = [header]
    for row in range(rows):
        values = []
        for locus in range(loci):
            if rng.random() < missing_rate:
                values.append(rng.choice(["-", "LNF", "~", ""]))
            elif rng.random() < 0.2:
                values.append(f"~{100 + (row + locus * 3) % 7}")
            else:
                values.append(str(100 + (row + locus * 3) % 7))
        lines.append(f"S{row:03d}\tsenterica\t{100 + row % 3}\t" + "\t".join(values))
    return "\n".join(lines)


def test_packed_parser_reproduces_profiles() -> None:
    tsv = _make_tsv(40, 30)
    table = parse_packed_table(tsv, None)
    metadata_by_sample, extra = _parse_metadata_text(None)
    nodes, loci, _fields = _parse_rows(
        tsv,
        metadata_by_sample=metadata_by_sample,
        extra_metadata_fields=extra,
    )

    assert table.loci == loci
    assert table.labels == [node.label for node in nodes]
    for row, node in enumerate(nodes):
        for locus, value in enumerate(node.profile):
            code = int(table.codes[row, locus])
            expected = "" if is_missing(value) else value
            assert table.tokens[locus][code] == expected


def test_packed_aggregation_matches_reference() -> None:
    tsv = _make_tsv(60, 25)
    table = parse_packed_table(tsv, None)
    metadata_by_sample, extra = _parse_metadata_text(None)
    nodes, _loci, _fields = _parse_rows(
        tsv,
        metadata_by_sample=metadata_by_sample,
        extra_metadata_fields=extra,
    )
    expected = sorted(sorted(node.members) for node in _aggregate_profiles(nodes)[0])
    groups = fast_mst._group_profiles(table)
    actual = sorted(
        sorted(table.labels[index] for index in members) for members in groups.values()
    )
    assert actual == expected


def test_packed_distance_matches_reference() -> None:
    tsv = _make_tsv(30, 20)
    table = parse_packed_table(tsv, None)
    metadata_by_sample, extra = _parse_metadata_text(None)
    nodes, loci, _fields = _parse_rows(
        tsv,
        metadata_by_sample=metadata_by_sample,
        extra_metadata_fields=extra,
    )
    from gmlst.visual.mst_grapetree import _normalized_symmetric_distance

    expected = np.asarray(_normalized_symmetric_distance(nodes, loci))
    actual = fast_mst._distance_matrix(table.codes)
    assert np.allclose(actual, expected, atol=1e-4)


@pytest.mark.parametrize("include_missing", [False, True])
def test_fast_mst_edge_weights_match_profile_difference(
    include_missing: bool,
) -> None:
    tsv = _make_tsv(50, 20)
    nodes, edges, _fields = build_fast_mst(
        tsv,
        include_missing=include_missing,
        aggregate_profiles=True,
    )
    metadata_by_sample, extra = _parse_metadata_text(None)
    parsed, loci, _ = _parse_rows(
        tsv,
        metadata_by_sample=metadata_by_sample,
        extra_metadata_fields=extra,
    )
    member_to_node = {
        member: node
        for node in _aggregate_profiles(parsed)[0]
        for member in node.members
    }
    for edge in edges:
        left = member_to_node[edge["source_label"]]
        right = member_to_node[edge["target_label"]]
        weight, _ = _profile_difference(
            left.profile,
            right.profile,
            loci,
            include_missing=include_missing,
        )
        assert edge["weight"] == weight


def test_fast_mst_aggregation_off_keeps_every_sample() -> None:
    tsv = _make_tsv(20, 10, missing_rate=0)
    # Duplicate every profile (with fresh sample IDs) so aggregation has work.
    lines = tsv.splitlines()
    for line in lines[1:]:
        cells = line.split("\t")
        cells[0] = cells[0] + "-copy"
        lines.append("\t".join(cells))
    duplicated = "\n".join(lines)

    nodes, edges, _fields = build_fast_mst(
        duplicated,
        aggregate_profiles=False,
    )
    assert len(nodes) == 40
    assert len(edges) == 39
    assert any(edge["weight"] == 0 for edge in edges)


def test_fast_mst_wide_allele_space_uses_16_bit_codes() -> None:
    header = "FILE\t" + "\t".join(f"L{i}" for i in range(3))
    lines = [header]
    for row in range(300):
        lines.append(f"S{row}\t{row}\t{row % 7}\t{row % 5}")
    table = parse_packed_table("\n".join(lines), None)
    assert table.codes.dtype == np.uint16

    nodes, edges, _fields = build_fast_mst("\n".join(lines))
    assert len(nodes) == 300
    assert len(edges) == 299


def test_build_mst_routes_large_inputs_to_fast_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gmlst.visual import mst

    monkeypatch.setattr(mst, "FAST_PATH_CELLS", 1)
    monkeypatch.setattr(mst, "FAST_PATH_SAMPLES", 1)
    tsv = _make_tsv(25, 12)
    nodes, edges, _fields = build_mst_from_tsv(tsv, method="grapetree_classic")
    assert len(nodes) == 25
    assert len(edges) == 24


def test_fast_mst_rejects_inputs_above_the_node_cap() -> None:
    tsv = _make_tsv(30, 8, missing_rate=0)
    with pytest.raises(ValueError, match="too many nodes"):
        build_fast_mst(tsv, max_nodes=3)
