from __future__ import annotations

import csv
import io
from typing import Literal, TypedDict, cast

from gmlst.visual.mst_edmonds import build_edmonds_mst
from gmlst.visual.mst_grapetree import build_grapetree_v2_mst
from gmlst.visual.mst_shared import (
    META_COLUMNS,
    _aggregate_profiles,
    _build_payload,
    _parse_metadata_text,
    _parse_rows,
    _profile_difference,
    _restore_duplicate_leaves,
    _sample_key_for,
    _sniff_delimiter,
    _validate_mst,
    is_missing,
    profile_distance,
)

MstMethod = Literal["edmonds", "grapetree_v2", "grapetree_classic"]

VALID_MST_METHODS: tuple[MstMethod, ...] = (
    "edmonds",
    "grapetree_v2",
    "grapetree_classic",
)


def build_mst_from_tsv(
    tsv_text: str,
    *,
    metadata_text: str | None = None,
    include_missing: bool = False,
    aggregate_profiles: bool = False,
    method: MstMethod = "edmonds",
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    if not tsv_text.strip():
        raise ValueError("No TSV content provided")
    if method not in VALID_MST_METHODS:
        raise ValueError(
            f"Unknown MST method: {method!r}. Choose from {VALID_MST_METHODS}"
        )

    metadata_by_sample, extra_metadata_fields = _parse_metadata_text(metadata_text)
    nodes, loci, metadata_fields = _parse_rows(
        tsv_text,
        metadata_by_sample=metadata_by_sample,
        extra_metadata_fields=extra_metadata_fields,
    )
    meta_breakdowns = None
    if aggregate_profiles:
        nodes, meta_breakdowns = _aggregate_profiles(nodes)

    if aggregate_profiles:
        payload_mst_nodes = nodes
        if method == "edmonds":
            edges = build_edmonds_mst(
                payload_mst_nodes,
                loci,
                include_missing=include_missing,
            )
        elif method == "grapetree_v2":
            edges = build_grapetree_v2_mst(
                payload_mst_nodes,
                loci,
                include_missing=include_missing,
            )
        elif method == "grapetree_classic":
            from gmlst.visual.mst_grapetree import build_grapetree_classic_mst

            edges = build_grapetree_classic_mst(
                payload_mst_nodes,
                loci,
                include_missing=include_missing,
            )
        else:
            raise ValueError(
                f"Unknown MST method: {method!r}. Choose from {VALID_MST_METHODS}"
            )
    else:
        payload_mst_nodes, edges = _restore_duplicate_leaves(
            nodes,
            loci,
            include_missing=include_missing,
        )

    payload_nodes = _build_payload(payload_mst_nodes, meta_breakdowns)
    if len(payload_mst_nodes) == 1:
        return payload_nodes, [], metadata_fields

    _validate_mst(
        payload_mst_nodes,
        edges,
        loci,
        include_missing=include_missing,
    )
    return payload_nodes, edges, metadata_fields


def build_distance_matrix_from_tsv(
    tsv_text: str,
    *,
    include_missing: bool,
    aggregate_profiles: bool = False,
    metadata_text: str | None = None,
) -> tuple[list[str], list[list[int]], list[dict[str, object]], list[str]]:
    if not tsv_text.strip():
        raise ValueError("No TSV content provided")

    metadata_by_sample, extra_metadata_fields = _parse_metadata_text(metadata_text)
    nodes, loci, metadata_fields = _parse_rows(
        tsv_text,
        metadata_by_sample=metadata_by_sample,
        extra_metadata_fields=extra_metadata_fields,
    )
    meta_breakdowns = None
    if aggregate_profiles:
        nodes, meta_breakdowns = _aggregate_profiles(nodes)

    payload_nodes = _build_payload(nodes, meta_breakdowns)
    labels = [str(node["label"]) for node in payload_nodes]
    matrix: list[list[int]] = []
    for left in nodes:
        row: list[int] = []
        for right in nodes:
            row.append(
                profile_distance(
                    left.profile,
                    right.profile,
                    include_missing=include_missing,
                )
            )
        matrix.append(row)
    return labels, matrix, payload_nodes, metadata_fields


def build_locus_diff_from_tsv(
    tsv_text: str,
    *,
    left_label: str,
    right_label: str,
    include_missing: bool,
    metadata_text: str | None = None,
) -> dict[str, object]:
    if not tsv_text.strip():
        raise ValueError("No TSV content provided")

    metadata_by_sample, extra_metadata_fields = _parse_metadata_text(metadata_text)
    nodes, loci, _metadata_fields = _parse_rows(
        tsv_text,
        metadata_by_sample=metadata_by_sample,
        extra_metadata_fields=extra_metadata_fields,
    )

    left_node = next((node for node in nodes if node.label == left_label), None)
    right_node = next((node for node in nodes if node.label == right_label), None)
    if left_node is None or right_node is None:
        raise ValueError("Requested labels not found in profile input")

    distance, mismatch_loci = _profile_difference(
        left_node.profile,
        right_node.profile,
        loci,
        include_missing=include_missing,
    )
    locus_index = {locus: index for index, locus in enumerate(loci)}

    def _difference_type(left_value: str, right_value: str) -> str:
        left_missing = is_missing(left_value)
        right_missing = is_missing(right_value)
        if left_missing and right_missing:
            return "both_missing"
        if left_missing:
            return "left_missing"
        if right_missing:
            return "right_missing"
        return "allele_difference"

    differences = [
        {
            "locus": locus,
            "left": left_node.profile[locus_index[locus]],
            "right": right_node.profile[locus_index[locus]],
            "type": _difference_type(
                left_node.profile[locus_index[locus]],
                right_node.profile[locus_index[locus]],
            ),
        }
        for locus in mismatch_loci
    ]
    return {
        "left_label": left_label,
        "right_label": right_label,
        "distance": distance,
        "differences": differences,
    }


def build_allele_heatmap_from_tsv(
    tsv_text: str,
    *,
    aggregate_profiles: bool = False,
    metadata_text: str | None = None,
) -> tuple[
    list[str], list[str], list[list[dict[str, str]]], list[dict[str, object]], list[str]
]:
    if not tsv_text.strip():
        raise ValueError("No TSV content provided")

    metadata_by_sample, extra_metadata_fields = _parse_metadata_text(metadata_text)
    nodes, loci, metadata_fields = _parse_rows(
        tsv_text,
        metadata_by_sample=metadata_by_sample,
        extra_metadata_fields=extra_metadata_fields,
    )
    meta_breakdowns = None
    if aggregate_profiles:
        nodes, meta_breakdowns = _aggregate_profiles(nodes)

    payload_nodes = _build_payload(nodes, meta_breakdowns)
    labels = [str(node["label"]) for node in payload_nodes]

    def _state(value: str) -> str:
        return "missing_token" if is_missing(value) else "present_allele"

    cells = [
        [
            {
                "value": node.profile[index],
                "state": _state(node.profile[index]),
            }
            for index in range(len(loci))
        ]
        for node in nodes
    ]
    return labels, loci, cells, payload_nodes, metadata_fields


def build_result_comparison_from_tsv(
    left_tsv: str,
    right_tsv: str,
) -> dict[str, object]:
    if not left_tsv.strip() or not right_tsv.strip():
        raise ValueError("Both left_tsv and right_tsv are required")

    class _ComparisonEntry(TypedDict):
        st: str
        profile: dict[str, str]

    def _sample_to_profile(tsv_text: str) -> dict[str, _ComparisonEntry]:
        reader = csv.DictReader(
            io.StringIO(tsv_text), delimiter=_sniff_delimiter(tsv_text)
        )
        if not reader.fieldnames:
            raise ValueError("TSV must include a header")
        fieldnames = list(reader.fieldnames)
        if "ST" not in fieldnames:
            raise ValueError("TSV must include an ST column")
        sample_key = _sample_key_for(fieldnames)
        loci = [
            name
            for name in fieldnames
            if name not in META_COLUMNS and name != sample_key
        ]
        mapping: dict[str, _ComparisonEntry] = {}
        for row in reader:
            sample = str(row.get(sample_key, "")).strip()
            if not sample:
                continue
            if sample in mapping:
                raise ValueError(f"Duplicate sample ID in comparison input: {sample}")
            mapping[sample] = {
                "st": str(row.get("ST", "")).strip(),
                "profile": {locus: str(row.get(locus, "")).strip() for locus in loci},
            }
        return mapping

    left_map = _sample_to_profile(left_tsv)
    right_map = _sample_to_profile(right_tsv)
    all_samples = sorted(set(left_map) | set(right_map))

    rows: list[dict[str, object]] = []
    summary = {
        "matched_samples": 0,
        "same_st": 0,
        "different_st": 0,
        "samples_with_locus_differences": 0,
        "left_only": 0,
        "right_only": 0,
    }
    for sample_id in all_samples:
        left_entry = left_map.get(sample_id)
        right_entry = right_map.get(sample_id)
        left_st = str(left_entry["st"]) if left_entry else ""
        right_st = str(right_entry["st"]) if right_entry else ""
        differing_loci_count = 0
        if left_entry is not None and right_entry is not None:
            summary["matched_samples"] += 1
            if left_st == right_st:
                status = "same_st"
                summary["same_st"] += 1
            else:
                status = "different_st"
                summary["different_st"] += 1

            left_profile = cast(dict[str, str], left_entry["profile"])
            right_profile = cast(dict[str, str], right_entry["profile"])
            differing_loci_count = sum(
                1
                for locus in set(left_profile) | set(right_profile)
                if str(left_profile.get(locus, "")) != str(right_profile.get(locus, ""))
            )
            if differing_loci_count > 0:
                summary["samples_with_locus_differences"] += 1
        elif left_entry is not None:
            status = "left_only"
            summary["left_only"] += 1
        else:
            status = "right_only"
            summary["right_only"] += 1
        rows.append(
            {
                "sample_id": sample_id,
                "left_st": left_st,
                "right_st": right_st,
                "status": status,
                "differing_loci_count": differing_loci_count,
            }
        )

    return {"summary": summary, "rows": rows}
