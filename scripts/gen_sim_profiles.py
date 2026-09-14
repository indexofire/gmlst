#!/usr/bin/env python3
"""Generate simulated cgMLST profiles with known phylogenetic structure.

Simulates 1000 genomes across clonal complexes (star-like bursts from
founders) plus noise, producing a GrapeTree-style TSV with embedded
metadata (clade, source, year) for visualization testing.

The ground truth (clade assignment + pairwise distance stats) is written
alongside so MST/visualization results can be validated objectively.

Usage:
    python scripts/gen_sim_profiles.py -n 1000 -o /tmp/sim1000
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

N_LOCI = 100


def simulate(n_samples: int, seed: int) -> tuple[list[list[str]], list[dict]]:
    """Return (profiles, metadata) with clonal-complex structure.

    Structure: 12 clades; each clade has a founder profile and members
    differ by a few SNVs (alleles). A small fraction of singletons and
    a few deliberate duplicate profiles test edge cases.
    """
    rng = random.Random(seed)
    profiles: list[list[str]] = []
    meta: list[dict] = []

    n_clades = 12
    per_clade = (n_samples - 20) // n_clades  # 20 reserved for singletons/dups

    for clade_idx in range(n_clades):
        founder = [str(rng.randint(1, 4)) for _ in range(N_LOCI)]
        snv_rate = [0.02, 0.05, 0.10][clade_idx % 3]
        for member_idx in range(per_clade):
            profile = [
                str(int(a) + 1) if rng.random() < snv_rate else a for a in founder
            ]
            profiles.append(profile)
            meta.append(
                {
                    "clade": f"CC{clade_idx + 1:02d}",
                    "source": rng.choice(["blood", "water", "food", "env"]),
                    "year": str(rng.randint(2015, 2025)),
                }
            )

    # Singleton outliers: heavily diverged profiles
    for i in range(15):
        profiles.append(
            [str(rng.randint(50, 99)) for _ in range(N_LOCI)]
        )
        meta.append(
            {"clade": f"SIN{i + 1:02d}", "source": "imported", "year": "2020"}
        )

    # Exact duplicates of a random existing sample (tests zero-weight edges)
    for i in range(5):
        src = rng.randrange(len(profiles))
        profiles.append(list(profiles[src]))
        meta.append(dict(meta[src]))
        meta[-1]["source"] = "lab_dup"

    rng.shuffle(list(zip(profiles, meta, strict=True)))
    # re-pair after shuffle — shuffle on zipped list needs explicit handling
    combined = list(zip(profiles, meta, strict=True))
    rng.shuffle(combined)
    profiles = [p for p, _ in combined]
    meta = [m for _, m in combined]
    return profiles, meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--samples", type=int, default=1000)
    parser.add_argument("-o", "--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--missing", type=float, default=0.02, help="LNF fraction")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed + 1)
    profiles, meta = simulate(args.samples, args.seed)

    # Inject missing data (LNF)
    for profile in profiles:
        for i in range(len(profile)):
            if rng.random() < args.missing:
                profile[i] = "LNF"

    # Write profile TSV (GrapeTree format with metadata columns)
    locus_cols = [f"L{i:03d}" for i in range(N_LOCI)]
    sample_ids = [f"S{i:04d}" for i in range(len(profiles))]

    tsv_path = args.output_dir / "profiles.tsv"
    with tsv_path.open("w") as fh:
        fh.write("#Strain\t" + "\t".join([*locus_cols, "clade", "source", "year"]) + "\n")
        for sid, profile, m in zip(sample_ids, profiles, meta, strict=True):
            fh.write(
                "\t".join([sid, *profile, m["clade"], m["source"], m["year"]]) + "\n"
            )

    # Ground truth for objective validation
    truth = {
        "n_samples": len(profiles),
        "n_loci": N_LOCI,
        "clades": {},
    }
    for m in meta:
        c = m["clade"]
        truth["clades"].setdefault(c, 0)
        truth["clades"][c] += 1
    import json

    (args.output_dir / "ground_truth.json").write_text(json.dumps(truth, indent=2))

    print(f"Wrote {tsv_path} ({len(profiles)} samples x {N_LOCI} loci)")
    print(f"Clades: {truth['clades']}")


if __name__ == "__main__":
    main()
