from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Approximate chewBBACA-style locus classifications from gmlst JSON "
            "(keeps raw allele calls unchanged)."
        )
    )
    parser.add_argument("--gmlst-json", required=True, type=Path)
    parser.add_argument("--scheme-alleles-dir", required=True, type=Path)
    parser.add_argument("--size-threshold", type=float, default=0.2)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=False, type=Path)
    return parser.parse_args()


def _read_fasta_lengths(path: Path) -> list[int]:
    lengths: list[int] = []
    current = 0
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current > 0:
                    lengths.append(current)
                current = 0
            else:
                current += len(line)
    if current > 0:
        lengths.append(current)
    return lengths


def _mode(values: list[int]) -> int:
    counts = Counter(values)
    best = max(counts.items(), key=lambda item: (item[1], -item[0]))
    return best[0]


def _load_locus_length_stats(alleles_dir: Path) -> dict[str, tuple[int, int, int]]:
    stats: dict[str, tuple[int, int, int]] = {}
    for fasta_path in sorted(alleles_dir.glob("*.tfa")) + sorted(
        alleles_dir.glob("*.fasta")
    ):
        locus = fasta_path.stem
        lengths = _read_fasta_lengths(fasta_path)
        if not lengths:
            continue
        stats[locus] = (min(lengths), _mode(lengths), max(lengths))
    return stats


def _contig_position_classification(call: dict[str, object]) -> str | None:
    contig_len = call.get("query_contig_length")
    contig_start = call.get("query_start")
    contig_end = call.get("query_end")
    allele_len = call.get("allele_length")
    allele_start = call.get("allele_start")
    allele_end = call.get("allele_end")
    strand = str(call.get("strand", "+"))

    if not all(
        isinstance(v, int)
        for v in [
            contig_len,
            contig_start,
            contig_end,
            allele_len,
            allele_start,
            allele_end,
        ]
    ):
        return None

    if contig_len < allele_len:
        return "LOTSC"

    contig_left_rest = contig_start
    contig_right_rest = contig_len - contig_end
    allele_left_rest = allele_start
    allele_right_rest = allele_len - allele_end

    if strand == "+":
        if contig_left_rest < allele_left_rest:
            return "PLOT5"
        if contig_right_rest < allele_right_rest:
            return "PLOT3"
    else:
        if contig_right_rest < allele_left_rest:
            return "PLOT5"
        if contig_left_rest < allele_right_rest:
            return "PLOT3"
    return None


def _size_classification(
    call: dict[str, object],
    locus: str,
    stats: dict[str, tuple[int, int, int]],
    size_threshold: float,
) -> str | None:
    if locus not in stats:
        return None

    allele_len_value = call.get("allele_length")
    if not isinstance(allele_len_value, int):
        novel_seq = call.get("novel_sequence")
        if isinstance(novel_seq, str) and novel_seq:
            allele_len_value = len(novel_seq)
        else:
            return None

    mode_len = stats[locus][1]
    low = mode_len - int(mode_len * size_threshold)
    high = mode_len + int(mode_len * size_threshold)
    if allele_len_value < low:
        return "ASM"
    if allele_len_value > high:
        return "ALM"
    return None


def main() -> int:
    args = _parse_args()
    payload = json.loads(args.gmlst_json.read_text())
    if not isinstance(payload, list) or not payload:
        raise ValueError("Expected non-empty list in gmlst JSON output")

    sample = payload[0]
    allele_calls: dict[str, dict[str, object]] = sample["allele_calls"]
    stats = _load_locus_length_stats(args.scheme_alleles_dir)

    rows: list[dict[str, str]] = []
    class_counts: Counter[str] = Counter()

    for locus, call in sorted(allele_calls.items()):
        call_type = str(call.get("call_type", ""))
        allele_id = str(call.get("allele_id") or "")
        multiple_hits = bool(call.get("multiple_hits", False))

        chew_class = "LNF"
        detail = "missing"
        if multiple_hits:
            if call_type == "exact":
                chew_class = "NIPHEM"
                detail = "multiple_exact_hits"
            else:
                chew_class = "NIPH"
                detail = "multiple_nonexact_hits"
        elif call_type == "missing":
            chew_class = "LNF"
            detail = "missing"
        elif call_type == "exact":
            chew_class = allele_id
            detail = "exact_numeric"
        else:
            pos_class = _contig_position_classification(call)
            if pos_class is not None:
                chew_class = pos_class
                detail = "contig_boundary_rule"
            else:
                size_class = _size_classification(
                    call, locus, stats, args.size_threshold
                )
                if size_class is not None:
                    chew_class = size_class
                    detail = "size_threshold_rule"
                elif call_type in {"closest", "novel"}:
                    chew_class = f"INF-{allele_id}" if allele_id else "INF"
                    detail = "inferred_non_exact"
                elif call_type == "partial":
                    chew_class = "LNF"
                    detail = "partial_without_boundary_evidence"
                else:
                    chew_class = "LNF"
                    detail = "fallback_missing"

        rows.append(
            {
                "sample_id": str(sample.get("sample_id", "")),
                "locus": locus,
                "raw_allele_id": allele_id,
                "raw_call_type": call_type,
                "multiple_hits": str(int(multiple_hits)),
                "copy_count": str(call.get("copy_count", "")),
                "chew_style_class": chew_class,
                "decision_detail": detail,
            }
        )
        class_counts[chew_class if not chew_class.isdigit() else "NUMERIC"] += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sample_id",
                "locus",
                "raw_allele_id",
                "raw_call_type",
                "multiple_hits",
                "copy_count",
                "chew_style_class",
                "decision_detail",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"rows\t{len(rows)}")
    for key in sorted(class_counts):
        print(f"class::{key}\t{class_counts[key]}")

    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        with args.summary.open("w", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["metric", "value"])
            writer.writerow(["rows", len(rows)])
            for key in sorted(class_counts):
                writer.writerow([f"class::{key}", class_counts[key]])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
