from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import cast

META_COLUMNS = {
    "FILE",
    "SCHEME",
    "ST",
    "sample_id",
    "SAMPLE",
    "Sample",
    "backend",
    "runtime_seconds",
    "call_policy",
}

MISSING_TOKENS = {
    "",
    "-",
    "LNF",
    "NIPH",
    "NIPHEM",
    "ASM",
    "ALM",
    "PLOT3",
    "PLOT5",
    "LOTSC",
    "PAMA",
    "PLNF",
}

_MAX_SAMPLE_COUNT = 5000
_MAX_LOCI_COUNT = 5000


@dataclass(frozen=True)
class MstNode:
    label: str
    profile: tuple[str, ...]
    metadata: dict[str, str]
    members: tuple[str, ...]
    profile_key: str


@dataclass(frozen=True)
class DirectedEdge:
    source: int
    target: int
    weight: int
    asymmetric_weight: int
    combined_weight: float
    source_label: str
    target_label: str
    mismatch_loci: tuple[str, ...]
    asymmetric_mismatch_loci: tuple[str, ...]


def validate_tsv_scale(tsv_text: str) -> None:
    lines = tsv_text.strip().splitlines()
    if not lines:
        return
    header_cols = lines[0].split("\t")
    loci_count = max(len(header_cols) - 1, 0)
    sample_count = max(len(lines) - 1, 0)
    if sample_count > _MAX_SAMPLE_COUNT:
        raise ValueError(f"Too many samples: {sample_count} (max {_MAX_SAMPLE_COUNT})")
    if loci_count > _MAX_LOCI_COUNT:
        raise ValueError(f"Too many loci: {loci_count} (max {_MAX_LOCI_COUNT})")


def _resolved_allele_count(profile: tuple[str, ...]) -> int:
    return sum(0 if is_missing(value) else 1 for value in profile)


def normalize_allele(value: str | None) -> str:
    cleaned = (value or "").strip()
    if cleaned.startswith("~"):
        cleaned = cleaned[1:]
    if cleaned.endswith("?"):
        cleaned = cleaned[:-1]
    if cleaned.startswith("INF-"):
        cleaned = cleaned[4:]
    return cleaned


def is_missing(value: str | None) -> bool:
    token = (value or "").strip().upper()
    return token in MISSING_TOKENS


def _profile_difference(
    left: tuple[str, ...],
    right: tuple[str, ...],
    loci: list[str],
    *,
    include_missing: bool,
) -> tuple[int, list[str]]:
    distance = 0
    mismatch_loci: list[str] = []
    for locus, left_value, right_value in zip(loci, left, right, strict=True):
        left_missing = is_missing(left_value)
        right_missing = is_missing(right_value)
        if left_missing or right_missing:
            if include_missing and left_missing != right_missing:
                distance += 1
                mismatch_loci.append(locus)
            continue
        if left_value != right_value:
            distance += 1
            mismatch_loci.append(locus)
    return distance, mismatch_loci


def _asymmetric_profile_difference(
    source: tuple[str, ...],
    target: tuple[str, ...],
    loci: list[str],
    *,
    include_missing: bool,
) -> tuple[int, list[str]]:
    distance = 0
    mismatch_loci: list[str] = []
    for locus, source_value, target_value in zip(loci, source, target, strict=True):
        source_missing = is_missing(source_value)
        target_missing = is_missing(target_value)
        if source_missing and target_missing:
            continue
        if source_missing and not target_missing:
            distance += 1
            mismatch_loci.append(locus)
            continue
        if not source_missing and target_missing:
            if include_missing:
                distance += 1
                mismatch_loci.append(locus)
            continue
        if source_value != target_value:
            distance += 1
            mismatch_loci.append(locus)
    return distance, mismatch_loci


def profile_distance(
    left: tuple[str, ...],
    right: tuple[str, ...],
    *,
    include_missing: bool,
) -> int:
    distance = 0
    for left_value, right_value in zip(left, right, strict=True):
        left_missing = is_missing(left_value)
        right_missing = is_missing(right_value)
        if left_missing or right_missing:
            if include_missing and left_missing != right_missing:
                distance += 1
            continue
        if left_value != right_value:
            distance += 1
    return distance


def asymmetric_profile_distance(
    source: tuple[str, ...],
    target: tuple[str, ...],
    *,
    include_missing: bool,
) -> int:
    distance = 0
    for source_value, target_value in zip(source, target, strict=True):
        source_missing = is_missing(source_value)
        target_missing = is_missing(target_value)
        if source_missing and target_missing:
            continue
        if source_missing and not target_missing:
            distance += 1
            continue
        if not source_missing and target_missing:
            if include_missing:
                distance += 1
            continue
        if source_value != target_value:
            distance += 1
    return distance


def _sample_key_for(fieldnames: list[str]) -> str:
    if "FILE" in fieldnames:
        return "FILE"
    return fieldnames[0]


def _metadata_fields_for(fieldnames: list[str], sample_key: str) -> list[str]:
    return [name for name in fieldnames if name in META_COLUMNS and name != sample_key]


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join(line for line in text.splitlines()[:10] if line.strip())
    if not sample:
        return "\t"
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except csv.Error:
        if "," in sample and "\t" not in sample:
            return ","
        return "\t"


def _parse_metadata_text(
    metadata_text: str | None,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    if metadata_text is None or not metadata_text.strip():
        return {}, []

    delimiter = _sniff_delimiter(metadata_text)
    reader = csv.DictReader(io.StringIO(metadata_text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("Metadata must include a header")

    fieldnames = list(reader.fieldnames)
    sample_key = "ID" if "ID" in fieldnames else fieldnames[0]
    metadata_fields = [name for name in fieldnames if name != sample_key]
    metadata_by_sample: dict[str, dict[str, str]] = {}
    for row in reader:
        sample = row.get(sample_key, "").strip()
        if not sample:
            continue
        metadata_by_sample[sample] = {
            field: row.get(field, "").strip()
            for field in metadata_fields
            if row.get(field, "").strip()
        }
    return metadata_by_sample, metadata_fields


def _merge_metadata(
    base: dict[str, str],
    extra: dict[str, str],
) -> dict[str, str]:
    merged = dict(base)
    for key, value in extra.items():
        if value:
            merged[key] = value
    return merged


def _parse_rows(
    tsv_text: str,
    *,
    metadata_by_sample: dict[str, dict[str, str]],
    extra_metadata_fields: list[str],
) -> tuple[list[MstNode], list[str], list[str]]:
    delimiter = _sniff_delimiter(tsv_text)
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("TSV must include a header")

    fieldnames = list(reader.fieldnames)
    sample_key = _sample_key_for(fieldnames)
    loci = [
        name for name in fieldnames if name not in META_COLUMNS and name != sample_key
    ]
    metadata_fields = _metadata_fields_for(fieldnames, sample_key)
    metadata_fields.extend(
        field for field in extra_metadata_fields if field not in metadata_fields
    )
    if not loci:
        raise ValueError("No locus columns detected in TSV")

    nodes: list[MstNode] = []
    for row in reader:
        sample = row.get(sample_key, "").strip()
        if not sample:
            continue
        profile = tuple(normalize_allele(row.get(locus, "")) for locus in loci)
        metadata = {
            field: row.get(field, "").strip()
            for field in metadata_fields
            if field in row and row.get(field, "").strip()
        }
        metadata = _merge_metadata(metadata, metadata_by_sample.get(sample, {}))
        profile_key = "|".join(profile)
        nodes.append(
            MstNode(
                label=sample,
                profile=profile,
                metadata=metadata,
                members=(sample,),
                profile_key=profile_key,
            )
        )

    seen_labels: set[str] = set()
    for node in nodes:
        label = node.label
        if label in seen_labels:
            raise ValueError(f"Duplicate sample ID: {label!r}")
        seen_labels.add(label)

    if not nodes:
        raise ValueError("No sample rows found")
    return nodes, loci, metadata_fields


def _build_meta_breakdown(nodes: list[MstNode]) -> dict[str, dict[str, int]]:
    meta_breakdown: dict[str, dict[str, int]] = {}
    all_keys: set[str] = set()
    for node in nodes:
        all_keys.update(node.metadata)

    for key in all_keys:
        value_counts: dict[str, int] = {}
        for node in nodes:
            value = node.metadata.get(key, "")
            if value:
                value_counts[value] = value_counts.get(value, 0) + 1
        meta_breakdown[key] = value_counts
    return meta_breakdown


def _aggregate_profiles(
    nodes: list[MstNode],
) -> tuple[list[MstNode], dict[tuple[str, ...], dict[str, dict[str, int]]]]:
    grouped: dict[str, list[MstNode]] = {}
    for node in nodes:
        grouped.setdefault(node.profile_key, []).append(node)

    aggregated: list[MstNode] = []
    meta_breakdowns: dict[tuple[str, ...], dict[str, dict[str, int]]] = {}
    for members in grouped.values():
        first = members[0]
        labels = tuple(node.label for node in members)
        label = (
            first.label if len(labels) == 1 else f"{first.label} (+{len(labels) - 1})"
        )
        metadata = dict(first.metadata)
        extra_values: dict[str, list[str]] = {}
        for member in members:
            for key, value in member.metadata.items():
                if not value:
                    continue
                extra_values.setdefault(key, [])
                if value not in extra_values[key]:
                    extra_values[key].append(value)
        for key, values in extra_values.items():
            metadata[key] = " | ".join(values)
        if len(labels) > 1:
            metadata.setdefault("duplicates", str(len(labels)))
        meta_breakdowns[labels] = _build_meta_breakdown(members)
        aggregated.append(
            MstNode(
                label=label,
                profile=first.profile,
                metadata=metadata,
                members=labels,
                profile_key=first.profile_key,
            )
        )

    aggregated.sort(key=lambda node: (node.label.lower(), node.profile_key))
    return aggregated, meta_breakdowns


def _group_profiles(nodes: list[MstNode]) -> list[list[MstNode]]:
    grouped: dict[str, list[MstNode]] = {}
    for node in nodes:
        grouped.setdefault(node.profile_key, []).append(node)
    return list(grouped.values())


def _build_payload(
    nodes: list[MstNode],
    meta_breakdowns: dict[tuple[str, ...], dict[str, dict[str, int]]] | None = None,
) -> list[dict[str, object]]:
    return [
        {
            "id": index,
            "label": node.label,
            "meta": node.metadata,
            "meta_breakdown": (
                meta_breakdowns.get(node.members)
                if meta_breakdowns is not None and node.members in meta_breakdowns
                else _build_meta_breakdown([node])
            ),
            "profile_key": node.profile_key,
            "member_count": len(node.members),
            "members": list(node.members),
        }
        for index, node in enumerate(nodes)
    ]


def _restore_duplicate_leaves(
    nodes: list[MstNode],
    loci: list[str],
    *,
    include_missing: bool,
) -> tuple[list[MstNode], list[dict[str, object]]]:
    from gmlst.visual.mst_edmonds import build_edmonds_mst

    grouped_profiles = _group_profiles(nodes)
    representative_nodes = [members[0] for members in grouped_profiles]

    representative_edges = build_edmonds_mst(
        representative_nodes,
        loci,
        include_missing=include_missing,
    )

    payload_nodes: list[MstNode] = []
    representative_payload_ids: list[int] = []
    duplicate_edges: list[dict[str, object]] = []

    for members in grouped_profiles:
        representative = members[0]
        representative_payload_id = len(payload_nodes)
        representative_payload_ids.append(representative_payload_id)
        payload_nodes.append(representative)

        for duplicate in members[1:]:
            duplicate_payload_id = len(payload_nodes)
            payload_nodes.append(duplicate)
            duplicate_edges.append(
                {
                    "source": representative_payload_id,
                    "target": duplicate_payload_id,
                    "weight": 0,
                    "asymmetric_weight": 0,
                    "source_label": representative.label,
                    "target_label": duplicate.label,
                    "mismatch_count": 0,
                    "mismatch_loci": [],
                    "asymmetric_mismatch_loci": [],
                }
            )

    payload_edges: list[dict[str, object]] = []
    for edge in representative_edges:
        source = int(cast(int | str, edge["source"]))
        target = int(cast(int | str, edge["target"]))
        payload_edges.append(
            {
                **edge,
                "source": representative_payload_ids[source],
                "target": representative_payload_ids[target],
            }
        )
    payload_edges.extend(duplicate_edges)
    return payload_nodes, payload_edges


def _validate_mst(
    nodes: list[MstNode],
    edges: list[dict[str, object]],
    loci: list[str],
    *,
    include_missing: bool,
) -> None:
    node_count = len(nodes)
    if node_count <= 1:
        if edges:
            raise ValueError("Single-node MST must not contain edges")
        return
    if len(edges) != node_count - 1:
        raise ValueError("MST must contain exactly n-1 edges")

    adjacency: dict[int, list[int]] = {index: [] for index in range(node_count)}
    for edge in edges:
        source = int(cast(int | str, edge["source"]))
        target = int(cast(int | str, edge["target"]))
        if source == target:
            raise ValueError("MST cannot contain self-loops")
        if source not in adjacency or target not in adjacency:
            raise ValueError("MST edge references unknown node")
        adjacency[source].append(target)
        adjacency[target].append(source)

        expected_weight, expected_loci = _profile_difference(
            nodes[source].profile,
            nodes[target].profile,
            loci,
            include_missing=include_missing,
        )
        expected_asymmetric_weight, expected_asymmetric_loci = (
            _asymmetric_profile_difference(
                nodes[source].profile,
                nodes[target].profile,
                loci,
                include_missing=include_missing,
            )
        )
        weight = int(cast(int | str, edge["weight"]))
        asymmetric_weight = int(
            cast(int | str, edge.get("asymmetric_weight", expected_asymmetric_weight))
        )
        mismatch_loci = list(cast(list[str], edge.get("mismatch_loci", [])))
        asymmetric_mismatch_loci = list(
            cast(list[str], edge.get("asymmetric_mismatch_loci", []))
        )
        if weight != expected_weight:
            raise ValueError("MST edge weight does not match profile distance")
        if asymmetric_weight != expected_asymmetric_weight:
            raise ValueError(
                "MST edge asymmetric weight does not match profile distance"
            )
        if mismatch_loci != expected_loci:
            raise ValueError("MST edge mismatch loci do not match profile distance")
        if asymmetric_mismatch_loci != expected_asymmetric_loci:
            raise ValueError(
                "MST edge asymmetric mismatch loci do not match profile distance"
            )

    visited: set[int] = set()
    stack = [0]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(
            neighbor for neighbor in adjacency[current] if neighbor not in visited
        )

    if len(visited) != node_count:
        raise ValueError("MST must connect all nodes")
