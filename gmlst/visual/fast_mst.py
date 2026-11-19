"""Packed fast path for large profile tables (numpy + numba).

The regular pipeline stores every allele as a Python string, which is fine
for a few hundred samples but costs gigabytes at 10k x 3k. This module parses
the table straight into integer codes (one byte per locus, 0 = missing),
computes pairwise distances with a fused numba kernel, and builds the MST with
Prim's algorithm so the 50M-edge list is never materialised.

The public entry point is :func:`build_fast_mst`, which mirrors the return
contract of :func:`gmlst.visual.mst.build_mst_from_tsv`.
"""

from __future__ import annotations

import hashlib
from array import array
from dataclasses import dataclass
from typing import Any

import numpy as np

from gmlst.visual.mst_shared import (
    META_COLUMNS,
    _detect_non_allele_columns,
    _merge_metadata,
    _metadata_fields_for,
    _parse_metadata_text,
    _sample_key_for,
    _sniff_delimiter,
    is_missing,
    normalize_allele,
)

#: Inputs at or above this size use the packed + numba path.
FAST_PATH_CELLS = 750_000
#: Inputs with at least this many samples also use the fast path (n^2 work).
FAST_PATH_SAMPLES = 2_500
#: Above this many MST nodes the per-edge mismatch locus lists are omitted
#: from the payload; the UI queries them on demand.
PAYLOAD_LOCI_NODES = 2_000

_NUMBA_BLOCK = 8


def _import_numba() -> Any:
    try:
        import numba  # noqa: PLC0415 - optional at import time
    except Exception:  # pragma: no cover - only when numba is unavailable
        return None
    return numba


_NUMBA = _import_numba()


@dataclass(frozen=True)
class PackedTable:
    """Profiles packed into integer codes.

    ``codes[i, k]`` is the allele code of sample *i* at locus *k*; ``0``
    means the call is missing. ``tokens[k]`` maps codes back to the
    normalised token (index 0 is the empty missing token).
    """

    labels: list[str]
    loci: list[str]
    codes: np.ndarray
    metadata: list[dict[str, str]]
    profile_keys: list[str]
    tokens: list[tuple[str, ...]]
    metadata_fields: list[str]


def _register_token(
    tokens: list[str],
    by_raw: dict[str, int],
    by_normalised: dict[str, int],
    raw: str,
) -> int:
    """Return the code for *raw*, adding it to the locus tables on first use.

    Call decorations are stripped before the lookup, so ``105`` and ``~105``
    share one code — otherwise identical profiles would not aggregate.
    """
    token = raw.strip()
    if is_missing(token):
        by_raw[raw] = 0
        return 0
    normalised = normalize_allele(token)
    # Decoration-only calls ("~", "?", ...) normalise to an empty token and
    # count as missing everywhere else in the pipeline; keep them code 0 so
    # aggregation and distances match the string-based path.
    if not normalised or is_missing(normalised):
        by_raw[raw] = 0
        return 0
    code = by_normalised.get(normalised)
    if code is None:
        code = len(tokens)
        by_normalised[normalised] = code
        tokens.append(normalised)
    by_raw[raw] = code
    return code


def parse_packed_table(
    tsv_text: str,
    metadata_text: str | None,
) -> PackedTable:
    """Parse profile TSV text into integer codes without keeping strings."""
    if not tsv_text.strip():
        raise ValueError("No TSV content provided")

    metadata_by_sample, extra_metadata_fields = _parse_metadata_text(metadata_text)
    delimiter = _sniff_delimiter(tsv_text)
    lines = tsv_text.splitlines()
    if not lines:
        raise ValueError("TSV must include a header")
    header = lines[0].split(delimiter)
    sample_key = _sample_key_for(header)
    sample_index = header.index(sample_key)
    locus_indexes = [
        index
        for index, name in enumerate(header)
        if name not in META_COLUMNS and index != sample_index
    ]
    metadata_fields = _metadata_fields_for(header, sample_key)
    metadata_fields.extend(
        field for field in extra_metadata_fields if field not in metadata_fields
    )

    # Auto-detect free-text columns hiding among the loci, using a bounded
    # sample so a 10k-row table is never materialised as dicts.
    peek: list[dict[str, str]] = []
    for line in lines[1:201]:
        cells = line.split(delimiter)
        peek.append(
            {
                header[index]: cells[index] if index < len(cells) else ""
                for index in range(len(header))
            }
        )
    locus_names = [header[index] for index in locus_indexes]
    auto_meta = _detect_non_allele_columns(peek, locus_names)
    if auto_meta:
        locus_indexes = [
            index for index in locus_indexes if header[index] not in auto_meta
        ]
        metadata_fields.extend(
            name for name in sorted(auto_meta) if name not in metadata_fields
        )
    if not locus_indexes:
        raise ValueError("No locus columns detected in TSV")

    meta_indexes = [
        (name, header.index(name))
        for name in metadata_fields
        if name in header and header.index(name) != sample_index
    ]

    locus_count = len(locus_indexes)
    tokens: list[list[str]] = [[""] for _ in range(locus_count)]
    mappings: list[dict[str, int]] = [{} for _ in range(locus_count)]
    normalised_maps: list[dict[str, int]] = [{} for _ in range(locus_count)]
    columns: list[array] = [array("H") for _ in range(locus_count)]

    labels: list[str] = []
    metadata: list[dict[str, str]] = []
    seen: set[str] = set()

    for line in lines[1:]:
        cells = line.split(delimiter)
        if not cells or not any(cell.strip() for cell in cells):
            continue
        label = cells[sample_index].strip() if sample_index < len(cells) else ""
        if not label:
            continue
        if label in seen:
            raise ValueError(f"Duplicate sample ID: {label!r}")
        seen.add(label)
        row_metadata = {
            name: cells[index].strip()
            for name, index in meta_indexes
            if index < len(cells) and cells[index].strip()
        }
        row_metadata = _merge_metadata(
            row_metadata,
            metadata_by_sample.get(label, {}),
        )
        labels.append(label)
        metadata.append(row_metadata)

        for locus in range(locus_count):
            index = locus_indexes[locus]
            raw = cells[index] if index < len(cells) else ""
            code = mappings[locus].get(raw)
            if code is None:
                code = _register_token(
                    tokens[locus],
                    mappings[locus],
                    normalised_maps[locus],
                    raw,
                )
            columns[locus].append(code)

    if not labels:
        raise ValueError("No sample rows found")

    max_code = max(len(locus) - 1 for locus in tokens)
    dtype = np.uint8 if max_code <= 255 else np.uint16
    codes = np.empty((len(labels), locus_count), dtype=dtype)
    for locus in range(locus_count):
        codes[:, locus] = np.frombuffer(columns[locus], dtype=np.uint16).astype(
            dtype, copy=False
        )

    profile_keys = [
        hashlib.blake2b(codes[index].tobytes(), digest_size=16).hexdigest()
        for index in range(len(labels))
    ]

    return PackedTable(
        labels=labels,
        loci=[header[index] for index in locus_indexes],
        codes=codes,
        metadata=metadata,
        profile_keys=profile_keys,
        tokens=[tuple(locus) for locus in tokens],
        metadata_fields=metadata_fields,
    )


def _numba_kernel(numba: Any) -> Any:
    @numba.njit(parallel=True, cache=False, boundscheck=False, nogil=True)
    def kernel(codes: np.ndarray, out: np.ndarray, block: int) -> None:
        n, locus_count = codes.shape
        blocks = (n + block - 1) // block
        for block_index in numba.prange(blocks):
            start = block_index * block
            stop = min(start + block, n)
            for left in range(start, stop):
                left_codes = codes[left]
                for right in range(left + 1, n):
                    right_codes = codes[right]
                    differences = 0
                    comparable = 0
                    for locus in range(locus_count):
                        a = left_codes[locus]
                        b = right_codes[locus]
                        if a and b:
                            comparable += 1
                            if a != b:
                                differences += 1
                    value = (differences + 0.01) * locus_count / (comparable + 0.01)
                    out[left, right] = value
                    out[right, left] = value

    return kernel


_KERNEL_CACHE: dict[int, Any] = {}


def _distance_matrix(codes: np.ndarray) -> np.ndarray:
    """Pairwise missing-aware Hamming-style distance matrix (float32)."""
    n = int(codes.shape[0])
    out = np.zeros((n, n), dtype=np.float32)
    if n <= 1:
        return out
    if _NUMBA is not None:
        key = int(codes.dtype.itemsize)
        kernel = _KERNEL_CACHE.get(key)
        if kernel is None:
            kernel = _numba_kernel(_NUMBA)
            _KERNEL_CACHE[key] = kernel
        kernel(codes, out, _NUMBA_BLOCK)
        return out

    # Fallback without numba: row-by-row numpy. Much slower but correct.
    locus_count = int(codes.shape[1])
    for row in range(n - 1):
        left_codes = codes[row]
        others = codes[row + 1 :]
        both = (left_codes[None, :] != 0) & (others != 0)
        differences = ((left_codes[None, :] != others) & both).sum(axis=1)
        comparable = both.sum(axis=1)
        values = (differences + 0.01) * locus_count / (comparable + 0.01)
        out[row, row + 1 :] = values
        out[row + 1 :, row] = values
    return out


def _eburst_weights(
    dist: np.ndarray,
    group_sizes: list[int],
    max_bins: int = 32,
) -> np.ndarray:
    """eBURST-style ranks from capped distance histograms.

    The exact implementation uses one bin per observed distance; capping the
    bins keeps the ranking cheap on 10k-node graphs. Ties are broken by
    sample size and then array order, deterministically.
    """
    n = int(dist.shape[0])
    if n <= 1:
        return np.zeros(n, dtype=np.float32)
    dist_int = np.rint(dist).astype(np.int32)
    bins = int(min(max_bins, int(dist_int.max())))
    counts = np.zeros((bins + 1, n), dtype=np.int32)
    for index in range(n):
        counts[:, index] = np.bincount(dist_int[index], minlength=bins + 1)[: bins + 1]
    counts[0] = np.asarray(group_sizes, dtype=np.int32)
    keys = [-counts[0]]
    keys.extend(-counts[bin_index] for bin_index in range(bins, 0, -1))
    order = np.lexsort(tuple(keys))
    weights = np.empty(n, dtype=np.float32)
    weights[order] = np.arange(n, dtype=np.float32) / n
    return weights


def _prim_mst(cost: np.ndarray) -> np.ndarray:
    """Prim's MST over a dense cost matrix; returns the parent of each node."""
    n = int(cost.shape[0])
    parent = np.full(n, -1, dtype=np.int32)
    if n <= 1:
        return parent
    in_tree = np.zeros(n, dtype=bool)
    best = np.full(n, np.inf, dtype=np.float32)
    best[0] = 0.0
    for _ in range(n):
        node = int(np.argmin(best))
        in_tree[node] = True
        best[node] = np.inf
        row = cost[node]
        better = (~in_tree) & (row < best)
        best[better] = row[better]
        parent[better] = node
    return parent


def _group_profiles(table: PackedTable) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for index, key in enumerate(table.profile_keys):
        groups.setdefault(key, []).append(index)
    return groups


def _merge_group_metadata(
    members: list[dict[str, str]],
) -> tuple[dict[str, str], dict[str, dict[str, int]]]:
    merged = dict(members[0])
    extras: dict[str, list[str]] = {}
    for metadata in members:
        for key, value in metadata.items():
            if not value:
                continue
            values = extras.setdefault(key, [])
            if value not in values:
                values.append(value)
    for key, values in extras.items():
        merged[key] = " | ".join(values)
    breakdown: dict[str, dict[str, int]] = {}
    for metadata in members:
        for key, value in metadata.items():
            if not value:
                continue
            counts = breakdown.setdefault(key, {})
            counts[value] = counts.get(value, 0) + 1
    return merged, breakdown


def _payload_node(
    *,
    label: str,
    metadata: dict[str, str],
    breakdown: dict[str, dict[str, int]],
    profile_key: str,
    members: list[str],
) -> dict[str, object]:
    return {
        "id": 0,
        "label": label,
        "meta": metadata,
        "meta_breakdown": breakdown,
        "profile_key": profile_key,
        "member_count": len(members),
        "members": members,
    }


def _edge_payload(
    table: PackedTable,
    source: int,
    target: int,
    source_label: str,
    target_label: str,
    *,
    include_missing: bool,
    with_loci: bool,
) -> dict[str, object]:
    codes = table.codes
    source_codes = codes[source]
    target_codes = codes[target]
    source_missing = source_codes == 0
    target_missing = target_codes == 0
    both_present = ~source_missing & ~target_missing
    differing = both_present & (source_codes != target_codes)
    one_missing = source_missing ^ target_missing
    weight = int(differing.sum())
    if include_missing:
        weight += int(one_missing.sum())

    asymmetric = (~target_missing & (source_missing | differing)) | (
        include_missing & ~source_missing & target_missing
    )
    asymmetric_weight = int(asymmetric.sum())

    mismatch_loci: list[str] = []
    asymmetric_loci: list[str] = []
    if with_loci:
        for locus in np.flatnonzero(differing):
            mismatch_loci.append(table.tokens[int(locus)][int(source_codes[locus])])
        if include_missing:
            for locus in np.flatnonzero(one_missing):
                code = int(source_codes[locus] or target_codes[locus])
                mismatch_loci.append(table.tokens[int(locus)][code])
        for locus in np.flatnonzero(asymmetric):
            code = (
                int(source_codes[locus])
                if both_present[locus]
                else int(target_codes[locus])
            )
            asymmetric_loci.append(table.tokens[int(locus)][code])

    return {
        "source": source,
        "target": target,
        "weight": weight,
        "asymmetric_weight": asymmetric_weight,
        "source_label": source_label,
        "target_label": target_label,
        "mismatch_count": weight,
        "mismatch_loci": mismatch_loci,
        "asymmetric_mismatch_loci": asymmetric_loci,
    }


def build_fast_mst(
    tsv_text: str,
    *,
    metadata_text: str | None = None,
    include_missing: bool = False,
    aggregate_profiles: bool = True,
    max_nodes: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    """Build the MST for a large profile table using the packed path."""
    table = parse_packed_table(tsv_text, metadata_text)
    groups = _group_profiles(table)
    group_keys = list(groups.keys())
    group_members = [groups[key] for key in group_keys]
    representative_indexes = [members[0] for members in group_members]
    codes = table.codes[representative_indexes]

    node_count = len(group_members) if aggregate_profiles else len(table.labels)
    if max_nodes is not None and node_count > max_nodes:
        raise ValueError(
            "too many nodes for MST method 'grapetree_classic': "
            f"{len(table.labels)} > {max_nodes}; use a cheaper method or fewer samples"
        )

    distances = _distance_matrix(codes)
    weights = _eburst_weights(
        distances,
        [len(members) for members in group_members],
    )
    costs = distances
    np.rint(costs, out=costs)
    for start in range(0, costs.shape[0], 512):
        stop = min(start + 512, costs.shape[0])
        costs[start:stop] += (weights[start:stop, None] + weights[None, :]) / 2.0
    parents = _prim_mst(costs)

    with_loci = len(group_members) <= PAYLOAD_LOCI_NODES

    nodes: list[dict[str, object]] = []
    if aggregate_profiles:
        records: list[tuple[str, str, int, dict[str, object]]] = []
        for group_index, members in enumerate(group_members):
            labels = [table.labels[index] for index in members]
            label = (
                labels[0] if len(labels) == 1 else f"{labels[0]} (+{len(labels) - 1})"
            )
            merged, breakdown = _merge_group_metadata(
                [table.metadata[index] for index in members]
            )
            if len(labels) > 1:
                merged.setdefault("duplicates", str(len(labels)))
            node = _payload_node(
                label=label,
                metadata=merged,
                breakdown=breakdown,
                profile_key=group_keys[group_index],
                members=labels,
            )
            records.append((label.lower(), group_keys[group_index], group_index, node))
        records.sort(key=lambda item: (item[0], item[1]))
        nodes = [record[3] for record in records]
        payload_index = {record[2]: position for position, record in enumerate(records)}
    else:
        payload_index = {}
        for group_index, members in enumerate(group_members):
            representative_id = len(nodes)
            payload_index[group_index] = representative_id
            first = members[0]
            nodes.append(
                _payload_node(
                    label=table.labels[first],
                    metadata=table.metadata[first],
                    breakdown={
                        key: {value: 1}
                        for key, value in table.metadata[first].items()
                        if value
                    },
                    profile_key=group_keys[group_index],
                    members=[table.labels[first]],
                )
            )
            for duplicate in members[1:]:
                nodes.append(
                    _payload_node(
                        label=table.labels[duplicate],
                        metadata=table.metadata[duplicate],
                        breakdown={
                            key: {value: 1}
                            for key, value in table.metadata[duplicate].items()
                            if value
                        },
                        profile_key=group_keys[group_index],
                        members=[table.labels[duplicate]],
                    )
                )

    for index, node in enumerate(nodes):
        node["id"] = index

    edges: list[dict[str, object]] = []
    for child in range(1, len(group_members)):
        parent = int(parents[child])
        if parent < 0:
            continue
        edge = _edge_payload(
            table,
            representative_indexes[parent],
            representative_indexes[child],
            table.labels[representative_indexes[parent]],
            table.labels[representative_indexes[child]],
            include_missing=include_missing,
            with_loci=with_loci,
        )
        edge["source"] = payload_index[parent]
        edge["target"] = payload_index[child]
        edges.append(edge)

    if not aggregate_profiles:
        for group_index, members in enumerate(group_members):
            representative_id = payload_index[group_index]
            for offset, duplicate in enumerate(members[1:], start=1):
                duplicate_id = representative_id + offset
                edges.append(
                    {
                        "source": representative_id,
                        "target": duplicate_id,
                        "weight": 0,
                        "asymmetric_weight": 0,
                        "source_label": table.labels[members[0]],
                        "target_label": table.labels[duplicate],
                        "mismatch_count": 0,
                        "mismatch_loci": [],
                        "asymmetric_mismatch_loci": [],
                    }
                )

    if len(nodes) > 1 and len(edges) != len(nodes) - 1:
        raise ValueError("MST must contain exactly n-1 edges")
    return nodes, edges, table.metadata_fields
