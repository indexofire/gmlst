# gmlst Architecture

This document explains how `gmlst` is structured, how data moves through the system, and where each major responsibility lives in the repository. For installation and user-facing command syntax, see [`docs/installation.md`](installation.md), [`docs/quickstart.md`](quickstart.md), [`docs/commands.md`](commands.md), and [`docs/providers.md`](providers.md).

## Overview

`gmlst` is a layered Python CLI for MLST, cgMLST, wgMLST, and scheme-free typing. The project combines a stable command surface, backend-agnostic alignment and calling logic, cached scheme databases, and an optional visualization stack.

The main design goals are:

- keep the CLI thin and move decisions into reusable domain code
- support multiple alignment backends behind one normalized result model
- support multiple remote scheme providers behind one provider interface
- cache schemes and indexes so repeated runs work quickly and can run offline
- keep FASTA, FASTQ, and cgMLST-specific policy explicit in code, not hidden in backend implementations

## System architecture diagram

```text
                                +------------------+
                                |  User / Shell    |
                                +--------+---------+
                                         |
                                         v
                                +------------------+
                                | gmlst/cli.py     |
                                | Click entrypoint |
                                +--------+---------+
                                         |
              +--------------------------+---------------------------+
              |                          |                           |
              v                          v                           v
    +------------------+      +------------------+       +------------------+
    | commands/typing  |      | commands/scheme  |       | visual/cli.py    |
    | commands/utils   |      | catalog/cache UX |       | Flask / exports  |
    +--------+---------+      +--------+---------+       +--------+---------+
             |                         |                           |
             v                         v                           v
    +------------------+      +------------------+       +------------------+
    | core/ pipeline   |      | database/cache.py|       | visual/app.py    |
    | calling/         |      | providers/*      |       | visual/mst.py    |
    | novel/           |      | download.py      |       | web/* assets     |
    | schemefree/      |      +------------------+       +------------------+
    +--------+---------+
             |
             v
    +------------------+
    | aligners/*       |
    | readers/*        |
    | external tools   |
    +--------+---------+
             |
             v
    +------------------+
    | Output layer     |
    | TSV / JSON / UI  |
    +------------------+
```

## Source code structure

The directory tree below shows the main code layout. Paths are repository-relative.

```text
gmlst/
├── __init__.py
├── __main__.py
├── cli.py
├── core_config.py
├── fasta_io.py
├── kmer_prefilter.py
├── metadata_io.py
├── utils.py
├── aligners/
│   ├── base.py
│   ├── blastn.py
│   ├── kma.py
│   ├── minimap2.py
│   └── nucmer.py
├── calling/
│   ├── allele.py
│   ├── chew_policy.py
│   ├── confidence.py
│   └── st_lookup.py
├── commands/
│   ├── common.py
│   ├── config.py
│   ├── typing.py
│   ├── typing_output.py
│   ├── typing_runner.py
│   ├── typing_runtime.py
│   ├── typing_scheme.py
│   ├── scheme.py
│   ├── scheme_common.py
│   ├── scheme_render.py
│   ├── scheme_custom.py
│   ├── utils.py
│   ├── utils_extract.py
│   └── utils_benchmark.py
├── core/
│   ├── config.py
│   ├── pipeline.py
│   ├── gene_predictor.py
│   ├── indexing.py
│   ├── prefilter.py
│   ├── ranking.py
│   ├── refinement.py
│   ├── sequences.py
│   ├── types.py
│   ├── cds.py
│   ├── exact_hash.py
│   ├── adapters_cds.py
│   ├── adapters_exact_hash.py
│   ├── adapters_index_prefilter.py
│   └── adapters_refinement.py
├── data/
│   ├── blocked_schemes.json
│   ├── organism_mapping.json
│   └── catalogs/
├── database/
│   ├── cache.py
│   ├── download.py
│   ├── schema.py
│   └── providers/
│       ├── __init__.py
│       ├── base.py
│       ├── bigsdb.py
│       ├── enterobase.py
│       ├── cgmlst.py
│       └── cgmlst_schemes.py
├── novel/
│   ├── reader.py
│   ├── service.py
│   └── writer.py
├── readers/
│   ├── fasta.py
│   ├── fastq.py
│   └── sample.py
├── schemefree/
│   ├── assembly_engine.py
│   ├── cluster_engine.py
│   ├── config.py
│   ├── gene_predictor.py   # re-export shim (impl in core/)
│   ├── hasher.py
│   ├── io_handler.py
│   └── typing_engine.py
├── visual/
│   ├── cli.py
│   ├── _cli_helpers.py
│   ├── _cli_export.py
│   ├── app.py
│   └── mst.py
└── web/
    ├── frontend/
    ├── static/
    └── templates/
```

### Top-level modules

- `gmlst/__main__.py` is the `python -m gmlst` entrypoint.
- `gmlst/cli.py` registers top-level Click groups, `typing`, `scheme`, `utils`, and `visual`.
- `gmlst/core_config.py` centralizes environment-driven cgMLST and backend toggles.
- `gmlst/fasta_io.py` and `gmlst/metadata_io.py` provide focused I/O helpers.
- `gmlst/utils.py` contains logging and shared utility helpers.

### Domain and orchestration packages

- `gmlst/core/` contains typing pipeline orchestration, indexing, prefiltering, ranking, refinement, sequence handling, and adapter layers.
- `gmlst/calling/` contains allele interpretation, confidence logic, chewBBACA-style policy, and ST lookup.
- `gmlst/novel/` contains novel allele/profile extraction and writing.
- `gmlst/schemefree/` contains the separate tgMLST workflow.

### Infrastructure packages

- `gmlst/aligners/` wraps BLAST+, KMA, minimap2, and MUMmer4 under one interface.
- `gmlst/database/` handles provider integration, downloads, catalogs, and cache layout.
- `gmlst/readers/` detects input type and groups FASTQ mate pairs.

### Presentation packages

- `gmlst/commands/` defines the CLI command behavior.
- `gmlst/visual/` exposes MST and result comparison APIs and the Flask app.
- `gmlst/web/` stores frontend source, built static assets, and templates.

## Architecture layers

### 1. CLI layer

The CLI layer lives in `gmlst/cli.py` and `gmlst/commands/`. It is responsible for:

- parsing user input with Click
- validating command combinations
- applying command-level policy, such as FASTQ cgMLST backend switching
- dispatching to domain logic
- formatting output for terminal or files

Important files:

- `gmlst/cli.py`
- `gmlst/commands/typing.py`
- `gmlst/commands/typing_runner.py`
- `gmlst/commands/typing_output.py`
- `gmlst/commands/typing_scheme.py`
- `gmlst/commands/scheme.py`
- `gmlst/commands/utils.py`
- `gmlst/visual/cli.py`

### 2. Domain layer

The domain layer lives mainly in `gmlst/core/`, `gmlst/calling/`, `gmlst/novel/`, and `gmlst/schemefree/`. It owns typing behavior and result interpretation.

Examples:

- `gmlst/core/pipeline.py` orchestrates sample typing end to end.
- `gmlst/calling/allele.py` and `gmlst/calling/st_lookup.py` turn alignments into calls and ST assignments.
- `gmlst/novel/service.py` collects and persists novel alleles and profiles.
- `gmlst/schemefree/typing_engine.py` coordinates de novo scheme-free typing.

### 3. Infrastructure layer

The infrastructure layer lives in `gmlst/aligners/`, `gmlst/database/`, and `gmlst/readers/`. It integrates external tools, remote sources, and local cache storage.

Examples:

- `gmlst/aligners/base.py` defines the aligner contract.
- `gmlst/database/providers/base.py` defines the provider contract.
- `gmlst/database/cache.py` manages scheme and index storage.
- `gmlst/readers/sample.py` detects FASTA versus FASTQ input and auto-groups mates.

### 4. Presentation layer

The presentation layer lives in `gmlst/visual/` and `gmlst/web/`.

- `gmlst/visual/app.py` creates the Flask application and JSON endpoints.
- `gmlst/visual/mst.py` computes profile distances, MSTs, heatmaps, and comparisons.
- `gmlst/web/frontend/` contains the Vue 3 + Vite source.
- `gmlst/web/templates/` and `gmlst/web/static/` serve built assets.

## Core data flow

The main typing flow starts at the CLI and ends in a formatted report.

```text
User command
  -> gmlst/cli.py
  -> gmlst/commands/typing.py
  -> gmlst/commands/typing_scheme.py
  -> gmlst/database/cache.py ensure_scheme()
  -> gmlst/core/pipeline.py run_typing_impl()
  -> gmlst/readers/sample.py detect_sample() / prepare_sample_inputs()
  -> gmlst/core/indexing.py and gmlst/core/pipeline.py index selection
  -> gmlst/aligners/<backend>.py align()
  -> gmlst/calling/allele.py call_all_loci()
  -> gmlst/core/refinement.py and adapter layers
  -> gmlst/calling/st_lookup.py lookup_st()
  -> gmlst/commands/typing_output.py emit TSV / JSON / pretty output
```

For batch runs, `gmlst/commands/typing_runner.py` adds sample-level parallelism on top of the same core pipeline.

## Alignment backend architecture

### Protocol pattern

`gmlst/aligners/base.py` defines the `Aligner` `Protocol`. In Python, a `Protocol` is a structural interface. A backend does not need to inherit from one base class. It only needs to provide the required attributes and methods.

In practice, each aligner implementation must behave like this contract:

- `name`
- `supports_fastq`
- `check_dependencies()`
- `index(allele_fastas, index_dir)`
- `align(sample, index_path, loci, input_type)`

This lets `gmlst/core/pipeline.py` choose a backend once and then use it generically.

### `AlleleMatch` normalization

`gmlst/aligners/base.py` also defines `AlleleMatch` and `AlignmentResult`.

Every backend translates its native output into `AlleleMatch`, including:

- locus name
- allele id
- identity
- coverage
- score
- depth for read-based inputs when available
- extracted sequence for novel allele paths when available
- coordinate and copy-count metadata when available

This normalization is the key reason downstream calling can stay backend-agnostic.

### Backend implementations

- `gmlst/aligners/blastn.py` targets BLAST+ and FASTA-heavy workflows.
- `gmlst/aligners/kma.py` supports FASTA and FASTQ, and is the preferred cgMLST FASTQ route.
- `gmlst/aligners/minimap2.py` supports FASTA and FASTQ, plus representative and hash-prefilter driven cgMLST optimizations.
- `gmlst/aligners/nucmer.py` targets MUMmer4 for FASTA alignment.

## Database provider architecture

### Provider protocol

`gmlst/database/providers/base.py` defines the `Provider` `Protocol`. Like the aligner contract, this is a structural interface.

Each provider must expose:

- `name`
- `label`
- `list_schemes()`
- `download_scheme()`
- `update_scheme()`

Each listed scheme is represented as `SchemeInfo` from `gmlst/database/providers/base.py`, which carries:

- `scheme_name`
- `display_name`
- `organism`
- `scheme_type`
- `n_loci`
- `provider`
- `extra` for provider-specific fields such as URLs or directory names

### Provider registry

`gmlst/database/providers/__init__.py` builds the runtime registry. It always registers:

- `pubmlst` via `gmlst/database/providers/bigsdb.py`
- `pasteur` via `gmlst/database/providers/bigsdb.py`
- `enterobase` via `gmlst/database/providers/enterobase.py`
- `cgmlst` via `gmlst/database/providers/cgmlst.py`

If `GMLST_PRIVATE_BIGSDB_URL` is set, the registry also creates a private BIGSdb provider entry at runtime.

### Catalog management and global uniqueness

`gmlst/database/cache.py` manages cached provider catalogs under `_catalog/`. It also guarantees that scheme names stay globally unique across providers.

This logic has two layers:

1. `_normalize_scheme_names()` normalizes names within one provider catalog.
2. `save_catalog()` compares those names with all other cached catalogs and bumps numeric suffixes when needed.

That is why names like `spneumoniae_1`, `spneumoniae_2`, and later `spneumoniae_3` can coexist across providers without collisions.

## CLI layer

### Top-level command registration

`gmlst/cli.py` registers four top-level groups:

- `typing`
- `scheme`
- `utils`
- `visual`

`gmlst/__main__.py` makes the same entrypoint available through `python -m gmlst`.

### Typing command dispatch

Typing commands are implemented in `gmlst/commands/typing.py`. This module handles:

- sample preparation
- scheme type detection
- backend and mode validation
- temporary directory policy
- streaming versus final output
- optional novel allele/profile extraction

`gmlst/commands/typing_runner.py` adds sample-level parallel execution. When `--max-workers` is used, it forces per-sample backend threads to `1` and fans work out across samples.

### Scheme command responsibilities

`gmlst/commands/scheme.py` handles:

- catalog listing and refresh
- downloads and updates
- blocked scheme filtering via `gmlst/commands/common.py`
- local custom scheme creation and update under the `local` provider namespace

### FASTQ cgMLST policy at the command layer

The command layer owns one important policy decision. For cgMLST runs with FASTQ input, the backend is KMA-first. If the user selects `minimap2`, `gmlst/commands/typing.py` detects FASTQ samples and switches to `kma`, then forces `cgmlst_mode=standard`.

This keeps FASTQ cgMLST behavior explicit and avoids pretending that FASTA-only chew-style optimization branches apply to raw reads.

## Core pipeline

The main runtime entry is `run_typing_impl()` in `gmlst/core/pipeline.py`.

At a high level it does the following:

1. create `DatabaseCache`
2. resolve and cache the requested scheme
3. resolve mode overrides from `cgmlst_mode`
4. construct the selected aligner and verify external dependencies
5. detect each sample with `gmlst/readers/sample.py`
6. build or reuse indexes
7. decide whether prefiltering and exact-hash shortcuts are active
8. align each sample, or each unresolved locus set after exact matching
9. call loci and apply post-alignment refinements
10. perform ST lookup
11. emit results back to the command layer

### Indexing and reuse

Persistent backend indexes live under `DatabaseCache.index_dir()` in `gmlst/database/cache.py`. `gmlst/core/pipeline.py` only rebuilds indexes when needed or when `force_reindex` is enabled.

### Prefiltering and candidate narrowing

For large cgMLST schemes, the pipeline can avoid aligning against the entire allele database. `gmlst/core/pipeline.py`, `gmlst/core/prefilter.py`, `gmlst/kmer_prefilter.py`, and the adapter modules in `gmlst/core/adapters_index_prefilter.py` support:

- k-mer candidate narrowing for assembly inputs
- minimap2 representative prefiltering
- representative-only minimap2 main alignment in some FASTA routes

### Ranking and refinement

The initial best hits are not always the final answer. `gmlst/core/ranking.py`, `gmlst/core/refinement.py`, and adapter modules in `gmlst/core/adapters_refinement.py` refine calls after alignment. This is where backend-specific evidence can be folded back into a backend-independent call set.

## FASTA versus FASTQ execution paths

### Input detection and pair grouping

`gmlst/readers/sample.py` is the source of truth for input detection.

- FASTA suffixes include `.fasta`, `.fa`, `.fna`, `.ffn`, `.frn`
- FASTQ suffixes include `.fastq`, `.fq`, with optional `.gz`
- mate grouping recognizes patterns based on `_R1` and `_R2`, `_1` and `_2`, and `.1` and `.2`

Grouped pairs are converted into one `SampleInput` with `path` and `mate_path`.

### FASTA path

The FASTA path is the richer optimization path. In `gmlst/core/pipeline.py`, assembled genomes can use:

- exact DNA and protein hash pre-resolution
- cgMLST prefiltering
- minimap2 representative alignment shortcuts
- chewBBACA-style CDS-aware classification
- post-alignment refinement and evidence fallback paths

### FASTQ path

FASTQ support is intentionally narrower.

- only `kma` and `minimap2` advertise `supports_fastq` in the aligner contract
- cgMLST FASTQ runs are normalized to the KMA-first route at the CLI layer
- minimap2 FASTQ remains available for non-cgMLST cases where the user chooses it directly
- exact-hash and assembly-style cgMLST prefilter paths are gated off unless all samples are single-file FASTA inputs

## cgMLST modes

cgMLST mode configuration is driven by `gmlst/core_config.py` plus override logic inside `gmlst/core/` and `gmlst/core/pipeline.py`.

The user-visible modes are:

- `standard`
- `chew-fast`
- `chew-ultrafast`
- `chew-balanced`

These modes mainly affect FASTA-oriented minimap2 and refinement behavior, for example:

- whether exact-hash shortcuts are enabled
- whether minimap2 hash prefiltering is enabled
- whether representative-main alignment is allowed
- how large the second-pass rescue budget is
- whether CDS-aware chew-style classification is active

Relevant files:

- `gmlst/core_config.py`
- `gmlst/core/pipeline.py`
- `gmlst/calling/chew_policy.py`
- `gmlst/core/cds.py`
- `gmlst/core/exact_hash.py`
- `gmlst/core/adapters_cds.py`
- `gmlst/core/adapters_exact_hash.py`

For FASTQ cgMLST, `gmlst/commands/typing.py` forces these mode choices back to `standard`.

## Novel allele workflow

Novel allele handling spans the typing and scheme commands.

### During typing

`gmlst/novel/service.py` collects novel alleles and novel profiles from typing results. Writers from `gmlst/novel/writer.py` persist:

- per-locus `*_novel.fasta`
- `profiles_novel.txt`

### During custom scheme creation

`gmlst/commands/scheme.py` uses those files to build local schemes named `custom_<n>` under the `local` namespace. Metadata is assembled with helpers from `gmlst/novel/service.py` and stored as `.meta.json` next to the allele FASTA and profile files.

This makes novel discovery part of a repeatable loop:

```text
typing result
  -> novel extraction
  -> local custom scheme creation
  -> later custom scheme update with more novel data
```

## Scheme-free typing, tgMLST

Scheme-free typing lives in `gmlst/schemefree/` and is separate from downloaded provider-backed schemes.

The main entry is `SchemeFreeTyper` in `gmlst/schemefree/typing_engine.py`. It coordinates:

1. optional assembly for FASTQ via `gmlst/schemefree/assembly_engine.py`
2. gene prediction via `gmlst/core/gene_predictor.py`
3. clustering via `gmlst/schemefree/cluster_engine.py`
4. allele hashing via `gmlst/schemefree/hasher.py`
5. scheme import and export via `gmlst/schemefree/io_handler.py`

This path is exposed from `gmlst/commands/typing.py` and does not depend on the provider cache model used by classic MLST and cgMLST typing.

## Visualization architecture

The visualization stack has two main layers.

### Backend layer

- `gmlst/visual/cli.py` exposes export and server commands.
- `gmlst/visual/app.py` creates the Flask app and validates JSON payloads.
- `gmlst/visual/mst.py` computes distances, mismatch loci, aggregate nodes, and MST edges from typing output tables.

### Frontend layer

- `gmlst/web/frontend/` contains the Vue 3 + Vite source
- `gmlst/web/templates/` contains HTML templates used by Flask
- `gmlst/web/static/` contains built assets served by Flask

The visual stack is intentionally decoupled from the typing pipeline. It consumes exported TSV or JSON-like payloads instead of calling the alignment pipeline directly.

## Cache management

`gmlst/database/cache.py` is the core cache manager. The cache root is resolved in order: explicit parameter, `GMLST_CACHE_DIR` env var, `$CONDA_PREFIX/share/gmlst` (conda), `$VIRTUAL_ENV/.cache/gmlst` (venv), or `~/.cache/gmlst` as fallback. Each conda or virtualenv environment gets its own isolated cache by default.

Typical layout:

```text
~/.cache/gmlst/
├── <provider>/
│   └── <scheme_name>/
│       ├── <locus>.tfa or <locus>.fasta
│       ├── <scheme_name>.txt or .tsv
│       └── .meta.json
├── _catalog/
│   └── <provider>.json
└── _indexes/
    └── <provider>/
        └── <backend>/
            └── <scheme_name>/
```

### Offline operation

Once a scheme and its indexes are cached, typing can reuse them without re-downloading provider content. The built-in catalog files under `gmlst/data/catalogs/` can also be copied into cache as defaults when no local catalog exists yet.

## Key design decisions

### Why use `Protocol`

The aligner and provider systems both use `Protocol` instead of deep inheritance trees. This keeps integrations simple. New implementations only need to satisfy the interface shape, which reduces coupling between orchestration code and concrete backends.

### Why normalize backend output

Without `AlleleMatch` in `gmlst/aligners/base.py`, each downstream calling path would need backend-specific conditionals. Normalization keeps `gmlst/calling/` focused on allele semantics instead of parsing BLAST, KMA, minimap2, or nucmer output formats.

### Why keep FASTQ policy in the CLI layer

The FASTQ cgMLST KMA-first rule is not a generic backend property. It is a product-level policy choice. Keeping it in `gmlst/commands/typing.py` makes the behavior visible and easier to change without rewriting backend modules.

### Why cache catalogs and indexes

The provider list operation and backend indexing are both expensive relative to a normal command parse. Persisting catalogs and indexes reduces repeated network work and repeated index builds.

### Why use Click

Click gives the project consistent option parsing, grouped commands, shell-friendly help output, and straightforward composition across `typing`, `scheme`, `utils`, and `visual` command families.

## Repository path conventions

These conventions describe how code is organized today and where new code should live.

### Code placement

- CLI registration belongs in `gmlst/cli.py` or feature-local CLI modules such as `gmlst/visual/cli.py`.
- Command implementation belongs in `gmlst/commands/`.
- Pure typing orchestration belongs in `gmlst/core/`.
- Allele and ST interpretation belongs in `gmlst/calling/`.
- Remote provider and cache logic belongs in `gmlst/database/`.
- External aligner integrations belong in `gmlst/aligners/`.
- Input detection belongs in `gmlst/readers/`.
- Visualization code belongs in `gmlst/visual/` and `gmlst/web/`.

### Naming rules

- modules and files use `snake_case`, for example `typing_runner.py`
- classes use `PascalCase`, for example `DatabaseCache`, `SchemeInfo`, `SchemeFreeTyper`
- functions and variables use `snake_case`
- constants use `UPPER_SNAKE_CASE`

### Documentation paths

- architecture and contributor docs live in `docs/`
- Chinese translations live in `docs/zh/`
- provider-specific reference lives in [`docs/providers.md`](providers.md)
