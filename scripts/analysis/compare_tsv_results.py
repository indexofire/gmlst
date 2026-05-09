#!/usr/bin/env python3
"""Compare two gmlst TSV result files.

Reports:
- per-sample allele difference counts
- concrete differing loci with values from both files
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

_NON_LOCI_COLUMNS = {
    "FILE",
    "SCHEME",
    "ST",
    "sample_id",
    "SAMPLE",
    "Sample",
    "backend",
    "runtime_seconds",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two TSV typing outputs and print allele differences by locus."
        )
    )
    parser.add_argument("tsv_a", type=Path, help="First TSV file")
    parser.add_argument("tsv_b", type=Path, help="Second TSV file")
    parser.add_argument(
        "--sample",
        type=str,
        default=None,
        help="Optional sample key to compare (default: all common samples)",
    )
    return parser.parse_args()


def _infer_key_field(fieldnames: list[str]) -> str:
    for candidate in ("FILE", "sample_id", "SAMPLE", "Sample"):
        if candidate in fieldnames:
            return candidate
    return fieldnames[0]


def _load_rows(path: Path) -> tuple[str, dict[str, dict[str, str]], set[str]]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError(f"TSV has no header: {path}")

        fieldnames = list(reader.fieldnames)
        key_field = _infer_key_field(fieldnames)
        loci = {name for name in fieldnames if name not in _NON_LOCI_COLUMNS}

        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            key = row.get(key_field, "")
            if not key:
                continue
            rows[key] = row

    return key_field, rows, loci


def main() -> None:
    args = _parse_args()
    key_a, rows_a, loci_a = _load_rows(args.tsv_a)
    key_b, rows_b, loci_b = _load_rows(args.tsv_b)

    samples_a = set(rows_a)
    samples_b = set(rows_b)
    common_samples = sorted(samples_a & samples_b)

    if args.sample is not None:
        common_samples = [s for s in common_samples if s == args.sample]
        if not common_samples:
            raise ValueError(
                f"Sample '{args.sample}' not found in both files. "
                f"Available common samples: {sorted(samples_a & samples_b)}"
            )

    if not common_samples:
        raise ValueError("No common samples found between the two TSV files.")

    only_a = sorted(samples_a - samples_b)
    only_b = sorted(samples_b - samples_a)
    if only_a:
        print(f"Samples only in {args.tsv_a.name}: {only_a}")
    if only_b:
        print(f"Samples only in {args.tsv_b.name}: {only_b}")

    common_loci = sorted(loci_a & loci_b)
    only_loci_a = sorted(loci_a - loci_b)
    only_loci_b = sorted(loci_b - loci_a)

    print(f"Key fields: A={key_a}, B={key_b}")
    print(f"Common loci: {len(common_loci)}")
    if only_loci_a:
        print(f"Loci only in {args.tsv_a.name}: {len(only_loci_a)}")
    if only_loci_b:
        print(f"Loci only in {args.tsv_b.name}: {len(only_loci_b)}")

    for sample in common_samples:
        row_a = rows_a[sample]
        row_b = rows_b[sample]

        diffs: list[tuple[str, str, str]] = []
        for locus in common_loci:
            val_a = row_a.get(locus, "")
            val_b = row_b.get(locus, "")
            if val_a != val_b:
                diffs.append((locus, val_a, val_b))

        print("\n" + "=" * 72)
        print(f"Sample: {sample}")
        print(f"Different loci: {len(diffs)} / {len(common_loci)}")

        if not diffs:
            print("No differences.")
            continue

        print("Locus\tA\tB")
        for locus, val_a, val_b in diffs:
            print(f"{locus}\t{val_a}\t{val_b}")


if __name__ == "__main__":
    main()
