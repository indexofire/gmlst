#!/usr/bin/env python3
"""Benchmark gmlst vs chewBBACA cgMLST results with BLAST verification.

Usage:
    python cgmlst_benchmark.py \\
        --genome /path/to/sample.fna \\
        --scheme vparahaemolyticus_3 \\
        --chewbbaca-schema ~/dbs/cgmlst/vpa_pubmlst/schema \\
        --gmlst-cache ~/.cache/gmlst \\
        --chewbbaca-env chewbbaca \\
        --gmlst-env pixi \\
        --gmlst-project /path/to/gmlst \\
        --output /path/to/output_dir

For batch processing of multiple genomes:
    python cgmlst_benchmark.py \\
        --genome-dir /path/to/genomes/ \\
        --scheme vparahaemolyticus_3 \\
        --chewbbaca-schema ~/dbs/cgmlst/vpa_pubmlst/schema \\
        --output /path/to/output_dir

The script will:
1. Run gmlst typing cgmlst (chew-fast mode)
2. Run chewBBACA AlleleCall
3. Compare results locus by locus
4. For each difference, BLAST verify against the allele database
5. Generate comparison TSV, BLAST results, and summary report
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utility: run commands in conda environments
# ---------------------------------------------------------------------------


def run_in_env(
    cmd: list[str],
    env_name: str | None = None,
    env_prefix: Path | None = None,
    cwd: Path | None = None,
    timeout: int = 3600,
) -> subprocess.CompletedProcess:
    if env_prefix:
        env_bin = env_prefix / "bin"
        full_cmd = [str(env_bin / cmd[0])] + cmd[1:]
        env = dict(__import__("os").environ)
        env["PATH"] = f"{env_bin}:{env.get('PATH', '')}"
        env["CONDA_PREFIX"] = str(env_prefix)
        logger.debug("Running (direct): %s", " ".join(full_cmd))
        return subprocess.run(
            full_cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout, env=env
        )
    elif env_name:
        full_cmd = ["conda", "run", "-n", env_name] + cmd
        logger.debug("Running (conda): %s", " ".join(full_cmd))
        return subprocess.run(
            full_cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
    else:
        logger.debug("Running: %s", " ".join(cmd))
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )


# ---------------------------------------------------------------------------
# Step 1: Run gmlst typing cgmlst
# ---------------------------------------------------------------------------


def run_gmlst(
    genome: Path,
    scheme: str,
    output_tsv: Path,
    *,
    gmlst_env: str = "pixi",
    gmlst_project: Path | None = None,
    gmlst_prefix: Path | None = None,
    mode: str = "chew-fast",
) -> tuple[bool, float]:
    cmd = ["gmlst", "typing", "cgmlst", "-s", scheme]
    cmd += ["--cgmlst-mode", mode]
    cmd += ["--call-policy", "chewbbaca", "--no-chew-cds-gate"]
    cmd += ["-o", str(output_tsv), str(genome)]
    if gmlst_project:
        cmd = ["pixi", "run", "--manifest-path", str(gmlst_project / "pixi.toml")] + cmd
        t0 = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        elapsed = time.perf_counter() - t0
    else:
        t0 = time.perf_counter()
        result = run_in_env(cmd, env_prefix=gmlst_prefix)
        elapsed = time.perf_counter() - t0
    if result.returncode != 0:
        logger.error("gmlst failed: %s", result.stderr[-500:] if result.stderr else "")
        return False, elapsed
    return True, elapsed


# ---------------------------------------------------------------------------
# Step 2: Run chewBBACA AlleleCall
# ---------------------------------------------------------------------------


def run_chewbbaca(
    genome: Path,
    schema: Path,
    output_dir: Path,
    *,
    chewbbaca_env: str = "chewbbaca",
    chewbbaca_prefix: Path | None = None,
) -> tuple[bool, float]:
    output_dir.mkdir(parents=True, exist_ok=True)
    genome_input_dir = output_dir / "input"
    genome_input_dir.mkdir(parents=True, exist_ok=True)
    genome_link = genome_input_dir / genome.name
    if not genome_link.exists():
        genome_link.symlink_to(genome.resolve())

    cmd = [
        "chewBBACA.py",
        "AlleleCall",
        "-i",
        str(genome_input_dir),
        "-g",
        str(schema),
        "-o",
        str(output_dir),
    ]
    t0 = time.perf_counter()
    if chewbbaca_prefix:
        result = run_in_env(cmd, env_prefix=chewbbaca_prefix)
    else:
        result = run_in_env(cmd, env_name=chewbbaca_env)
    elapsed = time.perf_counter() - t0
    if result.returncode != 0:
        logger.error(
            "chewBBACA failed: %s", result.stderr[-500:] if result.stderr else ""
        )
        return False, elapsed
    return True, elapsed


# ---------------------------------------------------------------------------
# Step 3: Parse results
# ---------------------------------------------------------------------------


def parse_gmlst_tsv(tsv_path: Path) -> dict[str, str]:
    """Return locus → allele_call mapping."""
    result = {}
    with tsv_path.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            for locus, val in row.items():
                if locus in ("FILE", "SCHEME", "ST"):
                    continue
                result[locus] = val
    return result


def _find_chewbbaca_file(results_dir: Path, filename: str) -> Path | None:
    """Find a chewBBACA output file, handling timestamped subdirectories."""
    direct = results_dir / filename
    if direct.exists():
        return direct
    timestamped = sorted(results_dir.glob(f"results_*/{filename}"))
    if timestamped:
        return timestamped[-1]
    return None


def parse_chewbbaca_results(results_dir: Path, genome_name: str = "") -> dict[str, str]:
    """Return locus → allele_call mapping from results_alleles.tsv.

    If genome_name is given, only return results for that sample.
    """
    alleles_file = _find_chewbbaca_file(results_dir, "results_alleles.tsv")
    if not alleles_file:
        return {}
    result = {}
    genome_name_stem = Path(genome_name).stem if genome_name else ""
    with alleles_file.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            file_val = row.get("FILE", "")
            if (
                genome_name
                and file_val != genome_name
                and genome_name_stem not in file_val
                and file_val not in genome_name
            ):
                continue
            for locus, val in row.items():
                if locus == "FILE":
                    continue
                result[locus] = val
            break
    return result


def parse_chewbbaca_contig_info(
    results_dir: Path, genome_name: str = ""
) -> dict[str, str]:
    """Return locus → contig coordinates from results_contigsInfo.tsv.

    If genome_name is given, only return results for that sample.
    """
    info_file = _find_chewbbaca_file(results_dir, "results_contigsInfo.tsv")
    if not info_file:
        return {}
    result = {}
    genome_name_stem = Path(genome_name).stem if genome_name else ""
    with info_file.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            file_val = row.get("FILE", "")
            if (
                genome_name
                and file_val != genome_name
                and genome_name_stem not in file_val
                and file_val not in genome_name
            ):
                continue
            for locus, val in row.items():
                if locus == "FILE":
                    continue
                result[locus] = val
            break
    return result


# ---------------------------------------------------------------------------
# Step 4: Compare
# ---------------------------------------------------------------------------


def compare_results(
    gmlst: dict[str, str],
    chewbbaca: dict[str, str],
) -> list[dict[str, str]]:
    all_loci = sorted(set(gmlst) | set(chewbbaca))
    rows = []
    for locus in all_loci:
        g = gmlst.get(locus, "")
        c = chewbbaca.get(locus, "")
        same = _normalize(g) == _normalize(c)
        rows.append(
            {
                "locus": locus,
                "gmlst": g,
                "chewbbaca": c,
                "consistent": "YES" if same else "NO",
                "category": _classify_diff(g, c),
            }
        )
    return rows


def _normalize(val: str) -> str:
    val = val.strip()
    if val.startswith("INF-"):
        return val.split("-")[1] if "-" in val else val
    if val.startswith("~"):
        return val[1:]
    if val.endswith("?"):
        return val[:-1]
    return val


def _classify_diff(gmlst: str, chewbbaca: str) -> str:
    g = gmlst.strip()
    c = chewbbaca.strip()
    if _normalize(g) == _normalize(c):
        return "consistent"
    if c in ("-", "LNF") and g not in ("-", "LNF"):
        return "chew_LNF_gmlst_found"
    if g in ("-", "LNF") and c not in ("-", "LNF"):
        return "gmlst_LNF_chew_found"
    if c.startswith("INF-") and not g.startswith("INF") and not g.startswith("~"):
        return "chew_INF_gmlst_exact"
    if g.startswith("INF-") and not c.startswith("INF") and not c.startswith("~"):
        return "gmlst_INF_chew_exact"
    if (g.startswith("INF-") or g.startswith("~")) and c.startswith("INF-"):
        return "both_INF_diff_allele"
    if g.startswith("~") and not c.startswith("~") and not c.startswith("INF"):
        return "gmlst_closest_chew_exact"
    if c in ("NIPH", "NIPHEM"):
        return "chew_NIPH"
    return "other"


# ---------------------------------------------------------------------------
# Step 5: BLAST verification
# ---------------------------------------------------------------------------


def load_fasta(path: Path) -> dict[str, str]:
    seqs = {}
    name = None
    seq = []
    for line in path.read_text().split("\n"):
        if line.startswith(">"):
            if name:
                seqs[name] = "".join(seq)
            name = line[1:].split()[0]
            seq = []
        elif line:
            seq.append(line.strip())
    if name:
        seqs[name] = "".join(seq)
    return seqs


def extract_cds_from_genome(genome: Path, coord_str: str) -> str | None:
    """Extract CDS sequence from genome using chewBBACA coordinate format.

    Format: contig&start-end&strand
    """
    contigs = load_fasta(genome)
    parts = coord_str.split("&")
    if len(parts) < 3:
        return None
    contig_id = parts[0]
    try:
        start, end = parts[1].split("-")
        start = int(start)
        end = int(end)
    except (ValueError, IndexError):
        return None
    strand = parts[2]
    contig_seq = contigs.get(contig_id, "")
    if not contig_seq:
        return None
    cds = contig_seq[start - 1 : end]
    if strand == "-1":
        comp = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
        cds = "".join(comp.get(b, "N") for b in reversed(cds))
    return cds


def blast_cds_against_locus(
    cds_seq: str,
    allele_fasta: Path,
    work_dir: Path,
    locus: str,
) -> dict[str, Any]:
    """BLAST a CDS sequence against a single locus allele database."""
    query_file = work_dir / f"query_{locus}.fasta"
    query_file.write_text(f">{locus}_cds\n{cds_seq}\n")

    db_prefix = work_dir / f"db_{locus}"
    subprocess.run(
        [
            "makeblastdb",
            "-in",
            str(allele_fasta),
            "-dbtype",
            "nucl",
            "-out",
            str(db_prefix),
        ],
        capture_output=True,
        timeout=30,
    )

    result = subprocess.run(
        [
            "blastn",
            "-query",
            str(query_file),
            "-db",
            str(db_prefix),
            "-outfmt",
            "6 qseqid sseqid pident length qlen mismatch gapopen qstart qend",
            "-evalue",
            "1e-10",
            "-num_threads",
            "1",
            "-max_target_seqs",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    best = {
        "allele": "",
        "pident": 0.0,
        "coverage": 0.0,
        "mismatch": -1,
    }
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 8:
            pident = float(parts[2])
            aln_len = int(parts[3])
            qlen = int(parts[4])
            mismatch = int(parts[5])
            coverage = aln_len / qlen if qlen > 0 else 0
            if pident > best["pident"] or (
                pident == best["pident"] and coverage > best["coverage"]
            ):
                best = {
                    "allele": parts[1],
                    "pident": pident,
                    "coverage": coverage,
                    "mismatch": mismatch,
                }

    for ext in (".nhr", ".nin", ".nsq"):
        f = Path(str(db_prefix) + ext)
        if f.exists():
            f.unlink()
    query_file.unlink(missing_ok=True)
    return best


def count_multicopy_hits(
    allele_seq: str,
    genome_db: Path,
    work_dir: Path,
    name: str,
) -> dict[str, Any]:
    """BLAST an allele against the genome and count hits at different positions.

    Returns dict with:
      n_hits: number of significant hits (identity >= 90%, coverage >= 50%)
      n_exact: number of 100% identity hits
      hit_positions: list of (contig, start, end)
    """
    query_file = work_dir / f"multicopy_{name}.fasta"
    query_file.write_text(f">{name}\n{allele_seq}\n")

    result = subprocess.run(
        [
            "blastn",
            "-query",
            str(query_file),
            "-db",
            str(genome_db),
            "-outfmt",
            "6 qseqid sseqid pident length qlen qstart qend sstart send evalue",
            "-evalue",
            "1e-10",
            "-task",
            "blastn-short" if len(allele_seq) < 150 else "blastn",
            "-num_threads",
            "1",
            "-max_target_seqs",
            "20",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    query_file.unlink(missing_ok=True)

    hits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 10:
            continue
        pident = float(parts[2])
        aln_len = int(parts[3])
        qlen = int(parts[4])
        coverage = aln_len / qlen if qlen > 0 else 0
        contig = parts[1]
        s_start = min(int(parts[7]), int(parts[8]))
        s_end = max(int(parts[7]), int(parts[8]))
        if pident >= 90.0 and coverage >= 0.50:
            hits.append(
                {
                    "pident": pident,
                    "coverage": coverage,
                    "contig": contig,
                    "start": s_start,
                    "end": s_end,
                    "is_exact": pident == 100.0 and coverage >= 1.0,
                }
            )

    return {
        "n_hits": len(hits),
        "n_exact": sum(1 for h in hits if h["is_exact"]),
        "hit_positions": [(h["contig"], h["start"], h["end"]) for h in hits],
    }


def blast_allele_against_genome(
    allele_seq: str,
    genome_db: Path,
    work_dir: Path,
    name: str,
) -> dict[str, Any]:
    """BLAST an allele sequence against the genome."""
    query_file = work_dir / f"allele_{name}.fasta"
    query_file.write_text(f">{name}\n{allele_seq}\n")

    result = subprocess.run(
        [
            "blastn",
            "-query",
            str(query_file),
            "-db",
            str(genome_db),
            "-outfmt",
            "6 qseqid sseqid pident length qlen mismatch gapopen",
            "-evalue",
            "1e-10",
            "-task",
            "blastn-short" if len(allele_seq) < 150 else "blastn",
            "-num_threads",
            "1",
            "-max_target_seqs",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    best = {"pident": 0.0, "coverage": 0.0, "mismatch": -1, "length": 0}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            pident = float(parts[2])
            aln_len = int(parts[3])
            qlen = int(parts[4])
            mismatch = int(parts[5])
            coverage = aln_len / qlen if qlen > 0 else 0
            if pident > best["pident"]:
                best = {
                    "pident": pident,
                    "coverage": coverage,
                    "mismatch": mismatch,
                    "length": aln_len,
                }
    query_file.unlink(missing_ok=True)
    return best


def determine_verdict(entry: dict[str, Any]) -> str:
    gmlst_ok = entry.get("gmlst_allele_in_genome", False)
    chew_exact = entry.get("chew_cds_exact", False)
    gmlst_val = entry.get("gmlst", "")
    chew_val = entry.get("chewbbaca", "")
    gmlst_is_near = gmlst_val.startswith("INF-") or gmlst_val.startswith("~")

    if chew_val in ("NIPH", "NIPHEM"):
        if entry.get("multicopy_verified"):
            return "chew_niph_verified"
        return "chew_niph_unverified"

    if chew_val.startswith("INF-") and chew_exact:
        if gmlst_ok:
            return "cds_boundary_diff"
        return "chew_inf_bsr_bug"

    if chew_val in ("-", "LNF") and gmlst_ok:
        return "gmlst_correct"

    if gmlst_is_near and chew_exact:
        if gmlst_ok:
            return "cds_boundary_diff"
        return "chew_correct"

    if not gmlst_is_near and gmlst_val not in ("-", "LNF") and chew_val in ("-", "LNF"):
        return "gmlst_correct"

    if gmlst_ok and chew_exact:
        return "cds_boundary_diff"

    if gmlst_ok and not chew_exact:
        return "gmlst_correct"
    if chew_exact and not gmlst_ok:
        if gmlst_is_near:
            return "chew_correct"
        return "chew_correct"

    return "both_unverified"


def process_genome(
    genome: Path,
    scheme: str,
    chewbbaca_schema: Path,
    output_dir: Path,
    *,
    gmlst_env: str = "pixi",
    gmlst_project: Path | None = None,
    gmlst_prefix: Path | None = None,
    chewbbaca_env: str = "chewbbaca",
    chewbbaca_prefix: Path | None = None,
    args_force: bool = False,
) -> dict[str, Any]:
    """Process a single genome and return summary statistics."""
    sample_name = genome.stem
    sample_dir = output_dir / sample_name
    sample_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Processing %s ...", sample_name)

    gmlst_time: float | None = None
    chew_time: float | None = None

    # --- Step 1: Run gmlst ---
    gmlst_tsv = sample_dir / "gmlst_result.tsv"
    if not gmlst_tsv.exists() or args_force:
        logger.info("  Running gmlst chew-fast ...")
        ok, gmlst_time = run_gmlst(
            genome,
            scheme,
            gmlst_tsv,
            gmlst_env=gmlst_env,
            gmlst_project=gmlst_project,
            gmlst_prefix=gmlst_prefix,
        )
        if not ok:
            return {"sample": sample_name, "error": "gmlst failed"}
        logger.info("  gmlst completed in %.1fs", gmlst_time)
    else:
        logger.info("  gmlst result exists, skipping (use --force to re-run)")

    # --- Step 2: Run chewBBACA ---
    chew_dir = sample_dir / "chewbbaca"
    chew_alleles = _find_chewbbaca_file(chew_dir, "results_alleles.tsv")
    if not chew_alleles or args_force:
        logger.info("  Running chewBBACA AlleleCall ...")
        ok, chew_time = run_chewbbaca(
            genome,
            chewbbaca_schema,
            chew_dir,
            chewbbaca_env=chewbbaca_env,
            chewbbaca_prefix=chewbbaca_prefix,
        )
        if not ok:
            return {"sample": sample_name, "error": "chewBBACA failed"}
        logger.info("  chewBBACA completed in %.1fs", chew_time)

    # --- Step 3: Parse results ---
    gmlst_results = parse_gmlst_tsv(gmlst_tsv)
    chew_results = parse_chewbbaca_results(chew_dir, genome_name=genome.name)
    chew_coords = parse_chewbbaca_contig_info(chew_dir, genome_name=genome.name)

    if not chew_results:
        logger.warning(
            "  chewBBACA results empty for %s — check FILE column matching", genome.name
        )
        alleles_file = chew_dir / "results_alleles.tsv"
        if alleles_file.exists():
            with alleles_file.open() as f:
                header = f.readline().strip()
                first_data = f.readline().strip()
            logger.warning(
                "  FILE column values: header=%s, first_row=%s",
                header.split("\t")[0],
                first_data.split("\t")[0] if first_data else "empty",
            )

    # --- Step 4: Compare ---
    comparison = compare_results(gmlst_results, chew_results)

    # Write comparison TSV
    comp_tsv = sample_dir / "comparison.tsv"
    with comp_tsv.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["locus", "gmlst", "chewbbaca", "consistent", "category"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(comparison)

    # --- Step 5: Statistics ---
    total = len(comparison)
    consistent = sum(1 for r in comparison if r["consistent"] == "YES")
    diff_rows = [r for r in comparison if r["consistent"] == "NO"]
    cat_counts = Counter(r["category"] for r in diff_rows)

    stats = {
        "sample": sample_name,
        "total_loci": total,
        "consistent": consistent,
        "consistent_pct": f"{consistent / total * 100:.1f}%" if total else "N/A",
        "differences": len(diff_rows),
        "categories": dict(cat_counts),
        "gmlst_time_sec": round(gmlst_time, 1) if gmlst_time is not None else None,
        "chewbbaca_time_sec": round(chew_time, 1) if chew_time is not None else None,
        "speedup": round(chew_time / gmlst_time, 1)
        if gmlst_time and chew_time and gmlst_time > 0
        else None,
    }

    # --- Step 6: BLAST verification of differences ---
    blast_results = []
    if diff_rows and chewbbaca_schema.exists():
        logger.info("  BLAST verifying %d differences ...", len(diff_rows))
        work_dir = sample_dir / "blast_work"
        work_dir.mkdir(exist_ok=True)

        # Build genome BLAST DB (once)
        genome_db = work_dir / "genome_db"
        subprocess.run(
            [
                "makeblastdb",
                "-in",
                str(genome),
                "-dbtype",
                "nucl",
                "-out",
                str(genome_db),
            ],
            capture_output=True,
            timeout=60,
        )

        for row in diff_rows:
            locus = row["locus"]
            allele_file = chewbbaca_schema / f"{locus}.fasta"
            if not allele_file.exists():
                continue

            entry = {
                "locus": locus,
                "gmlst": row["gmlst"],
                "chewbbaca": row["chewbbaca"],
                "category": row["category"],
            }

            allele_seqs = load_fasta(allele_file)

            # Method A: Extract chewBBACA's CDS and BLAST to allele DB
            coord = chew_coords.get(locus, "")
            if coord and coord not in ("LNF", ""):
                cds_seq = extract_cds_from_genome(genome, coord)
                if cds_seq:
                    blast_a = blast_cds_against_locus(
                        cds_seq, allele_file, work_dir, locus
                    )
                    entry["chew_cds_blast_allele"] = blast_a["allele"]
                    entry["chew_cds_blast_pident"] = f"{blast_a['pident']:.1f}"
                    entry["chew_cds_blast_coverage"] = f"{blast_a['coverage']:.3f}"
                    entry["chew_cds_blast_mismatch"] = blast_a["mismatch"]
                    entry["chew_cds_exact"] = (
                        blast_a["pident"] == 100.0 and blast_a["coverage"] >= 1.0
                    )

            # Method B: BLAST gmlst's allele against genome
            raw_gmlst = row["gmlst"]
            gmlst_allele_id = raw_gmlst
            if gmlst_allele_id.startswith("INF-"):
                gmlst_allele_id = gmlst_allele_id[4:]
            gmlst_allele_id = gmlst_allele_id.lstrip("~").rstrip("?")
            if gmlst_allele_id and gmlst_allele_id not in ("-", "LNF", "INF", ""):
                allele_key = f"{locus}_{gmlst_allele_id}"
                allele_seq = allele_seqs.get(allele_key, "")
                if allele_seq:
                    blast_b = blast_allele_against_genome(
                        allele_seq, genome_db, work_dir, allele_key
                    )
                    entry["gmlst_allele_in_genome"] = (
                        blast_b["pident"] == 100.0 and blast_b["coverage"] >= 1.0
                    )
                    entry["gmlst_allele_pident"] = f"{blast_b['pident']:.1f}"
                    entry["gmlst_allele_coverage"] = f"{blast_b['coverage']:.3f}"
                    entry["gmlst_allele_len"] = len(allele_seq)

            # Length-based evaluation for cds_boundary_diff
            chew_allele_name = entry.get("chew_cds_blast_allele", "")
            gmlst_allele_len = entry.get("gmlst_allele_len", 0)
            if isinstance(gmlst_allele_len, str):
                gmlst_allele_len = 0

            if chew_allele_name and gmlst_allele_len:
                chew_seq = allele_seqs.get(chew_allele_name, "")
                chew_allele_len = len(chew_seq) if chew_seq else 0
                entry["chew_allele_len"] = chew_allele_len
                entry["length_diff"] = gmlst_allele_len - chew_allele_len

                gmlst_key = f"{locus}_{gmlst_allele_id}"
                gmlst_seq = allele_seqs.get(gmlst_key, "")

                if gmlst_seq and chew_seq:
                    if chew_seq in gmlst_seq and len(gmlst_seq) > len(chew_seq):
                        entry["substring_relation"] = "gmlst_contains_chew"
                    elif gmlst_seq in chew_seq and len(chew_seq) > len(gmlst_seq):
                        entry["substring_relation"] = "chew_contains_gmlst"
                    else:
                        entry["substring_relation"] = "neither"

                if gmlst_allele_len > chew_allele_len:
                    entry["probable_correct"] = "gmlst"
                elif chew_allele_len > gmlst_allele_len:
                    entry["probable_correct"] = "chew"
                else:
                    entry["probable_correct"] = "equal"

            chew_val = row["chewbbaca"]
            if chew_val in ("NIPH", "NIPHEM"):
                gmlst_allele_id_raw = row["gmlst"]
                gmlst_aid = gmlst_allele_id_raw
                if gmlst_aid.startswith("INF-"):
                    gmlst_aid = gmlst_aid[4:]
                gmlst_aid = gmlst_aid.lstrip("~").rstrip("?")
                if gmlst_aid and gmlst_aid not in ("-", "LNF", "INF", ""):
                    gmlst_key = f"{locus}_{gmlst_aid}"
                    allele_seq_for_mc = allele_seqs.get(gmlst_key, "")
                    if allele_seq_for_mc:
                        mc = count_multicopy_hits(
                            allele_seq_for_mc, genome_db, work_dir, gmlst_key
                        )
                        entry["multicopy_hits"] = mc["n_hits"]
                        entry["multicopy_exact_hits"] = mc["n_exact"]
                        if mc["n_hits"] >= 2:
                            positions_str = ";".join(
                                f"{c}:{s}-{e}" for c, s, e in mc["hit_positions"][:5]
                            )
                            entry["multicopy_positions"] = positions_str
                            entry["multicopy_verified"] = True
                        else:
                            entry["multicopy_verified"] = False

            blast_results.append(entry)

        for entry in blast_results:
            entry["verdict"] = determine_verdict(entry)

        if blast_results:
            blast_tsv = sample_dir / "blast_verification.tsv"
            all_fields: list[str] = []
            seen = set()
            for entry in blast_results:
                for key in entry:
                    if key not in seen:
                        seen.add(key)
                        all_fields.append(key)
            with blast_tsv.open("w", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=all_fields, delimiter="\t", extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(blast_results)

        verdict_counts = Counter(r.get("verdict", "unverified") for r in blast_results)
        stats["verdicts"] = dict(verdict_counts)
        stats["gmlst_correct"] = verdict_counts.get("gmlst_correct", 0)
        stats["chew_correct"] = verdict_counts.get("chew_correct", 0)
        stats["cds_boundary_diff"] = verdict_counts.get("cds_boundary_diff", 0)
        stats["chew_inf_bsr_bug"] = verdict_counts.get("chew_inf_bsr_bug", 0)
        stats["both_unverified"] = verdict_counts.get("both_unverified", 0)
        stats["chew_niph_verified"] = verdict_counts.get("chew_niph_verified", 0)
        stats["chew_niph_unverified"] = verdict_counts.get("chew_niph_unverified", 0)

        probable_counts = Counter(
            r.get("probable_correct", "")
            for r in blast_results
            if r.get("probable_correct")
        )
        stats["probable_gmlst"] = probable_counts.get("gmlst", 0)
        stats["probable_chew"] = probable_counts.get("chew", 0)
        stats["probable_equal"] = probable_counts.get("equal", 0)

        substring_counts = Counter(
            r.get("substring_relation", "")
            for r in blast_results
            if r.get("substring_relation")
        )
        stats["gmlst_contains_chew"] = substring_counts.get("gmlst_contains_chew", 0)
        stats["chew_contains_gmlst"] = substring_counts.get("chew_contains_gmlst", 0)

        total_diffs = len(blast_results)
        if total_diffs > 0:
            gmlst_score = stats["gmlst_correct"] + stats["cds_boundary_diff"]
            chew_score = stats["chew_correct"]
            stats["gmlst_accuracy_on_diffs"] = f"{gmlst_score / total_diffs * 100:.1f}%"
            stats["chew_accuracy_on_diffs"] = f"{chew_score / total_diffs * 100:.1f}%"
        else:
            stats["gmlst_accuracy_on_diffs"] = "N/A"
            stats["chew_accuracy_on_diffs"] = "N/A"

    logger.info(
        "  %s: %d/%d consistent (%.1f%%), %d diffs",
        sample_name,
        consistent,
        total,
        consistent / total * 100 if total else 0,
        len(diff_rows),
    )

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark gmlst vs chewBBACA cgMLST with BLAST verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--genome", type=Path, help="Single genome FASTA file")
    parser.add_argument(
        "--genome-dir", type=Path, help="Directory of genome FASTA files"
    )
    parser.add_argument("--scheme", required=True, help="gmlst scheme name")
    parser.add_argument(
        "--chewbbaca-schema",
        type=Path,
        required=True,
        help="chewBBACA schema directory",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument(
        "--gmlst-cache", type=Path, default=None, help="gmlst cache dir override"
    )
    parser.add_argument(
        "--gmlst-env", default="pixi", help="conda env for gmlst (default: pixi)"
    )
    parser.add_argument(
        "--gmlst-project",
        type=Path,
        default=None,
        help="gmlst project root (for pixi run)",
    )
    parser.add_argument(
        "--chewbbaca-env",
        default="chewbbaca",
        help="conda env name for chewBBACA (default: chewbbaca)",
    )
    parser.add_argument(
        "--chewbbaca-prefix",
        type=Path,
        default=None,
        help="Direct path to chewBBACA conda env (e.g. ~/.mamba/envs/chewbbaca). Bypasses conda run.",
    )
    parser.add_argument(
        "--gmlst-prefix",
        type=Path,
        default=None,
        help="Direct path to gmlst conda/pixi env bin dir. Bypasses conda run.",
    )
    parser.add_argument(
        "--mode", default="chew-fast", help="gmlst cgmlst mode (default: chew-fast)"
    )
    parser.add_argument("--skip-gmlst", action="store_true", help="Skip running gmlst")
    parser.add_argument(
        "--skip-chewbbaca", action="store_true", help="Skip running chewBBACA"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-run gmlst and chewBBACA even if results exist",
    )
    args = parser.parse_args()

    # Collect genomes
    if args.genome:
        genomes = [args.genome]
    elif args.genome_dir:
        genomes = sorted(
            p
            for p in args.genome_dir.iterdir()
            if p.suffix in (".fna", ".fasta", ".fa") and p.is_file()
        )
    else:
        parser.error("Either --genome or --genome-dir is required")

    if not genomes:
        parser.error("No genome files found")

    args.output.mkdir(parents=True, exist_ok=True)
    all_stats = []

    for genome in genomes:
        try:
            stats = process_genome(
                genome,
                args.scheme,
                args.chewbbaca_schema,
                args.output,
                gmlst_env=args.gmlst_env,
                gmlst_project=args.gmlst_project,
                gmlst_prefix=args.gmlst_prefix,
                chewbbaca_env=args.chewbbaca_env,
                chewbbaca_prefix=args.chewbbaca_prefix,
                args_force=args.force,
            )
            all_stats.append(stats)
        except Exception as exc:
            logger.error("Failed to process %s: %s", genome.name, exc)
            all_stats.append({"sample": genome.stem, "error": str(exc)})

    # Write summary
    summary_file = args.output / "summary.json"
    with summary_file.open("w") as f:
        json.dump(all_stats, f, indent=2)

    # Print summary table
    print(f"\n{'=' * 100}")
    print(f"Benchmark Summary: {len(all_stats)} genomes")
    print(f"{'=' * 100}")
    print(
        f"{'Sample':<28} {'Loci':>5} {'Cons%':>6} {'Diff':>5} {'gmlst(s)':>8} {'chew(s)':>8} {'Spd':>5} {'g✓':>4} {'c✓':>4} {'cdsΔ':>5} {'NIPH✓':>6} {'NIPH?':>6} {'len→g':>5} {'sub→g':>5}"
    )
    print("-" * 125)
    for s in all_stats:
        if "error" in s:
            print(f"{s['sample']:<28} ERROR: {s['error'][:40]}")
        else:
            gmlst_t = s.get("gmlst_time_sec", 0)
            chew_t = s.get("chewbbaca_time_sec", 0)
            speedup = s.get("speedup")
            speedup_str = f"{speedup:.1f}x" if speedup else "-"
            gmlst_str = (
                f"{gmlst_t:.1f}"
                if gmlst_t and gmlst_t > 0
                else "cached"
                if gmlst_t is None
                else "-"
            )
            chew_str = (
                f"{chew_t:.1f}"
                if chew_t and chew_t > 0
                else "cached"
                if chew_t is None
                else "-"
            )
            print(
                f"{s['sample']:<28} {s['total_loci']:>5} {s['consistent_pct']:>6} "
                f"{s['differences']:>5} {gmlst_str:>8} {chew_str:>8} "
                f"{speedup_str:>5} "
                f"{s.get('gmlst_correct', 0):>4} "
                f"{s.get('chew_correct', 0):>4} "
                f"{s.get('cds_boundary_diff', 0):>5} "
                f"{s.get('chew_niph_verified', 0):>6} "
                f"{s.get('chew_niph_unverified', 0):>6} "
                f"{s.get('probable_gmlst', 0):>5} "
                f"{s.get('gmlst_contains_chew', 0):>5}"
            )
    print("-" * 125)
    valid = [s for s in all_stats if "error" not in s]
    if valid:
        avg_pct = sum(
            s["consistent"] / max(s["total_loci"], 1) * 100 for s in valid
        ) / len(valid)
        timed_gmlst = [
            s.get("gmlst_time_sec")
            for s in valid
            if s.get("gmlst_time_sec") is not None
        ]
        timed_chew = [
            s.get("chewbbaca_time_sec")
            for s in valid
            if s.get("chewbbaca_time_sec") is not None
        ]
        total_gmlst_t = sum(timed_gmlst) if timed_gmlst else 0
        total_chew_t = sum(timed_chew) if timed_chew else 0
        avg_spd = total_chew_t / total_gmlst_t if total_gmlst_t > 0 else 0
        total_gmlst_correct = sum(s.get("gmlst_correct", 0) for s in valid)
        total_chew_correct = sum(s.get("chew_correct", 0) for s in valid)
        total_cds_diff = sum(s.get("cds_boundary_diff", 0) for s in valid)
        total_bsr_bug = sum(s.get("chew_inf_bsr_bug", 0) for s in valid)
        total_niph_v = sum(s.get("chew_niph_verified", 0) for s in valid)
        total_niph_u = sum(s.get("chew_niph_unverified", 0) for s in valid)
        total_prob_g = sum(s.get("probable_gmlst", 0) for s in valid)
        total_prob_c = sum(s.get("probable_chew", 0) for s in valid)
        total_sub_g = sum(s.get("gmlst_contains_chew", 0) for s in valid)
        print(
            f"{'TOTAL':<28} {'':>5} {avg_pct:>5.1f}% "
            f"{sum(s['differences'] for s in valid):>5} "
            f"{total_gmlst_t / len(timed_gmlst) if timed_gmlst else 0:>7.1f} "
            f"{total_chew_t / len(timed_chew) if timed_chew else 0:>7.1f} "
            f"{avg_spd:>4.1f}x "
            f"{total_gmlst_correct:>4} "
            f"{total_chew_correct:>4} "
            f"{total_cds_diff:>5} "
            f"{total_niph_v:>6} "
            f"{total_niph_u:>6} "
            f"{total_prob_g:>5} "
            f"{total_sub_g:>5}"
        )
    print("\nVerdict legend:")
    print("  g✓       = gmlst confirmed correct, chewBBACA wrong")
    print("  c✓       = chewBBACA confirmed correct, gmlst wrong")
    print("  cdsΔ     = CDS boundary difference (both valid, different alleles)")
    print("  NIPH✓    = chewBBACA NIPH confirmed by multi-copy BLAST verification")
    print("  NIPH?    = chewBBACA NIPH not verified (single copy in genome)")
    print("  len→g    = cdsΔ cases where gmlst's allele is longer")
    print("  sub→g    = cdsΔ cases where gmlst allele contains chewBBACA allele")
    print(f"\nDetailed results: {args.output}")
    print(f"Summary JSON: {summary_file}")


if __name__ == "__main__":
    main()
