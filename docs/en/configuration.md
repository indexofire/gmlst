# Configuration Reference

`gmlst` is configured in three main ways: CLI flags, environment variables, and the local cache. In practice, use CLI flags for run-specific choices such as backend, scheme, threads, and output path. Use environment variables for backend tuning, provider endpoint overrides, and temporary-file behavior. Use the cache to keep downloaded schemes and built indexes available for repeat runs.

This reference only documents settings that are implemented in the current codebase. The cache root can be set via the `GMLST_CACHE_DIR` environment variable, detected automatically from conda or virtualenv environments, or overridden per-command with `--cache-dir`.

## General configuration model

### CLI flags

Common examples:

```bash
# Pick scheme, backend, and threads for one run
gmlst typing mlst -s saureus_1 -b blastn -t 8 sample.fasta

# Override cache root for one command
gmlst scheme list --cache-dir /data/gmlst-cache

# Increase sample-level parallelism
gmlst typing cgmlst -s vparahaemolyticus_3 --max-workers 4 samples/*.fasta
```

### Environment variables

Environment variables are best for defaults you want to reuse across many runs.

```bash
export GMLST_MINIMAP2_FASTA_SPEED_PROFILE=ultrafast
export GMLST_TMPDIR=/scratch/gmlst-tmp
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fasta
```

Use `gmlst config` to inspect and manage variables:

```bash
gmlst config show                    # view all variables with current values
gmlst config env                     # shell-exportable format
gmlst config set GMLST_TMPDIR /scratch/gmlst-tmp  # write to ~/.config/gmlst/env.sh
gmlst config init                    # add source line to shell rc (run once)
source ~/.config/gmlst/env.sh        # apply now in current shell
```

### Cache

The cache stores downloaded schemes, catalogs, and backend-specific indexes. Once schemes are downloaded and indexed, routine typing can run without network access. Commands that refresh catalogs or download new scheme data still need network access.

## Environment Variables

### General

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_TMPDIR` | system temp directory | Overrides the root directory used for temporary files. The directory is created if needed. Useful for large FASTQ validation temp files or scratch disks. | General runtime, minimap2 targeted FASTQ validation, output-scoped temp handling |

### Cache

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_CACHE_DIR` | auto-detected | Override the cache root directory. When unset, the cache root is resolved automatically: `$CONDA_PREFIX/share/gmlst` in conda environments, `$VIRTUAL_ENV/.cache/gmlst` in virtualenvs, or `~/.cache/gmlst` as final fallback. | All scheme, typing, and utils commands |

### BLASTN

No BLASTN-specific environment variables are currently implemented. Control BLASTN with CLI flags such as `-b blastn` and `-t/--threads`.

### KMA

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS` | `8` | For FASTQ cgMLST, auto-raises per-sample KMA threads above `1`, capped by CPU count. Set to `1` to disable auto-raise. | `typing cgmlst` runtime normalization |
| `GMLST_CGMLST_KMA_FASTQ_MEM_MODE` | `1` | Enables KMA `-mem_mode` for FASTQ cgMLST. Faster, less strict first pass. | FASTQ cgMLST with KMA |
| `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI` | `64` | After a `-mem_mode` pass, re-check up to this many `closest` loci with strict KMA to recover exact calls. Set `0` to disable. | FASTQ cgMLST with KMA |

### minimap2

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_MINIMAP2_FASTA_SPEED_PROFILE` | `default` | FASTA speed tuning for minimap2. Valid values: `default`, `fast`, `ultrafast`. | minimap2 FASTA, cgMLST FASTA workflows |
| `GMLST_MINIMAP2_FASTA_EMIT_CIGAR` | `1` | Emits FASTA CIGAR output during minimap2 assembly alignment. Set `0` to reduce work in speed-oriented paths. | minimap2 FASTA |
| `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER` | `0` | Enables hash-first candidate reduction before minimap2 main alignment. | cgMLST FASTA, minimap2 prefilter path |
| `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI` | `0` | Max missing loci sent to a minimap2 refinement pass when not overridden by a workflow mode. `0` disables this pass. | cgMLST FASTA, minimap2 refinement |
| `GMLST_CGMLST_MINIMAP2_HASH_LOCI_TOP_N` | `0` | Limits how many loci survive the hash stage before main alignment. `0` keeps default behavior. | cgMLST FASTA, minimap2 prefilter path |
| `GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI` | `adaptive` | Budget for the ultrafast second pass. Use `adaptive`, `auto`, empty value, or a non-negative integer. | cgMLST FASTA, minimap2 ultrafast path |
| `GMLST_CGMLST_MINIMAP2_REPRESENTATIVE_MAIN_ALIGNMENT` | `0` | Restricts main alignment to representative targets in speed-focused workflows. | cgMLST FASTA, minimap2 representative alignment path |

### nucmer

No nucmer-specific environment variables are currently implemented. Choose the backend with `-b nucmer`.

### cgMLST workflow

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_CGMLST_PREFILTER_MAX_LOCI` | `3000` | Auto-skip threshold for cgMLST prefiltering. If the scheme exceeds this locus count, prefilter can be skipped automatically. `0` disables the auto-skip threshold. | cgMLST prefilter control |
| `GMLST_CGMLST_EXACT_HASH_PREFILTER` | `0` | Enables chew-style DNA exact-match pre-resolution before alignment. | cgMLST FASTA exact-hash path |
| `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND` | `none` | Targeted fallback backend for low-confidence loci. Valid values: `none`, `blastn`, `kma`, `nucmer`. | cgMLST evidence fallback |
| `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI` | `300` | Limits how many loci can be sent to evidence fallback. `0` means no explicit limit. | cgMLST evidence fallback |

### CDS prediction

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_CGMLST_CDS_PREDICTION_MODE` | `single` | Pyrodigal CDS mode. Valid values: `single`, `meta`. | cgMLST exact-hash and chew-style CDS-aware workflows |
| `GMLST_CGMLST_CDS_TRAINING_FILE` | unset | Path to a fixed Pyrodigal training file. If unset and mode is `single`, gmlst can create and reuse a training file during exact-hash workflows. | cgMLST CDS prediction |
| `GMLST_CGMLST_CDS_CLOSED_ENDS` | `0` | Enables Pyrodigal closed-end prediction behavior when set to a truthy value such as `1`, `true`, `yes`, or `on`. | cgMLST CDS prediction |
| `GMLST_CGMLST_CDS_COORDINATES_OUT` | unset | Writes predicted CDS coordinates to a TSV file. Similar to `--cds-coordinates-out`, but set globally through the environment. | cgMLST CDS coordinate export |

### Providers

| Name | Default | Description | Used By |
| --- | --- | --- | --- |
| `GMLST_PUBMLST_BASE_URL` | `https://rest.pubmlst.org/db` | Overrides the PubMLST BIGSdb API root. Useful for mirrors or test instances. | `scheme list`, `scheme show`, `scheme download`, `scheme update` |
| `GMLST_PASTEUR_BASE_URL` | `https://bigsdb.pasteur.fr/api/db` | Overrides the Pasteur BIGSdb API root. | `scheme list`, `scheme show`, `scheme download`, `scheme update` |
| `GMLST_PRIVATE_BIGSDB_URL` | unset | Registers an extra private BIGSdb provider at startup. | Provider registry, scheme commands |
| `GMLST_PRIVATE_BIGSDB_NAME` | `private` | Provider key for the private BIGSdb instance. Reserved names like `all` and `local` are normalized away. | Provider registry |
| `GMLST_PRIVATE_BIGSDB_LABEL` | `Private BIGSdb` | Human-readable label for the private BIGSdb provider. | Provider registry |

## Cache Configuration

### Default cache layout

The cache root is resolved in the following order (first match wins):

1. `--cache-dir` CLI flag on the current command
2. `GMLST_CACHE_DIR` environment variable
3. `$CONDA_PREFIX/share/gmlst` when inside a conda environment
4. `$VIRTUAL_ENV/.cache/gmlst` when inside a Python virtualenv
5. `~/.cache/gmlst` (default)

This means each conda or virtualenv environment gets its own isolated database cache by default. To share a cache across environments, set `GMLST_CACHE_DIR` explicitly.

```text
~/.cache/gmlst/
```

Typical structure:

```text
~/.cache/gmlst/
├── pubmlst/
│   └── saureus_1/
│       ├── *.tfa
│       ├── saureus_1.txt
│       └── .meta.json
├── pasteur/
├── enterobase/
├── cgmlst/
├── local/
│   └── custom_1/
│       ├── *.tfa
│       ├── custom_1.txt
│       └── .meta.json
├── _catalog/
│   ├── pubmlst.json
│   └── pasteur.json
└── _indexes/
    └── pubmlst/
        └── blastn/
            └── saureus_1/
```

### Overriding cache location

Use `--cache-dir` for a single command, or `GMLST_CACHE_DIR` for a session-wide override.

```bash
# Per-command override
gmlst scheme list --cache-dir /data/gmlst-cache
gmlst scheme download -s saureus_1 --cache-dir /data/gmlst-cache
gmlst typing mlst -s saureus_1 --cache-dir /data/gmlst-cache sample.fasta

# Session-wide override
export GMLST_CACHE_DIR=/data/gmlst-cache
gmlst scheme download -s saureus_1
gmlst typing mlst -s saureus_1 sample.fasta
```

### Sharing cache across conda environments

By default, each conda environment uses `$CONDA_PREFIX/share/gmlst` as its cache, keeping databases isolated. To share one cache across all environments:

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
```

### Offline use

- Cached schemes and indexes support repeat typing without re-downloading data.
- `scheme list` can read cached catalogs.
- `scheme update` and downloading new schemes still require network access.

## Provider Endpoints

### Built-in defaults

| Provider | Default URL |
| --- | --- |
| PubMLST | `https://rest.pubmlst.org/db` |
| Pasteur BIGSdb | `https://bigsdb.pasteur.fr/api/db` |

### Self-hosted BIGSdb example

```bash
export GMLST_PUBMLST_BASE_URL="http://127.0.0.1:8000/api/db"
gmlst scheme list -p pubmlst
```

### Private provider example

```bash
export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
export GMLST_PRIVATE_BIGSDB_LABEL="Lab BIGSdb"

gmlst scheme list -p labdb
gmlst scheme update -s saureus_1 --cache-dir /data/gmlst-cache
```

## CLI Options vs Environment Variables

Use CLI flags when the setting belongs to one command invocation. Use environment variables when the setting is part of a session-wide or machine-wide default.

| Prefer CLI flag when... | Prefer environment variable when... |
| --- | --- |
| you are selecting scheme, backend, output, or threads for one run | you want a reusable default for temp space, provider endpoints, or minimap2/KMA tuning |
| you need a one-off cache location with `--cache-dir` | you want a shared cache directory across runs or environments (`GMLST_CACHE_DIR`) |
| you are testing alternative workflows side by side | you are running a stable pipeline in a shared shell environment |

Examples:

```bash
# Good CLI usage, run-specific
gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 -t 16 sample.fasta

# Good environment usage, session-wide
export GMLST_MINIMAP2_FASTA_SPEED_PROFILE=fast
export GMLST_TMPDIR=/scratch/gmlst
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fasta
```

## Configuration Examples

### Large cgMLST with minimap2 ultrafast

```bash
export GMLST_MINIMAP2_FASTA_SPEED_PROFILE=ultrafast
export GMLST_CGMLST_EXACT_HASH_PREFILTER=1
export GMLST_CGMLST_MINIMAP2_HASH_PREFILTER=1
export GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI=adaptive

gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 --cgmlst-mode ultrafast -t 16 samples/*.fasta -o cgmlst.tsv
```

### FASTQ cgMLST with KMA

```bash
export GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS=8
export GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1
export GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI=64

gmlst typing cgmlst -s vparahaemolyticus_3 -b kma reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

### Self-hosted BIGSdb

```bash
export GMLST_PUBMLST_BASE_URL="http://bigsdb.local/api/db"
gmlst scheme list -p pubmlst
gmlst scheme download -s saureus_1
```

### Provider authentication

Since 1 January 2025, PubMLST and Pasteur BIGSdb require authentication for data added after 31 December 2024. Set API keys to access the latest scheme data:

```bash
# PubMLST (obtain at pubmlst.org → Preferences → API keys)
gmlst config set GMLST_PUBMLST_API_KEY XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX

# Pasteur BIGSdb (request at bigsdb.pasteur.fr/requesting-api-key/)
gmlst config set GMLST_PASTEUR_API_KEY YYYYYYYY-YYYY-YYYY-YYYY-YYYYYYYYYYYY

# Auto-load in every new shell (run once, safe to repeat)
gmlst config init

# Apply now in current shell
source ~/.config/gmlst/env.sh
```

After this, `gmlst scheme download` and `gmlst scheme update` will automatically include the `Authorization: Bearer <key>` header when communicating with PubMLST or Pasteur. Pre-2025 data remains accessible without keys.

### Custom temporary directory

```bash
export GMLST_TMPDIR=/scratch/gmlst-tmp
gmlst typing mlst -s saureus_1 -b minimap2 reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

### Performance tuning with minimap2 fallback

```bash
export GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=blastn
export GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI=120
export GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI=500

gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 --cgmlst-mode fast -t 12 sample.fasta
```
