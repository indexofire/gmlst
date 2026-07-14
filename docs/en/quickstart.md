# Quick Start

This guide walks through a complete first run of `gmlst`, from downloading a scheme to typing FASTA and FASTQ samples.

If you have not installed the tool yet, start with [Installation](installation.md).

## Prerequisites

Before you begin, make sure:

- `gmlst` is installed and on `PATH`
- at least one backend is available, for example `blastn`
- you have internet access for scheme download
- your sample data is in FASTA or FASTQ format

Useful checks:

```bash
gmlst --version
gmlst utils check -b blastn
gmlst scheme list -p pubmlst -t mlst
```

## Step 1: Download an MLST scheme

First, list schemes so you know what names are available:

```bash
gmlst scheme list
gmlst scheme list -p pubmlst -t mlst
```

Download a scheme by its canonical scheme name. Here we use `saureus_1`:

```bash
gmlst scheme download -s saureus_1
```

What this does:

- resolves the provider for `saureus_1`
- downloads the allele FASTA files and profile table
- stores the scheme in the local cache for later reuse

You can inspect the downloaded scheme afterward:

```bash
gmlst scheme show -s saureus_1
```

## Step 2: Type your first sample

For an assembled genome in FASTA format, the most direct command is:

```bash
gmlst typing mlst -s saureus_1 sample.fasta
```

This runs MLST typing against the downloaded scheme using the default `blastn` backend.

Typical TSV output looks like this:

```tsv
FILE	SCHEME	ST	arcC	aroE	glpF	gmk	pta	tpi	yqiL
sample	saureus_1	1	1	1	1	1	1	1	1
```

If you prefer a more human-readable one line summary for a quick check:

```bash
gmlst typing mlst -s saureus_1 --format pretty sample.fasta
```

Example output:

```text
sample: ST=1
```

## Step 3: Try different backends

`gmlst` supports multiple alignment backends. The best choice depends on your input type and the balance you want between speed and sensitivity.

### `blastn`

Good default for assembled genomes.

```bash
gmlst typing mlst -s saureus_1 -b blastn sample.fasta
```

### `kma`

Works with FASTA and FASTQ. Often useful when comparing read-based runs.

```bash
gmlst typing mlst -s saureus_1 -b kma sample.fasta
```

### `minimap2`

Supports FASTA and FASTQ. FASTQ mode includes targeted validation on uncertain loci.

```bash
gmlst typing mlst -s saureus_1 -b minimap2 sample.fasta
```

### `nucmer`

Assembly-oriented whole genome alignment from MUMmer4.

```bash
gmlst typing mlst -s saureus_1 -b nucmer sample.fasta
```

### Compare backends in one run

Use the benchmark utility if you want a side by side comparison:

```bash
gmlst utils benchmark -s saureus_1 -b blastn,kma,minimap2,nucmer sample.fasta
```

## Step 4: Batch processing and output files

You can type multiple samples in one command.

### Write TSV output

```bash
gmlst typing mlst -s saureus_1 samples/*.fasta -o results.tsv
```

This writes a tab-separated table that is easy to open in spreadsheets or parse in scripts.

### Write JSON output

```bash
gmlst typing mlst -s saureus_1 --format json samples/*.fasta -o results.json
```

JSON output is useful for downstream automation, reporting, or novel allele extraction.

### Increase sample-level parallelism

If you are processing many samples, you can run multiple samples in parallel:

```bash
gmlst typing mlst -s saureus_1 --max-workers 4 samples/*.fasta -o results.tsv
```

## Step 5: FASTQ paired-end input

`gmlst` can auto-detect common paired-end naming patterns and pass them to supported backends as true paired reads.

Recognized patterns include:

- `sample_R1.fastq.gz` and `sample_R2.fastq.gz`
- `sample_1.fq.gz` and `sample_2.fq.gz`
- `sample.1.fastq.gz` and `sample.2.fastq.gz`

### Paired-end MLST with `kma`

```bash
gmlst typing mlst -s saureus_1 -b kma reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

### Paired-end MLST with `minimap2`

```bash
gmlst typing mlst -s saureus_1 -b minimap2 reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

Notes:

- paired reads are not pre-merged into one temporary file
- `kma` and `minimap2` support FASTQ directly
- `blastn` and `nucmer` are generally assembly-oriented backends

## Step 6: Run cgMLST typing

Use `typing cgmlst` for larger schemes with many loci:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fasta
```

The default backend for `typing cgmlst` is `minimap2`.

You can select different cgMLST runtime modes depending on speed and sensitivity needs:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode standard sample.fasta
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-fast sample.fasta
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-ultrafast sample.fasta
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-balanced sample.fasta
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-bsr sample.fasta
```

For FASTQ inputs, `typing cgmlst` automatically favors a `kma`-based path even if you requested `minimap2`, because the chew-style optimizations are FASTA-oriented.

## Step 7: Run scheme-free typing

If you want to type samples without selecting a predefined scheme, use `tgmlst`:

```bash
gmlst typing tgmlst sample.fasta
```

Useful options include:

```bash
gmlst typing tgmlst --format json sample.fasta -o tgmlst.json
gmlst typing tgmlst --stats sample.fasta
gmlst typing tgmlst --save-scheme discovered_scheme.json sample.fasta
```

Scheme-free mode is helpful for exploratory workflows and cases where you want to derive a typing scheme from the data itself.

## Understanding results

### TSV output format

The default output format for `typing mlst` and `typing cgmlst` is TSV:

```tsv
FILE	SCHEME	ST	arcC	aroE	glpF	gmk	pta	tpi	yqiL
sample1	saureus_1	1	1	1	1	1	1	1	1
sample2	saureus_1	-	1	1	~2	1	1	15?	-
```

Columns mean:

- `FILE`: sample identifier
- `SCHEME`: scheme name used for typing
- `ST`: sequence type, or `-` when unresolved
- remaining columns: per-locus allele calls

### Call type markers

`gmlst` uses compact markers in the allele columns:

| Marker | Meaning | ST assigned? |
|---|---|---|
| `23` | exact match to allele 23, single copy | ✅ |
| `23*` | exact match, same-allele multicopy (gene duplicated on multiple chromosomes) | ✅ (uses `23`) |
| `~19` | closest known allele, or a novel call represented against the nearest allele ID | ❌ |
| `15?` | partial call, allele 15 found with incomplete coverage | ❌ |
| `1,2` | conflicting multicopy — different alleles detected at different copies | ❌ |
| `1,1` | same-allele copy expanded (with `--count-same-copy` flag) | ✅ |
| `-` | missing locus | ❌ |

Practical interpretation:

- no prefix or suffix means an exact call
- `*` suffix means the same allele was found in multiple copies (e.g. *Vibrio* housekeeping genes on Chr1 + Chr2)
- `~` means the locus is not a clean exact match
- `?` means coverage is incomplete
- comma-separated different numbers (`1,2`) means conflicting multicopy
- `-` means the locus was not found

If any locus is non-exact or has conflicting multicopy, `ST` may be reported as `-`.

### Multicopy loci

Some organisms show multicopy housekeeping gene signals, particularly species with multiple chromosomes (e.g. *Vibrio*, *Brucella*). gmlst distinguishes two cases:

**Same-allele multicopy** (`23*`): the same allele is detected at each copy. This is biologically normal — the gene is duplicated but both copies are identical. ST is assigned normally using allele `23`.

**Conflicting multicopy** (`1,2`): different alleles are detected at different copies (possible paralogs or mixed infection). ST is reported as `-` because a confident assignment cannot be made.

### Explicit copy counting

To expand `23*` into `23,23` notation (for downstream tools that expect it):

```bash
gmlst typing mlst -s vparahaemolyticus_1 -b blastn --count-same-copy sample.fna
```

### Recommended workflow for multicopy-prone organisms

For organisms or schemes where multicopy signals are common, a two-pass workflow is safer.

**Pass 1: routine typing**

```bash
gmlst typing mlst -s vparahaemolyticus_1 -b minimap2 samples/*.fna -o pass1.tsv
```

**Pass 2: targeted review of flagged samples**

Re-run only the problematic samples (those with `1,2` conflicting multicopy or `~` novel markers) with `blastn` and explicit copy counting:

```bash
gmlst typing mlst -s vparahaemolyticus_1 -b blastn --count-same-copy flagged_sample.fna
```

## Next steps

- Read the full [Command Reference](commands.md)
- Review [Installation](installation.md) if you need backend setup help
- Explore the [repository overview](https://github.com/indexofire/gmlst#readme)
