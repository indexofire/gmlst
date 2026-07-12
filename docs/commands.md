# Command Reference

This page documents the current `gmlst` CLI surface.

## Help Behavior

- `-h` and `--help` are equivalent at all levels.
- Running a command group with no subcommand prints its usage/help text:
  - `gmlst`
  - `gmlst scheme`
  - `gmlst utils`
  - `gmlst visual`

## Top-Level CLI

```bash
gmlst [OPTIONS] COMMAND [ARGS]...
```

Global options:

- `-V, --version`
- `-v, --verbose`
- `-q, --quiet`
- `-h, --help`

Top-level commands:

- `typing` - type FASTA/FASTQ samples against a scheme
- `scheme` - scheme/provider/cache management
- `utils` - extraction and sequence utility commands
- `visual` - local web visualization tools

## typing

```bash
gmlst typing [OPTIONS] COMMAND [ARGS]...
```

Subcommands:

- `mlst` - MLST schemes only
- `cgmlst` - cgMLST/wgMLST schemes only
- `tgmlst` - scheme-free typing mode

Examples:

```bash
gmlst typing mlst -s saureus_1 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --prefilter-k 31 --prefilter-top-n 20 sample.fna
gmlst typing tgmlst sample.fna
```

Legacy compatibility:

```bash
gmlst typing -s saureus_1 sample.fna
gmlst typing -s schemefree sample.fna
```

`mlst` and `cgmlst` common options:

- `-s, --scheme TEXT` (required)
- `-b, --backend [blastn|kma|minimap2|nucmer]`
- `--format [tsv|json|pretty]`
- `-o, --output PATH`
- `-t, --threads INTEGER`
- `--max-workers INTEGER` (sample-level parallel workers)
- `-q, --quiet`
- `--data-dir, --output-dir PATH` (preferred: `--data-dir`)
- `--novel-allele`
- `--novel-profile` (requires `--novel-allele`)
- `-h, --help`

`cgmlst` prefilter options:

- `--cgmlst-mode [standard|chew-fast|chew-ultrafast|chew-bsr|chew-balanced]`
- `--prefilter-k INTEGER`
- `--prefilter-top-n INTEGER`
- `--prefilter-min-loci-fraction FLOAT`
- `--cds-coordinates-out PATH` (export predicted CDS coordinates as TSV)
- `--call-policy [default|chewbbaca]` (chew-style output classification)
- `--chew-cds-gate/--no-chew-cds-gate` (only for `--call-policy chewbbaca`)

`cgmlst` defaults and performance notes:

- Default backend for `typing cgmlst` is `minimap2`.
- `--cgmlst-mode standard`: conservative behavior, no forced chew-style overrides.
- `--cgmlst-mode chew-fast`: enables exact-hash + minimap2 hash prefilter plus automatic missing-locus minimap2 refinement (default cap: 500 loci), then targeted blastn evidence fallback for low-confidence loci (default cap: 500 loci).
- `--cgmlst-mode chew-ultrafast`: same as `chew-fast`, but uses representative-only main alignment, disables minimap2 FASTA CIGAR emission, applies an ultrafast minimap2 FASTA speed profile, performs a strict low-confidence rescue pass (default limit: 120 loci), and then runs a second targeted pass with an adaptive budget over remaining partial/closest loci.
- `--cgmlst-mode chew-bsr`: adds protein-level exact-hash pre-resolution on top of `chew-fast` (including missing-locus refinement cap 500 and targeted blastn fallback cap 500). By default, no additional strict confirmation pass is performed (`BSR_CONFIRM_MAX_LOCI=0`), but you can enable targeted confirmation via environment variable when needed.
- `--cgmlst-mode chew-balanced`: enables exact-hash + minimap2 hash prefilter + targeted `blastn` fallback for low-confidence loci.
- For FASTQ inputs, `typing cgmlst` now auto-switches `-b minimap2` to `-b kma` and treats `--cgmlst-mode` as compatibility-only (`standard`) because chew-style mode optimizations are FASTA-oriented.
- `--call-policy chewbbaca` requires FASTA assemblies and keeps raw calls unchanged while rendering chew-style per-locus class labels in output.
- By default, `--call-policy chewbbaca` enforces CDS-gated classification (`--chew-cds-gate`). Use `--no-chew-cds-gate` to allow classification from any matched sequence context.

Architecture lock:

- FASTA: chew-style mode branches are active and interpreted normally.
- FASTQ: KMA-first policy is enforced at CLI layer; mode-specific chew branches are not interpreted as FASTQ features.
- Full contract and flow diagrams: see `docs/architecture.md`.

Additional tuning:

- `GMLST_MINIMAP2_FASTA_SPEED_PROFILE=default|fast|ultrafast`
  - `default`: existing minimap2 behavior
  - `fast`: moderate seed/chaining acceleration (`-w 15 -e 1000 -K 1G`)
  - `ultrafast`: aggressive speed profile (`fast` + `-f 0.001 -U 50,1000`)

- `GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI=adaptive|<int>`
  - `adaptive` (default): auto-scales second-pass budget by residual partial/closest burden
  - `<int>`: forces a fixed budget for the ultrafast second pass

- `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS=<int>`
  - Default: `8`
  - FASTQ cgMLST with KMA auto-raises per-sample threads from `1` to this value (capped by CPU count)
  - Set to `1` to disable auto-raise

- `GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1|0`
  - Default: `1`
  - Enables KMA `-mem_mode` for FASTQ cgMLST to accelerate single-thread mapping.

- `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI=<int>`
  - Default: `64`
  - After mem_mode pass, re-check up to this many `closest` loci with strict KMA (without `-mem_mode`) to recover exact calls.
- Prefilter auto-skip threshold is controlled by `GMLST_CGMLST_PREFILTER_MAX_LOCI` (default: `3000`).
  - Set to `0` to disable auto-skip and always attempt prefilter.
- For `-b kma` and default `-b minimap2`, cgMLST prefilter is skipped and the persistent full-index path is used.
- Set `GMLST_CGMLST_EXACT_HASH_PREFILTER=1` to enable chewBBACA-style DNA exact-match pre-resolution (CDS hash first).
- Set `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER=1` to enable experimental hash-first prefilter for minimap2 FASTA.
- `GMLST_CGMLST_CDS_PREDICTION_MODE=single|meta` controls Pyrodigal CDS mode for cgMLST exact-hash pre-resolution (default: `single`).
- `GMLST_CGMLST_CDS_TRAINING_FILE=/path/to/pyrodigal_training.trn` uses a fixed training file; if unset and mode is `single`, gmlst auto-creates and reuses `pre_computed/pyrodigal_training.trn` on first run.
- `GMLST_CGMLST_CDS_CLOSED_ENDS=1|0` controls Pyrodigal closed-end prediction behavior (default: `0`).
- `GMLST_CGMLST_CDS_COORDINATES_OUT=/path/to/cds_coordinates.tsv` exports predicted CDS coordinates for chewBBACA coordinate comparison.
- `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI` controls max missing loci for second-pass refinement when mode override does not set it (default: `0`, disabled).
- `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND` enables evidence-based targeted fallback for low-confidence loci (`none`/`blastn`/`kma`/`nucmer`, default: `none`).
- `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI` limits fallback scope by locus count (default: `300`, set `0` for no limit).
- For large cgMLST schemes with `-b kma`, set `-t` (for example `-t 8` to `-t 16`); `-t 1` can be much slower.

`tgmlst` options (scheme-free):

- `--format [tsv|json|pretty]`
- `-o, --output PATH`
- `--no-header`
- `--hash-strategy [safe|fast|ultra|strict|blast]`
- `--save-scheme PATH`
- `--load-scheme PATH`
- `--stats`
- `--max-workers INTEGER`
- `--assemble-timeout FLOAT`
- `--error-report PATH`
- `--fail-on-error`
- `--summary-report PATH`

Notes:

- JSON output includes per-locus `novel_sequence` data for downstream extraction.
- `--count-same-copy` currently applies to blastn same-allele multicopy counting.
- In `mlst/cgmlst` modes, FASTQ paired-end files are auto-detected and passed as paired input (no pre-merge) when naming matches common pairs:
  - `_R1` / `_R2`
  - `_1` / `_2`
  - `.1` / `.2`
  - Supports `.fastq`, `.fq`, and `.gz` variants.
- `minimap2` FASTQ mode uses a candidate pass plus targeted validation on uncertain loci.
- `GMLST_MINIMAP2_KMER_ENGINE` controls minimap2 k-mer support scoring (`python`, `kmc`, `auto`).
- `GMLST_TMPDIR` can be set to control where temporary files are created.

## scheme

```bash
gmlst scheme [OPTIONS] COMMAND [ARGS]...
```

Subcommands:

- `list`
- `search`
- `show`
- `download`
- `update`
- `create`
- `update-custom`
- `export`

### scheme download

```bash
gmlst scheme download SCHEME [OPTIONS]
```

Positional argument:

- `SCHEME` — scheme name (e.g., `saureus_1`)

Options:

- `-s, --scheme TEXT` (deprecated, use positional argument)
- `--force`
- `-q, --quiet`
- `--download-tool [auto|aria2c|curl|wget|httpx|requests]`
- `-x, --connections INTEGER` (default: 4)
- `--token TEXT`
- `--cache-dir PATH`

Examples:

```bash
gmlst scheme download saureus_1
gmlst scheme download vparahaemolyticus_3 --force -x 2
```

### scheme search

```bash
gmlst scheme search PATTERN [OPTIONS]
```

Search schemes by name, organism, description, or provider.

Positional argument:

- `PATTERN` — case-insensitive substring to search for

Options:

- `-p, --provider [<registered-provider>|local|all]`
- `-t, --type [mlst|cgmlst|wgmlst|all]`
- `--cache-dir PATH`

Example:

```bash
gmlst scheme search saureus
gmlst scheme search "salmonella" -t cgmlst
```

### scheme list

```bash
gmlst scheme list [OPTIONS]
```

Typical options:

- `-p, --provider [<registered-provider>|local|all]`
- `-t, --type [mlst|cgmlst|wgmlst|all]`
- `-n, --name TEXT`
- `-f, --format [text|table|csv|tsv|json]`
- `-a, --available`
- `--cache-dir PATH`

Blocked scheme configuration:

- `scheme list` filters entries using `gmlst/data/blocked_schemes.json`.
- `scheme show`, `scheme download`, and `scheme update` reject blocked schemes.
- Format: provider name → list of `scheme_name` values to hide.
- Template:

```json
{
  "_comment": "List of schemes that should be blocked/hidden from the user",
  "pubmlst": ["salmonella_1"],
  "pasteur": [],
  "enterobase": [],
  "cgmlst": []
}
```

Example (hide one scheme):

```json
{
  "pubmlst": ["vparahaemolyticus_3"],
  "pasteur": [],
  "enterobase": [],
  "cgmlst": []
}
```

Notes:

- Values must use canonical `scheme_name` (for example `saureus_1`, `vparahaemolyticus_3`).
- Filtering is currently applied to `scheme list` output.

### scheme show

```bash
gmlst scheme show [OPTIONS]
```

Options:

- `-s, --scheme TEXT`
- `-f, --format [text|table|csv|tsv|json]`
- `--cache-dir PATH`

Behavior:

- With `-s`: show detailed information for one scheme.
- Without `-s`: show guidance, then fall back to listing output.

### scheme update

```bash
gmlst scheme update [OPTIONS]
```

Options:

- `-s, --scheme TEXT`
- `-f, --force`
- `--download-tool [auto|aria2c|curl|wget|httpx|requests]`
- `-x, --connections INTEGER`
- `--token TEXT`
- `--cache-dir PATH`

Behavior:

- Without `-s`: refresh provider catalogs.
- With `-s`: provider-specific cached-scheme refresh/update.

Provider endpoint override (for self-hosted BIGSdb):

- `GMLST_PUBMLST_BASE_URL` (default: `https://rest.pubmlst.org/db`)
- `GMLST_PASTEUR_BASE_URL` (default: `https://bigsdb.pasteur.fr/api/db`)
- `GMLST_PRIVATE_BIGSDB_URL` (register private BIGSdb provider)
- `GMLST_PRIVATE_BIGSDB_NAME` (optional, default: `private`)
- `GMLST_PRIVATE_BIGSDB_LABEL` (optional display label)

Example:

```bash
export GMLST_PUBMLST_BASE_URL="http://127.0.0.1:8000/api/db"
gmlst scheme list -p pubmlst

export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
gmlst scheme list -p labdb
```

### scheme create

```bash
gmlst scheme create [OPTIONS]
```

Options:

- `-t, --type [mlst]` (required)
- `-s, --source TEXT` (required)
- `--data-dir, --datadir DIRECTORY` (required; preferred: `--data-dir`)
- `--desc TEXT`
- `--cache-dir PATH`

### scheme update-custom

```bash
gmlst scheme update-custom SCHEME [OPTIONS]
```

Positional argument:

- `SCHEME` — custom scheme name (e.g., `custom_1`)

Options:

- `-s, --scheme TEXT` (deprecated, use positional argument)
- `--data-dir, --datadir DIRECTORY` (required; preferred: `--data-dir`)
- `--cache-dir PATH`

### scheme export

```bash
gmlst scheme export SCHEME [OPTIONS]
```

Positional argument:

- `SCHEME` — scheme name (e.g., `custom_1`)

Options:

- `-s, --scheme TEXT` (deprecated, use positional argument)
- `--format [grapetree|original]` (required)
- `-o, --output PATH` (required)
- `--cache-dir PATH`

## utils

```bash
gmlst utils [OPTIONS] COMMAND [ARGS]...
```

Subcommands:

- `extract`
- `concat`
- `benchmark`
- `check`

### utils extract

```bash
gmlst utils extract [OPTIONS]
```

Primary modes:

1. Allele extraction from sample FASTA/FASTQ

```bash
gmlst utils extract -i genome.fasta -s ecoli_1 [--allele dnaN,tsvA]
```

2. Novel data extraction from typing JSON

```bash
gmlst utils extract -i typing_results.json --novel-allele --novel-profile --data-dir novel
```

3. TSV fallback for novel allele extraction (re-typing mode)

```bash
gmlst utils extract -i typing_results.tsv -s ecoli_1 --novel-allele --novel-profile \
  --samples-dir ./samples --data-dir novel
```

Key options:

- `-i, --input PATH` (required)
- `-s, --scheme TEXT` (required for allele extraction and TSV fallback re-typing)
- `-p, --provider TEXT`
- `--allele TEXT`
- `-b, --backend TEXT`
- `--novel-allele`
- `--novel-profile`
- `--data-dir PATH`
- `--samples-dir DIRECTORY` (TSV fallback with `--novel-allele`)
- `--cache-dir PATH`

### utils concat

```bash
gmlst utils concat -i genome_mlst.fasta [-o genome_mlst_concat.fasta]
```

Behavior:

- Concatenates input FASTA records in order into one FASTA sequence.

### utils check

```bash
gmlst utils check -b blastn
```

Behavior:

- Runs backend dependency check and reports availability.
- Exits with non-zero status if dependency is missing.

### utils benchmark

```bash
gmlst utils benchmark [OPTIONS] SAMPLES...
```

Options:

- `-s, --scheme TEXT` (required)
- `-b, --backends TEXT`
- `-r, --repeat INTEGER`
- `-f, --format [table|tsv|json]`
- `--cgmlst-gate`
- `--gate-max-mismatches INTEGER`
- `--gate-details-output PATH`
- `--gate-details-format [jsonl|tsv]`
- `-o, --output PATH`
- `--cache-dir PATH`
- `--force-reindex`
- `-h, --help`

## config

```bash
gmlst config [OPTIONS] COMMAND [ARGS]...
```

Inspect and manage gmlst configuration variables.

Subcommands:

- `env` — print all environment variables in shell format (sourceable)
- `show` — display configuration in a grouped table with current values
- `get` — get the current value of a single variable
- `set` — write a variable to the config file

### config env

```bash
gmlst config env
```

Prints `export NAME="value"` lines for every variable that is currently set in the environment. Output can be sourced directly:

```bash
eval "$(gmlst config env)"
```

### config show

```bash
gmlst config show
```

Displays all 29 configuration variables in a grouped table (Cache, Provider, Security, Auth, cgMLST). Shows the current value (or the default if unset) and a description for each.

### config get

```bash
gmlst config get NAME
```

Prints the current value of a single variable, or its default if unset.

```bash
gmlst config get GMLST_CACHE_DIR
```

### config set

```bash
gmlst config set NAME VALUE
```

Writes `export NAME="VALUE"` to `~/.config/gmlst/env.sh`. Source this file in your shell profile to apply the change:

```bash
gmlst config set GMLST_CACHE_DIR /data/gmlst-cache
source ~/.config/gmlst/env.sh
```

**Note**: Provider URL variables (`GMLST_PUBMLST_BASE_URL`, `GMLST_PRIVATE_BIGSDB_URL`, etc.) are read at import time. You must `source` the config file before running gmlst for changes to take effect.

## visual

```bash
gmlst visual [OPTIONS] COMMAND [ARGS]...
```

Subcommands:

- `web` - start local HTTP app for minimal-spanning-tree visualization

### visual web

```bash
gmlst visual web [OPTIONS]
```

Options:

- `--host TEXT` (default: `127.0.0.1`)
- `--port INTEGER` (default: `8787`)
- `--open-browser`

Usage:

```bash
gmlst visual web --open-browser
```

Then paste or upload a cgMLST TSV file in the web UI and click **Build MST**.

Implementation:

- Backend: Flask routes (`/`, `/health`, `/api/mst`)
- Frontend: Vue 3 app built by Vite and served as static assets
  (`gmlst/web/frontend` -> `gmlst/web/static/visual/dist`)

Behavior:

- Builds an MST from profile distances (per-locus allele differences).
- Supports missing-token penalty toggle (`LNF`, `NIPH`, `NIPHEM`, etc.).
- Supports two layouts in UI: `tree` and `radial`.
- Supports metadata-based node coloring (from TSV metadata columns).
- Supports SVG export from the UI.
- Accepts both gmlst TSV and GrapeTree-style profiles (`#Strain` first column).

For deeper discrepancy-analysis and experimental helper scripts, see internal
docs under [`docs/internal/`](https://github.com/indexofire/gmlst/tree/main/docs/internal).
