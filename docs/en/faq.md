# FAQ and Troubleshooting

This page collects common questions and practical fixes for `gmlst`. For installation and first-run instructions, see [installation.md](installation.md) and [quickstart.md](quickstart.md). For command syntax, see [commands.md](commands.md).

## General Questions

### What is gmlst?

`gmlst` is a Python CLI for bacterial genome typing. It supports classical MLST, larger cgMLST and wgMLST schemes, and scheme-free typing with `gmlst typing tgmlst`.

### What is the difference between MLST and cgMLST?

- MLST usually uses a small number of housekeeping loci, often 7
- cgMLST uses a much larger set of core-genome loci
- wgMLST goes broader still, often including accessory loci

In practice, MLST is lighter and easier to compare quickly. cgMLST gives finer resolution, but needs more compute and more complete locus recovery.

### Why does gmlst support multiple alignment backends?

Different inputs and workloads need different tools.

- `blastn` is a good baseline for assembly-based MLST
- `kma` is well suited to read-based workflows and cgMLST FASTQ paths
- `minimap2` is fast and flexible for assemblies and some read workflows
- `nucmer` can be useful for assembly comparison and alternate evidence

The project keeps the output model normalized so downstream calling logic can stay consistent across backends.

## Installation Issues

### `pixi: command not found`

Pixi is not installed, or your shell has not picked up the new PATH yet.

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

Then open a new terminal and verify:

```bash
pixi --version
```

### `Python 3.12 is required`

Your Python is too old for the package.

Check:

```bash
python --version
python3 --version
```

If you want the easiest path, use pixi instead of a system Python install:

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
pixi install
pixi run gmlst --version
```

### `pip install gmlst` fails

Common reasons:

- Python is not 3.12
- build tools or environment are inconsistent
- external tools are missing and later commands fail

Try a clean virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install gmlst
```

If you still hit environment problems, use pixi.

### `blastn` not found

`blastn` is part of BLAST+. If you installed with pixi, run inside the pixi environment. If you used pip, install BLAST+ separately.

Check:

```bash
gmlst utils check -b blastn
```

Or:

```bash
pixi run gmlst utils check -b blastn
```

### I get permission errors during install

Do not use `sudo pip` or `sudo pixi` for normal local installs. Use a user-local environment.

Good options:

- pixi environment
- Python virtual environment
- conda or mamba environment

## Scheme Management Issues

### `Scheme 'X' not found in catalog`

The name must match the canonical `scheme_name`, not just the organism name.

Check available schemes:

```bash
gmlst scheme list
gmlst scheme list -p pubmlst
gmlst scheme list -p enterobase -t cgmlst
```

Then use the exact scheme name, for example:

```bash
gmlst scheme download -s saureus_1
```

### Scheme download fails

Typical causes:

- temporary network failure
- provider-side outage or rate limit
- a download tool that does not work well in your environment

Try a different download tool:

```bash
gmlst scheme download -s saureus_1 --download-tool curl
gmlst scheme download -s saureus_1 --download-tool requests
gmlst scheme download -s saureus_1 --download-tool wget
```

If you are behind a proxy or firewall, test provider access separately.

### Where is the cache stored?

The cache root is auto-detected: `$CONDA_PREFIX/share/gmlst` in conda environments, `$VIRTUAL_ENV/.cache/gmlst` in virtualenvs, or `~/.cache/gmlst` by default. Each environment gets its own isolated cache.

You can override it:

```bash
export GMLST_CACHE_DIR="$HOME/work/gmlst-cache"
gmlst scheme list
```

To share a cache across conda environments:

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
```

### I want to use a different cache directory for one command

Some commands also support `--cache-dir`.

```bash
gmlst scheme list --cache-dir /tmp/gmlst-cache
gmlst scheme download -s saureus_1 --cache-dir /tmp/gmlst-cache
```

### A scheme is missing from `scheme list`

It may be blocked by `gmlst/data/blocked_schemes.json`.

That file is used to hide or reject selected schemes in list, show, download, and update flows. If you are maintaining the project and need to change block policy, edit that JSON file carefully.

### Provider URL overrides for self-hosted BIGSdb

You can point `gmlst` at a custom BIGSdb host with environment variables.

```bash
export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
export GMLST_PRIVATE_BIGSDB_LABEL="Lab BIGSdb"
gmlst scheme list -p labdb
```

For built-in hosts you can also override base URLs:

```bash
export GMLST_PUBMLST_BASE_URL="https://rest.pubmlst.org/db"
export GMLST_PASTEUR_BASE_URL="https://bigsdb.pasteur.fr/api/db"
```

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

More tips are in the [Performance Tips](#performance-tips) section below.

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

This is expected. For FASTQ input, the CLI enforces a KMA-first policy. If you request `-b minimap2` for cgMLST FASTQ, `gmlst` switches to `kma` and treats `--cgmlst-mode` as compatibility-only, effectively `standard`.

This behavior is documented in [architecture.md](architecture.md) and [commands.md](commands.md).

### Which cgMLST mode should I use?

Start with:

- `standard` if you want the most conservative default behavior
- `chew-fast` for common FASTA cgMLST work
- `chew-ultrafast` for larger FASTA batches where speed matters more
- `chew-balanced` if you want more fallback review

Examples:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode standard sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-ultrafast sample.fna
```

### Large cgMLST schemes run very slowly

For large schemes, increase threads for backends that benefit from them, especially KMA.

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 8 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 16 sample.fna
```

## Output Questions

### What do TSV markers mean?

- `23`, exact allele call
- `~23`, closest or non-exact high-coverage call
- `15?`, partial call
- `-`, missing locus

### Should I use JSON or TSV?

Use TSV when you want compact, table-friendly output. Use JSON when you need full structured details such as per-locus metadata and `novel_sequence` fields.

Example:

```bash
gmlst typing mlst -s saureus_1 --format tsv sample.fasta -o result.tsv
gmlst typing mlst -s saureus_1 --format json sample.fasta -o result.json
```

### GrapeTree export does not work for my scheme

GrapeTree export is intended for public or custom schemes that have the expected profile structure. If export fails, confirm the scheme is a downloaded public scheme or a custom scheme built through `gmlst scheme create`.

Example workflow:

```bash
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data --desc "Lab collection"
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

## Configuration Questions

### Which environment variables matter most?

Common ones are:

- `GMLST_CACHE_DIR`, override cache root (auto-detected from conda/venv by default)
- `GMLST_TMPDIR`, override temporary working directory
- provider URL overrides, such as `GMLST_PUBMLST_BASE_URL`

Example:

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
```

### Where are temporary files written?

By default they go to the system temporary area. Override with:

```bash
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
```

## Performance Tips

### Which backend is usually fastest?

There is no single answer, but these are good starting points:

- assembly MLST: start with `blastn` or `minimap2`
- FASTQ typing: start with `kma`
- FASTA cgMLST: start with `minimap2` and a chew-style mode if appropriate
- large FASTQ cgMLST: expect KMA-first behavior

### How should I tune threads?

Use sample-level parallelism for many independent samples and backend threads for expensive per-sample work.

Examples:

```bash
gmlst typing mlst -s saureus_1 --max-workers 8 samples/*.fasta -o results.tsv
gmlst typing cgmlst -s vparahaemolyticus_3 -t 8 sample.fna
```

### Should I process samples in batches?

Yes, especially for large cohorts. Reusing the cache and indexes is one of the easiest ways to save time.

## Error Messages

### `Unknown backend 'X'`

You requested a backend that is not registered in `gmlst/aligners/__init__.py`. Check supported backend names:

```bash
gmlst typing mlst --help
gmlst utils check -b blastn
```

### `Unknown provider 'X'`

The provider is not registered in `gmlst/database/providers/__init__.py`.

Check available providers with:

```bash
gmlst scheme list
```

### `No typing result produced for input sample`

This usually means the run failed before a valid typing result was assembled. Check input format, backend compatibility, scheme availability, and command output just before the failure.

### `Failed to download` errors

These usually point to network or provider-side issues. Retry with a different `--download-tool`, then verify the remote host is reachable.

### `--verbose and --quiet cannot be used together`

These flags are mutually exclusive. Pick one:

```bash
gmlst --verbose scheme list
gmlst --quiet scheme list
```

## Still Stuck?

When reporting a bug or opening an issue, include:

- the exact command you ran
- your install method, pixi or pip
- input type, FASTA or FASTQ
- backend name
- scheme name
- relevant stderr output
- whether the problem happens again with `--format json`

That makes it much easier to reproduce and fix the issue.
