# Typing Troubleshooting

Missing STs, split genes, multicopy alleles, missing loci, FASTQ pairing, and cgMLST mode selection.

## Typing Issues

### ST is `-`

An ST of `-` means there is no exact profile match. Common reasons:

- one or more loci are missing
- one or more loci are partial
- one or more loci are closest or novel-like instead of exact
- multicopy conflicts exist, such as `1,2`

What to do next:

```bash
gmlst typing mlst -s saureus_1 --format json sample.fasta -o sample.json
gmlst typing mlst -s saureus_1 --format pretty sample.fasta
```

The JSON output gives more detail for each locus.

### A gene is split across two contigs — what happens?

With the `blastn` and `minimap2` backends, gmlst joins the per-contig fragment
alignments of a split locus. Contigs that overlap inside the gene with agreeing
sequence are tiled into one reconstructed alignment that can be called exactly;
contigs that merely abut (no overlap) can never prove the junction, so the locus
stays a partial `?` call — but its reported coverage is the combined coverage of
all fragments, and JSON output lists every fragment
(`contig`, `allele_start`, `allele_end`). The join never fabricates an exact
call across an unsampled gap. Raise or lower the required overlap with
`--min-join-overlap` (default 10 bp). For assemblies that break genes cleanly
and often, typing the original reads with `-b kma` remains the most robust
path — read-level consensus reconstructs alleles from many overlapping reads.

### I see multicopy alleles like `1,2`

That means multiple conflicting hits were found for the locus. This can happen with duplicated loci, repeated sequence, or ambiguous mapping.

If you are reviewing assemblies with `blastn`, try:

```bash
gmlst typing mlst -s saureus_1 -b blastn --count-same-copy sample.fasta
```

This can expose same-allele copy notation such as `1,1` in supported cases.

### Many loci are missing

Common causes:

- wrong scheme for the organism
- low assembly quality
- truncated contigs
- FASTQ data used with a backend that does not support FASTQ

Check the scheme first:

```bash
gmlst scheme show -s saureus_1
gmlst scheme list -n aureus
```

Then try a backend that fits the input type:

- FASTA: `blastn`, `minimap2`, `nucmer`, `kma`
- FASTQ: `kma` or `minimap2`

### Typing is slower than expected

Try these checks:

```bash
gmlst typing mlst -s saureus_1 --max-workers 4 samples/*.fasta -o results.tsv
gmlst typing cgmlst -s vparahaemolyticus_3 -t 8 sample.fasta
```

More tips are in the [Performance Tips](performance.md#performance-tips) section below.

### FASTQ input fails with `blastn` or `nucmer`

That is expected. `blastn` and `nucmer` are assembly-oriented in this project. Use `kma` or `minimap2` for FASTQ input.

Example:

```bash
gmlst typing mlst -s saureus_1 -b kma reads_R1.fastq.gz reads_R2.fastq.gz
gmlst typing mlst -s saureus_1 -b minimap2 reads_R1.fastq.gz reads_R2.fastq.gz
```

## FASTQ-specific Issues

### How does paired-end detection work?

`gmlst` detects common naming patterns such as:

- `_R1` and `_R2`
- `_1` and `_2`
- `.1` and `.2`

Supported file extensions include `.fastq`, `.fq`, and `.gz` variants.

### My FASTQ files are not being treated as a pair

Rename them to a standard pair pattern, or pass the pair explicitly in matching order.

Example:

```bash
gmlst typing mlst -s saureus_1 -b kma sample_R1.fastq.gz sample_R2.fastq.gz
```

### Which backends support FASTQ?

- supported: `kma`, `minimap2`
- not supported for FASTQ typing here: `blastn`, `nucmer`

## cgMLST-specific Issues

### Why did `typing cgmlst` switch my FASTQ run to KMA?

This is expected. For FASTQ input, the CLI enforces a KMA-first policy. If you request `-b minimap2` for cgMLST FASTQ, `gmlst` switches to `kma` and treats `--cgmlst-mode` as compatibility-only, effectively `fast`.

This behavior is documented in [typing pipeline](../architecture/typing-pipeline.md) and [CLI reference](../usage/cli/index.md).

### Which cgMLST mode should I use?

Start with:

- `fast` for common FASTA cgMLST work
- `ultrafast` for larger FASTA batches where speed matters more
- `balanced` if you want more fallback review

Examples:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode ultrafast sample.fna
```

### Large cgMLST schemes run very slowly

For large schemes, increase threads for backends that benefit from them, especially KMA.

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 8 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 16 sample.fna
```

## Reading a result row

```text
FILE        SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample.fna  saureus_1   1   1     1     1     1    1    1    1
sample2.fna saureus_1   -   1     ~2    3?    -    1    1    1
```

- `ST = -` with `~2` and `3?` means no exact profile exists yet.
- A single `-` usually means assembly fragmentation, not a wrong scheme.
- Several `-` across many loci usually means the wrong scheme or species.

## When to re-type with another backend

| Situation | Try |
| --- | --- |
| MLST gives partial calls on a fragmented assembly | `-b kma` on the original reads |
| cgMLST FASTA run has many `~` calls | `--cgmlst-mode balanced` or `-b blastn` |
| Suspected paralogs / multicopy | `-b blastn --count-same-copy` |
| Very large scheme, time-limited | `--max-workers` across samples |

## Distinguish "wrong scheme" from "bad assembly"

```bash
# 1. Is the scheme right?
gmlst scheme show -s saureus_1

# 2. What do the loci look like?
gmlst typing mlst -s saureus_1 --format json sample.fna -o out.json

# 3. Are reads better than the assembly?
gmlst typing mlst -s saureus_1 -b kma sample_R1.fq.gz sample_R2.fq.gz
```

If reads recover the loci but the assembly does not, the problem is assembly
fragmentation. If both miss the same loci, revisit the scheme or species.
