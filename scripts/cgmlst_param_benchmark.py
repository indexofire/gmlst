#!/usr/bin/env python3
"""cgMLST parameter benchmark tool.

Sweeps minimap2 parameters (preset, threads, CIGAR, mode) one at a time,
measuring both speed and allele-call accuracy against a baseline.

Usage:
    # Single genome
    python scripts/cgmlst_param_benchmark.py \\
        --genome ~/data/vpa/O10K4/fna/GCA_019351375.1.fna \\
        --scheme vparahaemolyticus_3 \\
        --output /tmp/bench

    # Multiple genomes (better statistics)
    python scripts/cgmlst_param_benchmark.py \\
        --genome-dir ~/data/vpa/O10K4/fna/ \\
        --scheme vparahaemolyticus_3 \\
        --output /tmp/bench \\
        --max-genomes 5

    # Only test specific parameters
    python scripts/cgmlst_param_benchmark.py \\
        --genome genome.fna --scheme vparahaemolyticus_3 \\
        --output /tmp/bench \\
        --test preset,threads

Output:
    {output}/results.tsv          — full comparison table
    {output}/per_genome/          — per-genome TSV files
    {output}/summary.txt          — console-friendly summary
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Test configurations
# ---------------------------------------------------------------------------

# Baseline: current production defaults
BASELINE_NAME = "baseline"

# Each config: name → (env_overrides, cli_flags)
# We test ONE parameter at a time (one-at-a-time design)
TEST_CONFIGS: list[tuple[str, dict[str, str], list[str]]] = [
    # --- Baseline ---
    (BASELINE_NAME, {}, []),
    # --- Preset comparison (the main question) ---
    ("preset-asm10", {"GMLST_MINIMAP2_FASTA_PRESET": "asm10"}, []),
    ("preset-asm5", {"GMLST_MINIMAP2_FASTA_PRESET": "asm5"}, []),
    # --- Thread comparison ---
    ("threads-2", {}, ["--threads", "2"]),
    ("threads-4", {}, ["--threads", "4"]),
    ("threads-8", {}, ["--threads", "8"]),
    # --- CIGAR comparison ---
    ("no-cigar", {"GMLST_MINIMAP2_FASTA_EMIT_CIGAR": "0"}, []),
    # --- Mode comparison ---
    ("mode-ultrafast", {}, ["--cgmlst-mode", "ultrafast"]),
    ("mode-balanced", {}, ["--cgmlst-mode", "balanced"]),
    # --- Combined best-case scenarios ---
    (
        "asm5+t8",
        {"GMLST_MINIMAP2_FASTA_PRESET": "asm5"},
        ["--threads", "8"],
    ),
    (
        "asm5+t8+nc",
        {
            "GMLST_MINIMAP2_FASTA_PRESET": "asm5",
            "GMLST_MINIMAP2_FASTA_EMIT_CIGAR": "0",
        },
        ["--threads", "8"],
    ),
    (
        "asm5+t8+nc+uf",
        {
            "GMLST_MINIMAP2_FASTA_PRESET": "asm5",
            "GMLST_MINIMAP2_FASTA_EMIT_CIGAR": "0",
        },
        ["--threads", "8", "--cgmlst-mode", "ultrafast"],
    ),
]

TEST_GROUPS = {
    "preset": ["baseline", "preset-asm10", "preset-asm5"],
    "threads": ["baseline", "threads-2", "threads-4", "threads-8"],
    "cigar": ["baseline", "no-cigar"],
    "mode": ["baseline", "mode-ultrafast", "mode-balanced"],
    "combined": [
        "baseline",
        "asm5+t8",
        "asm5+t8+nc",
        "asm5+t8+nc+uf",
    ],
    "all": [c[0] for c in TEST_CONFIGS],
}


# ---------------------------------------------------------------------------
# TSV parsing
# ---------------------------------------------------------------------------


def parse_typing_tsv(path: Path) -> dict[str, str]:
    """Parse gmlst typing TSV output → {sample_id: {locus: allele_call}}.

    Returns the first data row (single sample) as {locus: call}.
    """
    calls: dict[str, str] = {}
    with path.open() as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader)
        # First column is FILE/sample name, rest are loci
        for row in reader:
            if not row:
                continue
            for i, locus in enumerate(header[1:], 1):
                calls[locus] = row[i] if i < len(row) else "-"
            break  # Only first sample
    return calls


def count_call_types(calls: dict[str, str]) -> dict[str, int]:
    """Count allele call types: exact, closest (~), partial (?), missing (-)."""
    counts = {"exact": 0, "closest": 0, "partial": 0, "missing": 0, "other": 0}
    for call in calls.values():
        call = call.strip()
        if call == "-" or call == "":
            counts["missing"] += 1
        elif call.startswith("~"):
            counts["closest"] += 1
        elif call.endswith("?"):
            counts["partial"] += 1
        elif "*" in call or "," in call:
            counts["other"] += 1
        else:
            counts["exact"] += 1
    return counts


def compare_calls(
    baseline: dict[str, str], candidate: dict[str, str]
) -> dict[str, int]:
    """Compare allele calls between baseline and candidate."""
    agree = 0
    disagree = 0
    baseline_only_called = 0
    candidate_only_called = 0
    both_missing = 0
    differences: list[tuple[str, str, str]] = []

    all_loci = set(baseline) | set(candidate)
    for locus in sorted(all_loci):
        b = baseline.get(locus, "-")
        c = candidate.get(locus, "-")
        if b == c:
            if b == "-":
                both_missing += 1
            else:
                agree += 1
        else:
            disagree += 1
            if b != "-" and c == "-":
                baseline_only_called += 1
            elif b == "-" and c != "-":
                candidate_only_called += 1
            differences.append((locus, b, c))

    return {
        "agree": agree,
        "disagree": disagree,
        "baseline_only": baseline_only_called,
        "candidate_only": candidate_only_called,
        "both_missing": both_missing,
        "total": len(all_loci),
        "differences": differences,  # type: ignore[dict-item]
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_gmlst(
    genome: Path,
    scheme: str,
    config_env: dict[str, str],
    config_flags: list[str],
    output_tsv: Path,
    gmlst_cmd: str = "gmlst",
) -> tuple[float, int]:
    """Run gmlst typing cgmlst and return (wall_time_seconds, exit_code)."""
    cmd = [
        gmlst_cmd,
        "typing",
        "cgmlst",
        "-s",
        scheme,
        *config_flags,
        str(genome),
        "-o",
        str(output_tsv),
    ]

    env = os.environ.copy()
    env.update(config_env)

    t0 = time.perf_counter()
    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    elapsed = time.perf_counter() - t0

    if result.returncode != 0:
        sys.stderr.write(f"  ERROR (exit {result.returncode}): {result.stderr[:500]}\n")

    return elapsed, result.returncode


# ---------------------------------------------------------------------------
# Main benchmark logic
# ---------------------------------------------------------------------------


def collect_genomes(args) -> list[Path]:
    """Collect genome files from --genome or --genome-dir."""
    genomes: list[Path] = []
    if args.genome:
        genomes.append(Path(args.genome))
    if args.genome_dir:
        exts = {".fna", ".fasta", ".fa", ".ffn"}
        dir_genomes = sorted(
            f
            for f in Path(args.genome_dir).iterdir()
            if f.suffix in exts and f.is_file()
        )
        genomes.extend(dir_genomes)
    if args.max_genomes and len(genomes) > args.max_genomes:
        genomes = genomes[: args.max_genomes]
    return genomes


def select_configs(
    test_filter: str | None,
) -> list[tuple[str, dict[str, str], list[str]]]:
    """Select test configurations based on filter."""
    if not test_filter:
        return TEST_CONFIGS
    wanted_names: set[str] = set()
    for group in test_filter.split(","):
        group = group.strip()
        if group in TEST_GROUPS:
            wanted_names.update(TEST_GROUPS[group])
        else:
            # Direct config name
            wanted_names.add(group)
    return [c for c in TEST_CONFIGS if c[0] in wanted_names]


def benchmark_single_genome(
    genome: Path,
    scheme: str,
    configs: list[tuple[str, dict[str, str], list[str]]],
    output_dir: Path,
    gmlst_cmd: str,
) -> dict[str, dict]:
    """Run all configs on a single genome. Returns {config_name: metrics}."""
    results: dict[str, dict] = {}

    for config_name, config_env, config_flags in configs:
        tsv_path = output_dir / f"{config_name}.tsv"
        sys.stderr.write(f"  Running {config_name}... ")

        elapsed, exit_code = run_gmlst(
            genome, scheme, config_env, config_flags, tsv_path, gmlst_cmd
        )

        if exit_code != 0:
            sys.stderr.write(f"FAILED ({elapsed:.1f}s)\n")
            results[config_name] = {
                "exit_code": exit_code,
                "wall_time": elapsed,
                "calls": {},
            }
            continue

        calls = parse_typing_tsv(tsv_path) if tsv_path.exists() else {}
        call_counts = count_call_types(calls)
        sys.stderr.write(
            f"OK ({elapsed:.1f}s, "
            f"exact={call_counts['exact']}, "
            f"missing={call_counts['missing']})\n"
        )

        results[config_name] = {
            "exit_code": 0,
            "wall_time": elapsed,
            "calls": calls,
            "call_counts": call_counts,
        }

    return results


def build_comparison_table(
    all_results: dict[str, dict[str, dict]],
    configs: list[tuple[str, dict[str, str], list[str]]],
) -> list[dict]:
    """Build comparison rows for output.

    all_results: {genome_name: {config_name: metrics}}
    Returns list of row dicts.
    """
    rows: list[dict] = []
    config_names = [c[0] for c in configs]
    genome_names = sorted(all_results.keys())

    for config_name in config_names:
        times: list[float] = []
        total_agree = 0
        total_compared = 0
        total_exact = 0
        total_closest = 0
        total_partial = 0
        total_missing = 0
        total_loci = 0
        all_diffs: list[tuple[str, str, str, str]] = []
        n_success = 0

        for genome_name in genome_names:
            genome_data = all_results[genome_name]
            if config_name not in genome_data:
                continue
            data = genome_data[config_name]
            if data["exit_code"] != 0:
                continue

            n_success += 1
            times.append(data["wall_time"])
            cc = data.get("call_counts", {})
            total_exact += cc.get("exact", 0)
            total_closest += cc.get("closest", 0)
            total_partial += cc.get("partial", 0)
            total_missing += cc.get("missing", 0)
            total_loci += sum(cc.values())

            # Compare against baseline
            baseline_data = genome_data.get(BASELINE_NAME, {})
            if baseline_data and baseline_data.get("exit_code") == 0:
                cmp = compare_calls(baseline_data["calls"], data["calls"])
                total_agree += cmp["agree"]
                total_compared += cmp["agree"] + cmp["disagree"]
                for locus, b, c in cmp.get("differences", []):  # type: ignore[attr-defined]
                    all_diffs.append((genome_name, locus, b, c))

        avg_time = statistics.mean(times) if times else 0.0
        agreement_pct = (
            (total_agree / total_compared * 100.0) if total_compared > 0 else 0.0
        )
        exact_pct = (total_exact / total_loci * 100.0) if total_loci > 0 else 0.0
        missing_pct = (total_missing / total_loci * 100.0) if total_loci > 0 else 0.0

        row = {
            "config": config_name,
            "n_genomes": n_success,
            "avg_time_s": round(avg_time, 2),
            "speedup_vs_baseline": "",
            "exact_pct": f"{exact_pct:.1f}%",
            "missing_pct": f"{missing_pct:.1f}%",
            "agreement_pct": f"{agreement_pct:.2f}%",
            "n_disagree": total_compared - total_agree,
            "n_diffs_detail": len(all_diffs),
        }
        rows.append(row)

    # Calculate speedup
    baseline_time = rows[0]["avg_time_s"] if rows else 0.0
    if baseline_time > 0:
        for row in rows:
            speedup = baseline_time / row["avg_time_s"] if row["avg_time_s"] > 0 else 0
            row["speedup_vs_baseline"] = f"{speedup:.2f}x"

    return rows


def write_results(rows: list[dict], output_dir: Path, all_diffs: list[tuple]):
    """Write results to TSV and summary."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # TSV
    tsv_path = output_dir / "results.tsv"
    fieldnames = list(rows[0].keys()) if rows else []
    with tsv_path.open("w") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    # Summary (console-friendly)
    summary_path = output_dir / "summary.txt"
    with summary_path.open("w") as fh:
        fh.write("cgMLST Parameter Benchmark Results\n")
        fh.write("=" * 100 + "\n\n")

        # Table header
        fh.write(
            f"{'Config':<22} {'Time(s)':>8} {'Speedup':>8} "
            f"{'Exact%':>8} {'Missing%':>9} {'Agree%':>8} {'Disagree':>9}\n"
        )
        fh.write("-" * 100 + "\n")
        for row in rows:
            fh.write(
                f"{row['config']:<22} {row['avg_time_s']:>8.2f} "
                f"{row['speedup_vs_baseline']:>8} {row['exact_pct']:>8} "
                f"{row['missing_pct']:>9} {row['agreement_pct']:>8} "
                f"{row['n_disagree']:>9}\n"
            )
        fh.write("\n")

        # Per-group analysis
        fh.write("\nParameter Group Analysis:\n")
        fh.write("-" * 60 + "\n")
        for group_name, group_configs in TEST_GROUPS.items():
            if group_name == "all":
                continue
            group_rows = [r for r in rows if r["config"] in group_configs]
            if len(group_rows) < 2:
                continue
            fh.write(f"\n  [{group_name}]\n")
            for row in group_rows:
                fh.write(
                    f"    {row['config']:<20} "
                    f"{row['avg_time_s']:>7.2f}s  "
                    f"speedup={row['speedup_vs_baseline']:<6}  "
                    f"agree={row['agreement_pct']:<7}  "
                    f"disagree={row['n_disagree']}\n"
                )

        # Differences detail
        if all_diffs:
            fh.write("\n\nAllele Call Differences (first 50):\n")
            fh.write("-" * 60 + "\n")
            diff_hdr = f"{'Genome':<25} {'Locus':<15} {'Base':>10} {'Cand':>10}\n"
            fh.write(diff_hdr)
            for genome, locus, b, c in all_diffs[:50]:
                fh.write(f"{genome:<25} {locus:<15} {b:>10} {c:>10}\n")
            if len(all_diffs) > 50:
                fh.write(f"... and {len(all_diffs) - 50} more\n")

    # Differences TSV
    if all_diffs:
        diff_path = output_dir / "differences.tsv"
        with diff_path.open("w") as fh:
            fh.write("genome\tlocus\tbaseline_call\tcandidate_call\n")
            for genome, locus, b, c in all_diffs:
                fh.write(f"{genome}\t{locus}\t{b}\t{c}\n")


def collect_all_diffs(
    all_results: dict[str, dict[str, dict]],
    configs: list[tuple[str, dict[str, str], list[str]]],
) -> list[tuple[str, str, str, str]]:
    """Collect all differences across genomes and configs."""
    diffs: list[tuple[str, str, str, str]] = []
    config_names = [c[0] for c in configs]
    genome_names = sorted(all_results.keys())

    for genome_name in genome_names:
        genome_data = all_results[genome_name]
        baseline = genome_data.get(BASELINE_NAME, {})
        if not baseline or baseline.get("exit_code") != 0:
            continue

        for config_name in config_names:
            if config_name == BASELINE_NAME:
                continue
            candidate = genome_data.get(config_name, {})
            if not candidate or candidate.get("exit_code") != 0:
                continue

            cmp = compare_calls(baseline["calls"], candidate["calls"])
            for locus, b, c in cmp.get("differences", []):  # type: ignore[attr-defined]
                diffs.append((genome_name, locus, b, c))

    return diffs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="cgMLST parameter benchmark: compare presets, threads, CIGAR, modes"
    )
    parser.add_argument(
        "--genome",
        type=Path,
        help="Single genome file to benchmark",
    )
    parser.add_argument(
        "--genome-dir",
        type=Path,
        help="Directory of genome files (.fna, .fasta, .fa)",
    )
    parser.add_argument(
        "--scheme",
        required=True,
        help="Scheme name (e.g., vparahaemolyticus_3)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for results",
    )
    parser.add_argument(
        "--max-genomes",
        type=int,
        default=5,
        help="Max genomes to test (default: 5)",
    )
    parser.add_argument(
        "--test",
        type=str,
        default=None,
        help=(
            "Test filter: comma-separated group names or config names. "
            f"Groups: {', '.join(TEST_GROUPS.keys())}"
        ),
    )
    parser.add_argument(
        "--gmlst-cmd",
        type=str,
        default="gmlst",
        help="gmlst command (default: gmlst; use 'pixi run gmlst' if needed)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip configs that already have output TSV",
    )

    args = parser.parse_args()

    # Collect genomes
    genomes = collect_genomes(args)
    if not genomes:
        sys.stderr.write("No genomes found. Use --genome or --genome-dir.\n")
        sys.exit(1)

    n_genomes = len(genomes)
    sys.stderr.write(
        f"\nBenchmarking {n_genomes} genome(s) on scheme '{args.scheme}'\n"
    )
    sys.stderr.write(f"Output: {args.output}\n\n")

    # Select configs
    configs = select_configs(args.test)
    sys.stderr.write(f"Testing {len(configs)} configurations\n")
    for name, _, _ in configs:
        sys.stderr.write(f"  - {name}\n")
    sys.stderr.write("\n")

    # Run benchmarks
    args.output.mkdir(parents=True, exist_ok=True)
    all_results: dict[str, dict[str, dict]] = {}

    for genome in genomes:
        genome_name = genome.stem
        sys.stderr.write(f"\n{'=' * 80}\n")
        sys.stderr.write(f"Genome: {genome_name}\n")
        sys.stderr.write(f"{'=' * 80}\n")

        per_genome_dir = args.output / "per_genome" / genome_name
        per_genome_dir.mkdir(parents=True, exist_ok=True)

        results = benchmark_single_genome(
            genome, args.scheme, configs, per_genome_dir, args.gmlst_cmd
        )
        all_results[genome_name] = results

    # Build comparison
    sys.stderr.write(f"\n{'=' * 80}\n")
    sys.stderr.write("Building comparison table...\n")

    rows = build_comparison_table(all_results, configs)
    all_diffs = collect_all_diffs(all_results, configs)
    write_results(rows, args.output, all_diffs)

    # Print summary to stderr
    summary_path = args.output / "summary.txt"
    sys.stderr.write(f"\nResults written to {args.output}/\n")
    sys.stderr.write("Summary:\n\n")
    sys.stderr.write(summary_path.read_text())


if __name__ == "__main__":
    main()
