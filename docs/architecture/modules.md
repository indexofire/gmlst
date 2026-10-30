# Modules and Layers

Where code lives, how the four layers divide responsibility, and the placement and naming conventions new code should follow.

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
- Chinese translations live in the same path with a `.zh.md` suffix
- provider-specific reference lives in [`docs/usage/providers.md`](../usage/providers.md)

## Dependency direction

Imports flow in one direction:

```text
commands/ + visual/cli.py  ->  core/ calling/ novel/ schemefree/  ->  aligners/ database/ readers/
```

Practical consequences:

- `gmlst/core/` must not import `click`.
- `gmlst/aligners/` must not import `gmlst/database/`.
- `gmlst/calling/` accepts normalized `AlleleMatch` objects, never raw backend
  output.

If a change seems to require an import that points the other way, the logic is
probably in the wrong layer.

## Worked example: placing a new feature

| Change | Correct home | Why |
| --- | --- | --- |
| Add `--min-depth` validation | `gmlst/commands/typing.py` | User input policy |
| Add a new output column | `gmlst/commands/typing_output.py` | Presentation concern |
| Add a prefilter heuristic | `gmlst/core/prefilter.py` | Pure domain logic |
| Parse a new aligner output format | `gmlst/aligners/<tool>.py` | Normalization at the boundary |
| Add a provider HTTP endpoint | `gmlst/database/providers/<name>.py` | External integration |
| Change scheme name uniqueness | `gmlst/database/cache.py` | Catalog ownership |

A quick rule: if the code needs `click`, `rich`, or `sys.exit`, it belongs in
`commands/`; if it needs `subprocess` to call a tool, it belongs in `aligners/`
or `database/download.py`; everything else is domain logic.
