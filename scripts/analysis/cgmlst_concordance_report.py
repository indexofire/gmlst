from __future__ import annotations

import argparse
import csv
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
        description="Generate concordance report between two cgMLST TSV outputs."
    )
    parser.add_argument("--query", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--query-sample", type=str, default=None)
    parser.add_argument("--reference-sample", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def _infer_key_field(fieldnames: list[str]) -> str:
    for candidate in ("FILE", "sample_id", "SAMPLE", "Sample"):
        if candidate in fieldnames:
            return candidate
    return fieldnames[0]


def _load_rows(path: Path) -> tuple[str, dict[str, dict[str, str]], list[str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError(f"TSV has no header: {path}")
        fieldnames = list(reader.fieldnames)
        key_field = _infer_key_field(fieldnames)
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            key = row.get(key_field, "").strip()
            if key:
                rows[key] = row
    return key_field, rows, fieldnames


def _pick_sample(
    rows: dict[str, dict[str, str]],
    sample: str | None,
    label: str,
) -> tuple[str, dict[str, str]]:
    if sample is not None:
        if sample not in rows:
            raise ValueError(
                f"{label} sample '{sample}' not found. Available: {sorted(rows)}"
            )
        return sample, rows[sample]
    if len(rows) != 1:
        raise ValueError(
            f"{label} has {len(rows)} samples; specify --{label.lower()}-sample"
        )
    selected = next(iter(rows))
    return selected, rows[selected]


def _normalize(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("~"):
        cleaned = cleaned[1:]
    if cleaned.endswith("?"):
        cleaned = cleaned[:-1]
    return cleaned


def _is_numeric(value: str) -> bool:
    return value.isdigit()


def _is_missing_like(value: str) -> bool:
    upper = value.upper()
    return upper in {"", "-", "LNF", "NIPH", "ALM", "ASM", "PLOT3", "PLOT5"}


def main() -> int:
    args = _parse_args()
    q_key, q_rows, q_fields = _load_rows(args.query)
    r_key, r_rows, r_fields = _load_rows(args.reference)

    query_id, query_row = _pick_sample(q_rows, args.query_sample, "query")
    reference_id, reference_row = _pick_sample(
        r_rows,
        args.reference_sample,
        "reference",
    )

    loci = sorted(
        (set(q_fields) - NON_LOCI_COLUMNS) & (set(r_fields) - NON_LOCI_COLUMNS)
    )
    strict_equal = 0
    normalized_equal = 0
    strict_numeric_diff = 0
    strict_numeric_equal = 0
    normalized_numeric_diff = 0
    normalized_numeric_equal = 0
    query_missing = 0
    reference_missing = 0
    both_missing = 0

    detail_rows: list[list[str]] = []
    for locus in loci:
        q_raw = query_row.get(locus, "")
        r_raw = reference_row.get(locus, "")
        q_norm = _normalize(q_raw)
        r_norm = _normalize(r_raw)
        q_raw_clean = q_raw.strip()
        r_raw_clean = r_raw.strip()

        if q_raw == r_raw:
            strict_equal += 1
        if q_norm == r_norm:
            normalized_equal += 1

        q_missing = _is_missing_like(q_norm)
        r_missing = _is_missing_like(r_norm)
        if q_missing and r_missing:
            both_missing += 1
        elif q_missing:
            query_missing += 1
        elif r_missing:
            reference_missing += 1

        if _is_numeric(q_raw_clean) and _is_numeric(r_raw_clean):
            if q_raw_clean == r_raw_clean:
                strict_numeric_equal += 1
            else:
                strict_numeric_diff += 1

        if _is_numeric(q_norm) and _is_numeric(r_norm):
            if q_norm == r_norm:
                normalized_numeric_equal += 1
            else:
                normalized_numeric_diff += 1

        if q_norm != r_norm:
            detail_rows.append([locus, q_raw, r_raw, q_norm, r_norm])

    print(f"query_file\t{args.query}")
    print(f"reference_file\t{args.reference}")
    print(f"query_key_field\t{q_key}")
    print(f"reference_key_field\t{r_key}")
    print(f"query_sample\t{query_id}")
    print(f"reference_sample\t{reference_id}")
    print(f"common_loci\t{len(loci)}")
    print(f"strict_equal\t{strict_equal}")
    print(f"normalized_equal\t{normalized_equal}")
    print(f"strict_numeric_equal\t{strict_numeric_equal}")
    print(f"strict_numeric_diff\t{strict_numeric_diff}")
    print(f"normalized_numeric_equal\t{normalized_numeric_equal}")
    print(f"normalized_numeric_diff\t{normalized_numeric_diff}")
    print(f"both_missing\t{both_missing}")
    print(f"query_missing_only\t{query_missing}")
    print(f"reference_missing_only\t{reference_missing}")
    print(f"normalized_diff_total\t{len(detail_rows)}")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(
                ["locus", "query_raw", "reference_raw", "query_norm", "reference_norm"]
            )
            writer.writerows(detail_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
