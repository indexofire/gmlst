# cgMLST Guide

This guide covers `gmlst typing cgmlst`, including mode selection, FASTA and FASTQ behavior, prefiltering, CDS-aware classification, and performance tuning. For the full CLI surface, see [commands.md](commands.md). For broader implementation context, see [architecture.md](architecture.md).

## Overview

cgMLST extends the classical seven-locus MLST idea to hundreds or thousands of loci across a core genome set. That gives you much finer resolution for outbreak analysis, surveillance, and population structure work.

In practical terms:

- MLST is small, stable, and fast for lineage naming
- cgMLST is larger, more discriminating, and better suited to high-resolution comparison

`gmlst` keeps both workflows under the same CLI, but `typing cgmlst` has extra logic for large schemes, CDS-aware classification, and backend-specific speed paths.

## Quick Start

The default backend for cgMLST is `minimap2`.

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
```

Typical TSV-style output:

```tsv
FILE	SCHEME	ST	dnaA	ftsZ	gyrB	...
sample.fna	vparahaemolyticus_3	-	12	44	109	...
```

For many cgMLST schemes, ST may be `-` because the main value is the per-locus profile, not a compact legacy ST label.

## cgMLST Modes

Choose a mode based on dataset size and how much rescue logic you want.

### `standard`

Conservative mode. No forced chew-style overrides.

Use it when:

- you want the plainest behavior
- you are comparing results across backends
- you are working with FASTQ, because chew-style modes are forced back to `standard` there

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode standard sample.fna
```

### `chew-fast`

Adds exact-hash resolution, minimap2 hash prefiltering, automatic missing-locus refinement with a default cap of 500 loci, and targeted `blastn` evidence fallback with a default cap of 500 loci.

Use it when:

- you want a strong speed and recovery balance for FASTA assemblies
- your scheme is large enough that early filtering helps

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode chew-fast sample.fna
```

### `chew-ultrafast`

Builds on `chew-fast` with representative-only main alignment, disabled CIGAR emission, an ultrafast minimap2 speed profile, a strict low-confidence rescue cap of 120 loci, and an adaptive second pass.

Use it when:

- your scheme has 1000 or more loci
- you need throughput first, then a focused rescue pass

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode chew-ultrafast sample.fna
```

### `chew-bsr`

Adds protein-level exact-hash pre-resolution on top of `chew-fast`, with optional BSR confirmation controlled by environment variables.

Use it when:

- you need extra protein-aware confirmation behavior
- you are investigating edge cases where DNA-only pre-resolution is not enough

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode chew-bsr sample.fna
```

### `chew-balanced`

Uses exact-hash resolution, minimap2 hash prefiltering, and targeted `blastn` fallback without the more aggressive ultrafast path.

Use it when:

- you want a middle ground between `standard` and the most aggressive acceleration profiles

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode chew-balanced sample.fna
```

## FASTA cgMLST

FASTA assemblies get the richest optimization path. This is where chew-style modes are active and where prefiltering, exact-hash resolution, and targeted evidence fallback have the most impact.

Common FASTA examples:

```bash
# Default path
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna

# Enable a custom prefilter shape
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --prefilter-k 31 \
  --prefilter-top-n 20 \
  --prefilter-min-loci-fraction 0.2 \
  sample.fna

# Disable prefilter explicitly
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --no-prefilter sample.fna

# Use a faster chew-style mode for a large scheme
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode chew-ultrafast sample.fna
```

Why FASTA gets more options:

- assemblies give stable locus boundaries for exact-hash and CDS-aware logic
- minimap2 prefiltering is more effective on assembled contigs
- second-pass rescue is cheaper when the candidate space is already narrow

## FASTQ cgMLST

FASTQ follows a KMA-first policy.

If you request `-b minimap2` with FASTQ inputs, `gmlst` automatically switches to `-b kma`. Chew-style modes are compatibility-only in FASTQ mode and are forced back to `standard`.

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  -b minimap2 reads_R1.fastq.gz reads_R2.fastq.gz
```

Effective behavior:

- backend is auto-switched to `kma`
- cgMLST mode is treated as `standard`
- per-sample threads may be auto-raised through `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS`
- `--call-policy chewbbaca` is rejected for FASTQ input

Recommended FASTQ run:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  -b kma -t 8 reads_R1.fastq.gz reads_R2.fastq.gz
```

Why this happens:

- chew-style accelerations are designed around FASTA assemblies
- KMA is a stronger fit for read mapping in cgMLST FASTQ workflows
- automatic switching avoids a slow or misleading configuration

## Prefiltering

Prefiltering reduces the number of loci that need full downstream alignment or rescue work.

CLI options:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --prefilter-k 31 \
  --prefilter-top-n 20 \
  --prefilter-min-loci-fraction 0.15 \
  sample.fna
```

Meaning of the options:

- `--prefilter-k`, k-mer size for the prefilter
- `--prefilter-top-n`, how many candidate loci to keep per query step
- `--prefilter-min-loci-fraction`, minimum fraction of loci required to keep the prefilter path active

Important behavior:

- schemes larger than the auto-skip threshold can bypass prefiltering
- the default auto-skip threshold is 3000 loci
- for `-b kma` and default `-b minimap2`, cgMLST prefilter can be skipped in favor of the persistent full-index path

## CDS Prediction

`gmlst` uses Pyrodigal for cgMLST CDS prediction in the exact-hash and chew-style path.

To export predicted CDS coordinates:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cds-coordinates-out cds_coordinates.tsv \
  sample.fna
```

Why coordinate export is useful:

- it helps compare predicted coding regions between runs
- it supports debugging chewBBACA-style locus classification differences
- it gives you a concrete record of what the CDS gate saw

Example coordinate TSV:

```tsv
sample	contig	start	end	strand	locus
sample.fna	contig_1	1042	1983	+	dnaA
sample.fna	contig_1	4021	4899	-	gyrB
```

## Call Policy

The call policy controls how locus results are classified for reporting.

### Default policy

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --call-policy default sample.fna
```

Use this when you want the normal `gmlst` interpretation without chewBBACA-style output classes.

### chewBBACA-compatible policy

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --call-policy chewbbaca sample.fna
```

Important limits:

- `--call-policy chewbbaca` requires FASTA assemblies
- raw calls stay unchanged, but output uses chew-style per-locus class labels
- CDS-gated classification is enabled by default

## CDS Gating

CDS gating decides whether chewBBACA-style classification should only consider matched sequence context that passes the CDS prediction filter.

```bash
# Default behavior when using --call-policy chewbbaca
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --call-policy chewbbaca \
  --chew-cds-gate \
  sample.fna

# Relax the gate
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --call-policy chewbbaca \
  --no-chew-cds-gate \
  sample.fna
```

Use the default gate when you want classification to stay close to coding-sequence expectations. Turn it off only when you are deliberately reviewing edge cases in lower-confidence sequence context.

## Evidence Fallback

Low-confidence loci can go through targeted fallback paths depending on mode and environment settings.

Supported evidence fallback backends are:

- `blastn`
- `kma`
- `nucmer`

These fallbacks are targeted, not full reruns. They are meant to rescue uncertain loci after the main pass has narrowed the search space.

Representative configuration:

```bash
export GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=blastn
export GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI=300

gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
```

## Performance Tuning

Use these rules as a starting point:

- small to medium FASTA schemes, start with `standard` or `chew-balanced`
- large FASTA schemes, start with `chew-ultrafast`
- FASTQ, use `-b kma` and set `-t 8` to `-t 16` when CPU is available
- many samples, add `--max-workers` for sample-level parallelism

Examples:

```bash
# Large scheme, fast assembly path
gmlst typing cgmlst -s vparahaemolyticus_3 \
  --cgmlst-mode chew-ultrafast \
  --max-workers 4 \
  samples/*.fna

# FASTQ run with tuned threads
gmlst typing cgmlst -s vparahaemolyticus_3 \
  -b kma -t 12 reads_R1.fastq.gz reads_R2.fastq.gz
```

Operational caveats:

- `--max-workers > 1` switches to sample-level parallelism, which means per-sample backend threads are reduced to `1`
- `--cds-coordinates-out` is intended for single-worker runs
- `nucmer` ignores thread settings

## Large Scheme Handling

For schemes with 1000 or more loci:

- prefer `chew-ultrafast` for FASTA assemblies
- expect the prefilter to matter more when the candidate space is still manageable
- remember that prefilter auto-skip can trigger above the configured threshold
- use `--max-workers` carefully, because each sample can still be expensive on its own

For very large schemes, the fastest run is not always the one with the most workers. You usually get better throughput by balancing sample-level parallelism with enough threads for the active backend.

## Environment Variables

These variables affect cgMLST-specific behavior.

### FASTA and minimap2 tuning

- `GMLST_MINIMAP2_FASTA_SPEED_PROFILE=default|fast|ultrafast`
- `GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI=adaptive|<int>`
- `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI=<int>`
- `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER=1`

### FASTQ and KMA tuning

- `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS=<int>`
- `GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1|0`
- `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI=<int>`

### Prefilter and exact-hash controls

- `GMLST_CGMLST_PREFILTER_MAX_LOCI=<int>`
- `GMLST_CGMLST_EXACT_HASH_PREFILTER=1`

### CDS prediction and export

- `GMLST_CGMLST_CDS_PREDICTION_MODE=single|meta`
- `GMLST_CGMLST_CDS_TRAINING_FILE=/path/to/pyrodigal_training.trn`
- `GMLST_CGMLST_CDS_CLOSED_ENDS=1|0`
- `GMLST_CGMLST_CDS_COORDINATES_OUT=/path/to/cds_coordinates.tsv`

### Other related settings

- `GMLST_CACHE_DIR=/path/to/cache`
- `GMLST_TMPDIR=/path/to/tmp`

### Evidence fallback

- `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=none|blastn|kma|nucmer`
- `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI=<int>`

### Example environment setup

```bash
export GMLST_MINIMAP2_FASTA_SPEED_PROFILE=ultrafast
export GMLST_CGMLST_PREFILTER_MAX_LOCI=3000
export GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS=8
export GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=blastn

gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
```
