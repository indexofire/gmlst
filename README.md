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
- 🗂️ **Multiple providers**: work with PubMLST, Pasteur BIGSdb, Enterobase, cgmlst.org, and local custom schemes.
- 🧠 **Smart cgMLST modes**: choose `standard`, `chew-fast`, `chew-ultrafast`, `chew-bsr`, or `chew-balanced` depending on speed and evidence needs.
- 🆕 **Novel allele workflow**: detect novel alleles, extract novel profiles, and build custom laboratory databases.
- 🔍 **Scheme-free typing**: run `tgmlst` for de novo allele discovery without a preselected public scheme.
- 📦 **Rich outputs**: export `tsv`, `json`, `pretty`, and GrapeTree-compatible tables.
- 🌐 **Local visualization**: launch a Flask + Vue web app with `gmlst visual web` to inspect MST results locally.
- 💾 **Cache-first operation**: downloaded schemes and built indexes are reused for offline or repeated runs.
- 🧵 **Batch processing**: use sample-level workers and backend threads for high-throughput workflows.
- 🧬 **CDS-aware calling**: cgMLST workflows can use Pyrodigal for CDS prediction and chewBBACA-compatible classification paths.

## Installation

### Option 1, pixi, recommended

Pixi installs Python, external bioinformatics tools, and the editable package in one environment.

```bash
curl -fsSL https://pixi.sh/install.sh | bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
pixi install
pixi run gmlst --version
```

### Option 2, pip

Use this if you already manage your own Python and system tools.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install gmlst

# Install external tools separately, for example with conda or mamba
conda install -c bioconda blast minimap2 mummer4 mmseqs2 prodigal kma kmc samtools
```

### Option 3, from source

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
gmlst --help
```

### Option 4, Docker

All tools pre-installed, no Python or conda setup needed.

```bash
docker pull indexofire/gmlst:latest

# Type a sample
docker run --rm -v $(pwd):/data indexofire/gmlst:latest \
  typing mlst -s saureus_1 /data/sample.fasta

# Web visualization
docker run --rm -p 8787:8787 -v $(pwd):/data indexofire/gmlst:latest \
  visual web --host 0.0.0.0 --port 8787
```

### External tools managed by pixi

- `blast >=2.14`
- `minimap2 >=2.26`
- `mummer4 >=4.0`
- `mmseqs2 >=15`
- `prodigal >=2.6`
- `kma >=1.6.8`
- `kmc >=3.2.4`
- `samtools >=1.23.1`

### Python package requirements

- `click`
- `flask`
- `requests`
- `rich`
- `xxhash`
- `pyyaml`
- `pyrodigal`

## Quick Start

### 1. Browse and download a scheme

```bash
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
```

### 2. Type one sample

```bash
# MLST on an assembled genome
gmlst typing mlst -s saureus_1 sample.fasta

# MLST on paired-end reads
gmlst typing mlst -s saureus_1 -b minimap2 sample_R1.fastq.gz sample_R2.fastq.gz

# cgMLST on an assembly
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-fast sample.fna
```

### 3. Batch processing

```bash
# Write TSV output for many assemblies
gmlst typing mlst -s saureus_1 --max-workers 8 samples/*.fasta -o results.tsv

# Save machine-readable JSON for downstream novel extraction
gmlst typing mlst -s saureus_1 --format json samples/*.fasta -o results.json
```

### 4. Understand the output

Default output is TSV, compatible with the familiar `tseemann/mlst` style.

```text
FILE            SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample1.fasta   saureus_1   1   1     1     1     1    1    1    1
sample2.fasta   saureus_1   -   1     ~2    3?    -    1    1    1
```

- plain allele number, exact known allele match
- `~23`, non-exact high-coverage call, typically a closest or novel-style locus depending on identity
- `15?`, partial locus hit with insufficient coverage
- `-`, locus not found

Use `--format pretty` for human-readable terminal output and `--format json` for downstream automation.

## Alignment Backends

| Backend | CLI selectable | FASTA | FASTQ | Best fit | Notes |
| --- | --- | --- | --- | --- | --- |
| `blastn` | Yes | Yes | No | Classical MLST on assemblies | Strong baseline for exact allele calls and targeted review |
| `kma` | Yes | Yes | Yes | FASTQ typing and cgMLST FASTQ routes | Good fit for mapping-based allele calling on reads |
| `minimap2` | Yes | Yes | Yes | Fast assembly typing and flexible read workflows | Used heavily in cgMLST optimization paths |
| `nucmer` | Yes | Yes | No | Sensitive assembly comparison | Useful for distant matches and alternate evidence |

### Backend notes

- `typing mlst` and `typing cgmlst` auto-detect common paired FASTQ naming patterns such as `_R1/_R2`, `_1/_2`, and `.1/.2`.
- `typing cgmlst` uses `minimap2` by default for FASTA assemblies.
- For FASTQ cgMLST, the CLI follows a KMA-first policy and treats chew-style cgMLST modes as FASTA-oriented compatibility options.
- `GMLST_MINIMAP2_KMER_ENGINE=python|kmc|auto` controls the minimap2 k-mer support scorer.

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
| `standard` | Conservative baseline behavior | Start here if you want predictable generic settings |
| `chew-fast` | Exact-hash plus minimap2 prefilter with targeted rescue | Fast everyday assembly typing |
| `chew-ultrafast` | More aggressive speed profile with bounded second-pass rescue | Large batches where turnaround matters most |
| `chew-bsr` | Adds protein-level exact-hash style resolution on top of `chew-fast` | Cases where protein evidence is useful |
| `chew-balanced` | Hash-first path with targeted `blastn` fallback | Balance speed with stronger low-confidence review |

Examples:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode standard sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-ultrafast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-bsr sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-balanced sample.fna
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

Useful options include `--hash-strategy`, `--summary-report`, `--error-report`, and `--fail-on-error`.

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

## Configuration

Key environment variables:

| Variable | Purpose |
| --- | --- |
| `GMLST_CACHE_DIR` | Override the cache root (auto-detected: `$CONDA_PREFIX/share/gmlst` in conda, `$VIRTUAL_ENV/.cache/gmlst` in venv, or `~/.cache/gmlst` by default) |
| `GMLST_TMPDIR` | Override temporary working directory used during typing and refinement |
| `GMLST_MINIMAP2_KMER_ENGINE` | Choose minimap2 k-mer support engine: `python`, `kmc`, or `auto` |
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
source ~/.config/gmlst/env.sh
```

Use `gmlst config show` to view all 29 configuration variables with current values and defaults:

```bash
gmlst config show                          # grouped table view
gmlst config env                           # shell-exportable format
gmlst config get GMLST_CACHE_DIR           # get a single variable
gmlst config set GMLST_CACHE_DIR /data     # write to ~/.config/gmlst/env.sh
source ~/.config/gmlst/env.sh              # apply changes
```

Example:

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
export GMLST_MINIMAP2_KMER_ENGINE=auto
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

| Marker | Meaning |
| --- | --- |
| `23` | Exact allele call |
| `~23` | Non-exact but high-coverage call, used for closest hits and novel-like loci |
| `15?` | Partial call, coverage below the confident threshold |
| `-` | Missing locus |

JSON output is the best choice when you want structured fields such as per-locus call metadata and `novel_sequence` extraction data.

## Multicopy Loci Notes

- Conflicting multicopy calls are reported with comma notation such as `1,2`.
- When conflicting multicopy loci are present, ST is reported as `-` to avoid overconfident profile assignment.
- Same-allele copy counting such as `1,1` is optional and currently exposed through `--count-same-copy` for `blastn` workflows.

Recommended review pattern:

```bash
# Fast first pass
gmlst typing mlst -s vparahaemolyticus_1 *.fna -o pass1.tsv

# Targeted second pass on flagged samples
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

See [docs/contributing.md](docs/contributing.md) for contributor workflow and [docs/architecture.md](docs/architecture.md) for module boundaries and typing-path contracts.

## Documentation Index

- [docs/README.md](docs/README.md) for the full documentation map
- [docs/installation.md](docs/installation.md) for installation details
- [docs/quickstart.md](docs/quickstart.md) for a guided first run
- [docs/commands.md](docs/commands.md) for the CLI reference
- [README_ZH.md](README_ZH.md) for the Chinese root guide

## License

Released under the [MIT License](LICENSE).

## Acknowledgments

- Inspired by [tseemann/mlst](https://github.com/tseemann/mlst)
- Uses public scheme data from [PubMLST](https://pubmlst.org/)
