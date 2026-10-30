# Performance

Backend choice, thread and worker tuning, batch strategy, and measured parallel speedups.

## Performance Tips

### Which backend is usually fastest?

There is no single answer, but these are good starting points:

- assembly MLST: start with `blastn` or `minimap2`
- FASTQ typing: start with `kma`
- FASTA cgMLST: start with `minimap2` and a chew-style mode if appropriate
- large FASTQ cgMLST: expect KMA-first behavior

### How should I tune threads?

Use sample-level parallelism for many independent samples and backend threads for expensive per-sample work.

`--max-workers N` and `-t/--threads` are complementary, not combinable: with `--max-workers > 1`, per-sample backend threads are forced to 1 and a warning is printed. Prefer `--max-workers` whenever you have many samples — especially with the `kma` and `nucmer` backends, whose single-sample alignment cannot use extra threads at all (measured: `kma -t 1` vs `-t 16` differ by ~5%).

Examples:

```bash

## Pick the lever first

| Workload | Lever | Example |
| --- | --- | --- |
| Many small samples | `--max-workers` | `--max-workers 16` |
| One large cgMLST sample | `-t` | `-t 8` |
| Repeated cohort | cache reuse | download and index once |
| FASTQ cohort | `kma` plus workers | `-b kma --max-workers 16` |

Measure instead of guessing:

```bash
gmlst utils benchmark -s saureus_1 -b blastn,minimap2,nucmer -r 3 samples/*.fna
gmlst utils benchmark -s vparahaemolyticus_3 --cgmlst-gate -b minimap2 samples/*.fna
```

`--max-workers` and `-t` do not compose: with more than one worker, per-sample
threads are forced to 1. That is intentional, and the CLI warns when both are
set.

## A staged tuning example

```bash
# 1. Start with the default and measure wall time
time gmlst typing mlst -s saureus_1 -t 8 sample.fna

# 2. Many samples? prefer workers
time gmlst typing mlst -s saureus_1 -t 1 --max-workers 16 samples/*.fna

# 3. Large cgMLST scheme? keep threads per sample
time gmlst typing cgmlst -s vparahaemolyticus_3 -t 8 sample.fna
```
