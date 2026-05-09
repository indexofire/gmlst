from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _first_present(columns: list[str], candidates: list[str]) -> str:
    lowered = {name.lower(): name for name in columns}
    for candidate in candidates:
        key = candidate.lower()
        if key in lowered:
            return lowered[key]
    raise ValueError(f"Missing required column; expected one of {candidates}")


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
        if not reader.fieldnames:
            raise ValueError(f"Empty or invalid TSV: {path}")
    return rows


def _as_int(value: str) -> int:
    return int(value.strip())


def _normalize_strand(value: str) -> str:
    cleaned = value.strip()
    if cleaned in {"1", "+1", "+"}:
        return "+"
    if cleaned in {"-1", "-"}:
        return "-"
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gmlst", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=False, type=Path)
    args = parser.parse_args()

    gmlst_rows = _load_rows(args.gmlst)
    ref_rows = _load_rows(args.reference)

    gmlst_fields = list(gmlst_rows[0].keys()) if gmlst_rows else []
    ref_fields = list(ref_rows[0].keys()) if ref_rows else []

    g_contig = _first_present(gmlst_fields, ["contig_id", "contig", "genome"])
    g_start = _first_present(gmlst_fields, ["start", "begin"])
    g_end = _first_present(gmlst_fields, ["end", "stop"])
    g_strand = _first_present(
        gmlst_fields,
        ["strand", "direction", "coding_strand"],
    )

    r_contig = _first_present(
        ref_fields,
        ["contig_id", "contig", "genome", "Contig", "Genome"],
    )
    r_start = _first_present(ref_fields, ["start", "begin"])
    r_end = _first_present(ref_fields, ["end", "stop"])
    r_strand = _first_present(
        ref_fields,
        ["strand", "direction", "coding_strand", "Coding_Strand"],
    )

    ref_index: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for row in ref_rows:
        key = (row[r_contig], _normalize_strand(row[r_strand]))
        ref_index.setdefault(key, []).append(
            (_as_int(row[r_start]), _as_int(row[r_end]))
        )

    exact = 0
    same_stop_diff_start = 0
    same_start_diff_stop = 0
    overlap_only = 0
    no_overlap = 0
    detail_rows: list[list[str]] = []

    for row in gmlst_rows:
        contig = row[g_contig]
        strand = _normalize_strand(row[g_strand])
        start = _as_int(row[g_start])
        end = _as_int(row[g_end])
        key = (contig, strand)
        candidates = ref_index.get(key, [])

        relation = "no_overlap"
        for ref_start, ref_end in candidates:
            if start == ref_start and end == ref_end:
                relation = "exact"
                break
            if end == ref_end and start != ref_start:
                relation = "same_stop_diff_start"
            elif start == ref_start and end != ref_end:
                if relation != "same_stop_diff_start":
                    relation = "same_start_diff_stop"
            elif not (end < ref_start or ref_end < start) and relation not in {
                "same_stop_diff_start",
                "same_start_diff_stop",
            }:
                relation = "overlap_only"

        if relation == "exact":
            exact += 1
        elif relation == "same_stop_diff_start":
            same_stop_diff_start += 1
        elif relation == "same_start_diff_stop":
            same_start_diff_stop += 1
        elif relation == "overlap_only":
            overlap_only += 1
        else:
            no_overlap += 1

        detail_rows.append(
            [
                row.get("sample_id", ""),
                row.get("gene_id", ""),
                contig,
                str(start),
                str(end),
                strand,
                relation,
            ]
        )

    print(f"gmlst_rows\t{len(gmlst_rows)}")
    print(f"reference_rows\t{len(ref_rows)}")
    print(f"exact\t{exact}")
    print(f"same_stop_diff_start\t{same_stop_diff_start}")
    print(f"same_start_diff_stop\t{same_start_diff_stop}")
    print(f"overlap_only\t{overlap_only}")
    print(f"no_overlap\t{no_overlap}")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(
                [
                    "sample_id",
                    "gene_id",
                    "contig_id",
                    "start",
                    "end",
                    "strand",
                    "relation",
                ]
            )
            writer.writerows(detail_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
