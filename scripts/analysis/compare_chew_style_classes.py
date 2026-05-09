from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

NON_LOCI_COLUMNS = {
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
            "Compare gmlst chew-style classes against chewBBACA results_alleles.tsv"
        )
    )
    parser.add_argument("--gmlst-classes", required=True, type=Path)
    parser.add_argument("--chew-alleles", required=True, type=Path)
    parser.add_argument("--chew-sample", required=True, type=str)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=False, type=Path)
    return parser.parse_args()


def _bucket(value: str) -> str:
    token = value.strip()
    if not token or token == "-":
        return "LNF"
    if token.isdigit():
        return "NUMERIC"
    if token.startswith("INF-"):
        return "INF"
    if token in {
        "EXC",
        "INF",
        "LNF",
        "PLOT3",
        "PLOT5",
        "LOTSC",
        "NIPH",
        "NIPHEM",
        "ALM",
        "ASM",
        "PAMA",
        "PLNF",
    }:
        return token
    return "OTHER"


def _read_gmlst_classes(path: Path) -> dict[str, str]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        out: dict[str, str] = {}
        for row in reader:
            locus = row.get("locus", "").strip()
            if not locus:
                continue
            out[locus] = row.get("chew_style_class", "").strip()
    return out


def _read_chew_sample(path: Path, sample: str) -> dict[str, str]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError(f"No header in {path}")
        rows = {row.get("FILE", "").strip(): row for row in reader}
    if sample not in rows:
        raise ValueError(f"Sample '{sample}' not found in {path}")
    row = rows[sample]
    return {
        key: value
        for key, value in row.items()
        if key is not None and key not in NON_LOCI_COLUMNS
    }


def main() -> int:
    args = _parse_args()
    gmlst = _read_gmlst_classes(args.gmlst_classes)
    chew = _read_chew_sample(args.chew_alleles, args.chew_sample)

    loci = sorted(set(gmlst) & set(chew))
    exact_match = 0
    bucket_match = 0
    mismatch_bucket_counts: Counter[tuple[str, str]] = Counter()
    detail_rows: list[list[str]] = []

    for locus in loci:
        g_val = gmlst[locus]
        c_val = chew[locus].strip()
        g_bucket = _bucket(g_val)
        c_bucket = _bucket(c_val)

        if g_val == c_val:
            exact_match += 1
        if g_bucket == c_bucket:
            bucket_match += 1
        else:
            mismatch_bucket_counts[(g_bucket, c_bucket)] += 1

        detail_rows.append([locus, g_val, c_val, g_bucket, c_bucket])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "locus",
                "gmlst_chew_style_class",
                "chew_raw",
                "gmlst_bucket",
                "chew_bucket",
            ]
        )
        writer.writerows(detail_rows)

    print(f"loci\t{len(loci)}")
    print(f"exact_label_match\t{exact_match}")
    print(f"bucket_match\t{bucket_match}")
    for (g_bucket, c_bucket), count in sorted(mismatch_bucket_counts.items()):
        print(f"mismatch::{g_bucket}->{c_bucket}\t{count}")

    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        with args.summary.open("w", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["metric", "value"])
            writer.writerow(["loci", len(loci)])
            writer.writerow(["exact_label_match", exact_match])
            writer.writerow(["bucket_match", bucket_match])
            for (g_bucket, c_bucket), count in sorted(mismatch_bucket_counts.items()):
                writer.writerow([f"mismatch::{g_bucket}->{c_bucket}", count])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
