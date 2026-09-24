# gmlst

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Bioinformatics](https://img.shields.io/badge/domain-bioinformatics-green.svg)](https://github.com/indexofire/gmlst)

`gmlst` is a fast Python 3.12 CLI for bacterial genome typing with classical MLST, large cgMLST and wgMLST schemes, and scheme-free discovery workflows. It supports assembled genomes and raw reads, several alignment backends, multiple public data providers, custom local schemes, offline cache reuse, and local MST visualization from one command-line interface.

English | [简体中文](README_ZH.md)

## Features

- 🧬 **Broad typing support**: run `gmlst typing mlst`, `gmlst typing cgmlst`, and `gmlst typing tgmlst` from the same CLI.
- ⚡ **Multiple backends**: use BLAST+, KMA, minimap2, MUMmer4, with built-in exact-hash pre-resolution for cgMLST workflows.
- 🧫 **FASTA and FASTQ input**: type assembled genomes and paired-end raw reads with backend-aware handling.
- 🗂️ **GenBank/EMBL input**: accept `.gbk`, `.gb`, `.gbff`, and `.embl` (optionally gzipped) directly — records are converted on the fly, no pre-processing.
- 🗂️ **Multiple providers**: work with PubMLST, Pasteur BIGSdb, Enterobase, cgmlst.org, and local custom schemes.
- 🧠 **Smart cgMLST modes**: choose `fast`, `ultrafast`, or `balanced` depending on speed and evidence needs.
- 🆕 **Novel allele workflow**: detect novel alleles, extract novel profiles, and build custom laboratory databases.
- 🔍 **Scheme-free typing**: run `tgmlst` for de novo allele discovery without a preselected public scheme.
- 📦 **Rich outputs**: export `tsv`, `json`, `pretty`, and GrapeTree-compatible tables.
- 📊 **Quality scoring**: every sample gets a 0-100 score and a status code (PERFECT/NOVEL/MIXED/MISSING/BAD) in JSON output, with `--minscore` filtering for batch QC.
- 🌐 **Local visualization**: launch a Flask + Vue web app with `gmlst visual web` to inspect MST results locally.
- 🐳 **Pipeline ready**: a Docker image with all backends plus Nextflow/Snakemake examples drops gmlst straight into surveillance pipelines.
- 💾 **Cache-first operation**: downloaded schemes and built indexes are reused for offline or repeated runs.
- 🧵 **Batch processing**: use sample-level workers and backend threads for high-throughput workflows.
- 🧬 **CDS-aware calling**: cgMLST workflows can use Pyrodigal for CDS prediction and chewBBACA-compatible classification paths.
- 🤖 **AI-agent friendly**: versioned JSON envelopes, data-only stdout, and stable exit codes make the CLI safe to drive from scripts and agents.

## Installation

### Quick install

A conda virtual environment is recommended for installing gmlst.

```bash
conda create -n gmlst
conda activate gmlst
conda install python=3.12
pip install gmlst
```

To make gmlst functional, you also need to install bioinformatics alignment tools. Currently, FASTA data supports the `blastn`, `minimap2`, `nucmer`, and `kma` backends. FASTQ data supports the `kma` backend. Install the ones you need based on your data types.

```bash
# Install all backend dependencies for full functionality
conda install blast minimap2 mummer4 kma
```

For other installation methods (Pixi, uv, source, Docker), see the [Installation Guide](docs/en/installation.md).

## Quick Start

### 1. Browse and download a scheme

```bash
# Zero-setup: skip scheme selection entirely — gmlst identifies the species
# from the genome, picks the matching scheme, downloads it, and types
gmlst typing mlst sample.fna

# Know the organism but not the scheme name? Resolve it with -n
# (unique match auto-selects; multiple matches print a candidate table)
gmlst typing mlst -n bordetella sample.fna

# The species fingerprint database powers auto-detection; build it on demand
gmlst scheme update-fingerprints

# List cached and available schemes (downloaded schemes shown in bold)
gmlst scheme list

# Search across scheme name, organism, description, and provider
gmlst scheme search saureus
gmlst scheme search "salmonella" -t cgmlst

# Restrict to one provider
gmlst scheme list -p pubmlst

# Download a scheme to the local cache
gmlst scheme download saureus_1

# Re-download with low concurrency (avoid 429 from rate-limited servers)
gmlst scheme download saureus_1 --force -x 2

# Refresh every cached scheme (asks for confirmation first)
gmlst scheme update -a
gmlst scheme update -a -y              # skip the Y/N prompt

# Delete a cached scheme you no longer need
gmlst scheme remove saureus_1
gmlst scheme remove saureus_1 -y        # no confirmation prompt
```

### 2. Type one sample

```bash
# MLST on an assembled genome
gmlst typing mlst -s saureus_1 sample.fasta

# MLST on paired-end reads (requires kma backend)
gmlst typing mlst -s saureus_1 sample_R1.fastq.gz sample_R2.fastq.gz
# Wildcard patterns are supported for _1/_2 and _R1/_R2 naming
gmlst typing mlst -s saureus_1 sample*.fastq.gz

# cgMLST on an assembly
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode fast sample.fna
```

### 3. Batch processing

`--max-workers N` types N samples in parallel and is the main speed lever for batch runs. It is distinct from `-t/--threads`: `-t` parallelizes a single backend invocation, while `--max-workers` fans out across samples (per-sample backend threads are forced to 1). The `kma` and `nucmer` backends cannot use `-t` effectively, so `--max-workers` is the only way to speed them up.

```bash
# Batch typing with 16 samples in parallel
gmlst typing mlst -s saureus_1 -t 1 --max-workers 16 samples/*.fasta -o results.tsv

# FASTQ batches: combine with the kma backend
gmlst typing mlst -s saureus_1 -b kma -t 1 --max-workers 16 samples/*_R1.fastq.gz -o results.tsv

# Save machine-readable JSON for downstream novel extraction
gmlst typing mlst -s saureus_1 --format json samples/*.fasta -o results.json
```

Measured on 639 *B. pertussis* assemblies (16 workers, results identical to serial runs):

| Backend | Serial (`-t 16`) | `--max-workers 16` |
| --- | --- | --- |
| minimap2 | 55 s | **9 s** |
| blastn | 97 s | **31 s** |
| nucmer | 270 s | **76 s** |
| kma | 330 s | **48 s** |

### 4. Understand the output

Default output is TSV, compatible with the familiar `tseemann/mlst` style.

```text
FILE            SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample1.fasta   saureus_1   1   1     1     1     1    1    1    1
sample2.fasta   saureus_1   -   1     ~2    3?    -    1    1    1
```

- plain allele number, exact known allele match
- `23*`, same allele detected at multiple genomic copies (e.g. gene duplicated on two chromosomes); does not affect ST assignment
- `~23`, non-exact high-coverage call, typically a closest or novel-style locus depending on identity
- `15?`, partial locus hit with insufficient coverage
- `-`, locus not found

Use `--format pretty` for human-readable terminal output and `--format json` for downstream automation.

## Alignment Backends

| Backend | CLI selectable | FASTA | FASTQ | Best fit | Notes |
| --- | --- | --- | --- | --- | --- |
| `blastn` | Yes | Yes | No | Classical MLST on assemblies | Strong baseline for exact allele calls and targeted review |
| `kma` | Yes | Yes | Yes | **FASTQ typing (all modes)** | Consensus-based allele calling from raw reads |
| `minimap2` | Yes | Yes | No | Fast assembly typing | FASTA assemblies only; use kma for FASTQ |
| `nucmer` | Yes | Yes | No | Sensitive assembly comparison | Useful for distant matches and alternate evidence |

### Backend notes

- `typing mlst` and `typing cgmlst` auto-detect common paired FASTQ naming patterns such as `_R1/_R2`, `_1/_2`, and `.1/.2`.
- `typing cgmlst` uses `minimap2` by default for FASTA assemblies.
- For FASTQ cgMLST, the CLI follows a KMA-first policy. Use `gmlst typing cgmlst` with KMA for raw reads.
- FASTQ input auto-switches to KMA for both `mlst` and `cgmlst` modes.
- `--max-depth` — Subsample FASTQ to a maximum read depth (default 100x, FASTQ only)

## Data Providers

| Provider | Source | Typical use |
| --- | --- | --- |
| `pubmlst` | PubMLST REST catalogs | Common public MLST schemes |
| `pasteur` | Pasteur BIGSdb API | BIGSdb-hosted species collections |
| `enterobase` | Enterobase scheme downloads | Large curated scheme sets |
| `cgmlst` | cgmlst.org | cgMLST-focused public schemes |
| `local` | Local cache and custom schemes | Private laboratory databases and exported custom schemes |

Examples:

```bash
gmlst scheme list -p pubmlst
gmlst scheme list -p enterobase -t cgmlst
gmlst scheme list -p local
gmlst scheme search saureus
gmlst scheme show saureus_1
```

## Novel Data Workflow

Build a local custom scheme from novel calls collected during routine typing.

```bash
# 1. Type samples and save JSON
gmlst typing mlst -s saureus_1 --format json *.fasta -o typing_results.json

# 2. Extract novel alleles and novel profiles
gmlst utils extract -i typing_results.json --novel-allele --novel-profile --data-dir novel_data

# 3. Create a local custom scheme
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data --desc "Lab collection 2024"

# 4. Add more novel data later
gmlst scheme update-custom custom_1 --data-dir more_novel_data

# 5. Export for downstream MST work
gmlst scheme export custom_1 --format grapetree -o custom_1_grapetree.tsv
```

TSV fallback is also supported when you only have tabular typing output and the original sample files are available:

```bash
gmlst utils extract -i typing_results.tsv -s saureus_1 --novel-allele --novel-profile \
  --samples-dir ./samples --data-dir novel_data
```

## cgMLST Modes

`gmlst typing cgmlst` supports several calling modes for different speed and evidence trade-offs.

| Mode | What it does | Good default |
| --- | --- | --- |
| `fast` | Exact-hash plus minimap2 prefilter with targeted rescue | Fast everyday assembly typing |
| `ultrafast` | More aggressive speed profile with bounded second-pass rescue | Large batches where turnaround matters most |
| `balanced` | Hash-first path with targeted `blastn` fallback | Balance speed with stronger low-confidence review |

Examples:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode ultrafast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode balanced sample.fna
```

## Scheme-free Typing (`tgmlst`)

Use `tgmlst` when you want scheme-free allele discovery and optional scheme reuse.

```bash
# Run scheme-free typing
gmlst typing tgmlst sample.fna --stats

# Save a discovered scheme for reuse
gmlst typing tgmlst sample.fna --save-scheme tgmlst_scheme.json

# Reuse a previously saved scheme
gmlst typing tgmlst another_sample.fna --load-scheme tgmlst_scheme.json --format json
```

Useful options include `--hash-strategy`, `--summary-report`, `--error-report`, and `--fail-on-error`. With `--stats`, the run statistics JSON is printed to stderr so stdout stays data-only.

## Visualization

Launch the local web application to build an MST from cgMLST or exported GrapeTree-style profiles.

```bash
gmlst visual web --open-browser
```

Or bind to a custom address:

```bash
gmlst visual web --host 0.0.0.0 --port 8787
```

The web UI accepts TSV data, builds a minimum spanning tree, and serves a local Flask API with a Vue frontend.

The `visual` subcommands also read profiles from stdin, so you can pipe typing results straight into an MST summary:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 *.fna --format tsv | gmlst visual mst --input - --format summary
```

See the [Visualization Guide](docs/en/visual_guide.md) for the full set of `visual` commands (`mst`, `matrix`, `heatmap`, `compare`, `locus-diff`).

## Configuration

Key environment variables:

| Variable | Purpose |
| --- | --- |
| `GMLST_CACHE_DIR` | Override the cache root (auto-detected: `$CONDA_PREFIX/share/gmlst` in conda, `$VIRTUAL_ENV/.cache/gmlst` in venv, or `~/.cache/gmlst` by default) |
| `GMLST_TMPDIR` | Override temporary working directory used during typing and refinement |
| `GMLST_MINIMAP2_FASTA_EMIT_CIGAR` | Emit CIGAR in minimap2 FASTA alignments (1/0) |
| `GMLST_PUBMLST_BASE_URL` | Override PubMLST API base URL |
| `GMLST_PASTEUR_BASE_URL` | Override Pasteur BIGSdb API base URL |
| `GMLST_PRIVATE_BIGSDB_URL` | Register a private BIGSdb instance as an extra provider |
| `GMLST_PRIVATE_BIGSDB_NAME` | Name shown for the private BIGSdb provider |
| `GMLST_PRIVATE_BIGSDB_LABEL` | Human-readable label for the private BIGSdb provider |
| `GMLST_PUBMLST_API_KEY` | PubMLST API key for post-2024 data access (Bearer auth) |
| `GMLST_PASTEUR_API_KEY` | Pasteur BIGSdb API key for post-2024 data access (Bearer auth) |

Since January 2025, PubMLST and Pasteur require authentication for data added
after 31 December 2024. Obtain an API key and configure it:

```bash
# PubMLST: register at pubmlst.org → Preferences → API keys → create key
gmlst config set GMLST_PUBMLST_API_KEY your-key-here
gmlst config init     # auto-load in every new shell (run once)
source ~/.config/gmlst/env.sh   # apply now in current shell
```

Use `gmlst config show` to view all 29 configuration variables with current values and defaults. Secret values such as API keys are masked in this view (`first4****last4`) so they stay out of terminal logs:

```bash
gmlst config show                          # grouped table view (secrets masked)
gmlst config env                           # shell-exportable format
gmlst config get GMLST_CACHE_DIR           # get a single variable
gmlst config get GMLST_CACHE_DIR --format json  # {name, value, source, is_default}
gmlst config set GMLST_CACHE_DIR /data     # write to ~/.config/gmlst/env.sh
gmlst config init                          # add source line to shell rc (run once)
```

In `config get --format json` output, `source` tells you where the value comes from: `file` (the `env.sh` config file), `env` (set in the environment any other way), or `default` (unset, built-in default, `is_default` true).

Example:

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
export GMLST_PUBMLST_BASE_URL="https://rest.pubmlst.org/db"
export GMLST_PASTEUR_BASE_URL="https://bigsdb.pasteur.fr/api/db"
```

Private BIGSdb example:

```bash
export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
export GMLST_PRIVATE_BIGSDB_LABEL="Lab BIGSdb"
gmlst scheme list -p labdb
```

## Output Format Details

The default TSV format uses compact markers per locus.

| Marker | Meaning | ST assigned? |
| --- | --- | --- |
| `23` | Exact allele call, single copy | ✅ Yes |
| `23*` | Exact allele call, **same-allele multicopy** (e.g. gene duplicated on two chromosomes) | ✅ Yes (uses `23`) |
| `~23` | Non-exact but high-coverage call, closest match or novel allele | ❌ Novel |
| `15?` | Partial call, coverage below the confident threshold | ❌ Incomplete |
| `1,2` | **Conflicting** multicopy — different alleles detected at different loci copies | ❌ Ambiguous |
| `1,1` | Same-allele copy expanded (with `--count-same-copy` flag) | ✅ Yes |
| `-` | Missing locus | ❌ Incomplete |

### Genes split across contigs

Fragmented assemblies often break a housekeeping gene across two contigs. For the `blastn` and `minimap2` backends, gmlst joins the per-contig fragment alignments of such a locus:

- **Overlapping fragments** (the contigs overlap inside the gene and the overlap sequence agrees) are tiled into one reconstructed alignment, which can yield a normal exact call.
- **Disjoint fragments** never produce an exact call — an indel at the unsampled junction is invisible — but the partial `?` call reports the combined coverage of all fragments, and JSON output lists each fragment (`contig`, `allele_start`, `allele_end`).

The minimum allele-coordinate overlap required to join fragments defaults to 10 bp and is tunable with `--min-join-overlap` (`0` = most permissive; overlap sequence must still agree exactly).

JSON output is the best choice when you want structured fields such as per-locus call metadata and `novel_sequence` extraction data. Every JSON document the CLI writes is wrapped in a versioned envelope, `{"schema_version": "<constant>", "data": <payload>}`, so scripts can version-check before parsing:

Each sample in the typing payload also carries a `score` (0-100, the mean of per-locus scores where exact calls are 100, novel/partial calls scale with the caller's confidence, and missing or conflicting loci are 0) and a `status` code — `PERFECT`, `NOVEL`, `MIXED`, `MISSING`, `BAD`, or `NONE`. Use `--minscore <float>` to drop samples below a quality threshold from TSV and JSON output alike (batch QC):

```bash
# Only report samples scoring at least 50
gmlst typing mlst -s saureus_1 --minscore 50 --format json *.fasta -o qc_passed.json
```

```json
{"schema_version": "gmlst-typing-v1", "data": [{"file": "sample.fasta", "scheme": "saureus_1", "...": "..."}]}
```

The full constant table lives in the [Command Reference](docs/en/commands.md#json-output-envelope).

## Exit Codes

| Code | Meaning |
| --- | --- |
| 0 | Success (including partial `tgmlst` failures without `--fail-on-error`) |
| 1 | Runtime failure (also `scheme update` when any provider or scheme update fails) |
| 2 | Usage error, such as bad flags or an invalid regex in `scheme list --name` |
| 3 | `tgmlst` input stage failure |
| 4 | `tgmlst` assembly stage failure |
| 5 | `tgmlst` prediction stage failure |
| 6 | `tgmlst` unknown stage failure |

Warnings, progress bars, and "Results written to" notices go to stderr; stdout carries data only.

## Multicopy Loci Notes

- **Same-allele multicopy** (`23*`): the same allele is detected at multiple genomic copies (e.g. housekeeping genes duplicated across two chromosomes in *Vibrio*). This is biologically normal and does **not** prevent ST assignment. The `*` suffix marks it for transparency; ST lookup uses the allele number without the `*`.
- **Conflicting multicopy** (`1,2`): different alleles are detected at different copies of the same locus (possible paralogs or mixed infection). ST is reported as `-` because a confident profile cannot be assigned.
- **Explicit copy counting** (`1,1`): use `--count-same-copy` to expand same-allele multicopy into comma notation for downstream tools that expect it.

Recommended review pattern:

```bash
# Fast first pass
gmlst typing mlst -s vparahaemolyticus_1 *.fna -o pass1.tsv

# Targeted second pass on flagged samples (those with conflicting multicopy or ~ markers)
gmlst typing mlst -s vparahaemolyticus_1 -b blastn --count-same-copy flagged_sample.fna
```

## Development

Set up the development environment:

```bash
pixi install
pixi run install-dev
```

Common tasks:

```bash
pixi run lint
pixi run format-check
pixi run test
pixi run check
```

Direct Ruff commands also work:

```bash
pixi run ruff check .
pixi run ruff format .
```

See [docs/en/contributing.md](docs/en/contributing.md) for contributor workflow and [docs/en/architecture.md](docs/en/architecture.md) for module boundaries and typing-path contracts.

## Documentation Index

- [docs/README.md](docs/README.md) for the full documentation map
- [docs/en/installation.md](docs/en/installation.md) for installation details
- [docs/en/quickstart.md](docs/en/quickstart.md) for a guided first run
- [docs/en/commands.md](docs/en/commands.md) for the CLI reference
- [docs/en/configuration.md](docs/en/configuration.md) for configuration reference
- [docs/en/pipelines.md](docs/en/pipelines.md) for Docker, Nextflow, and Snakemake integration
- [README_ZH.md](README_ZH.md) for the Chinese root guide

## License

Released under the [MIT License](LICENSE).

## Acknowledgments

- Inspired by [tseemann/mlst](https://github.com/tseemann/mlst)
- Uses public scheme data from [PubMLST](https://pubmlst.org/)
