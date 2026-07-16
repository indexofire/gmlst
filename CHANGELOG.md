# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - Planned

### Planned
- Cache storage optimization: support compressed scheme artifacts for downloaded
  allele/profile data to reduce disk usage.
- Keep backend typing behavior unchanged while adding compression support
  (indexing/typing should continue to use materialized local files).
- Design provider-specific incremental update strategy to avoid full re-downloads:
  - PubMLST/Pasteur (BigsDB): compare remote metadata and fetch only changed
    loci/profile assets when possible.
  - Enterobase/cgMLST: evaluate available metadata/headers and implement
    best-effort incremental sync.
- Extend `.meta.json` schema to track update metadata needed for incremental
  refresh (for example: timestamps/checksums/ETag-like fields).

### Scope Note
- `0.1.x` remains focused on basic functionality verification and stability.
- The compression + incremental-update work is deferred to `0.2.0`.

## [0.1.3] - 2026-07-16

### Fixed

- **Dead code removed**: nucmer.py unreachable code after `return`, blastn.py wasted binary
  write overwritten by text write, `count_sequences` dead function
- **Provider silent exceptions**: 4 provider/cache sites escalated from `logger.debug` to
  `logger.warning` (bigsdb, enterobase, cache)
- **Exception handling**: 11 `except...: pass`/`suppress()` sites annotated with explanatory
  comments per AGENTS.md guideline; nucmer malformed-line handler now logs skipped lines
- **`novel/reader.py`**: bare `open()` replaced with `open_text()` (fixes `.gz` file support)

### Added

#### Novel Allele Detection & Custom Schemes
- **`gmlst typing --novel-allele`**: Detect and save novel allele sequences to `{locus}_novel.fasta` files
- **`gmlst typing --novel-profile`**: Generate novel ST profiles and save to `profiles_novel.txt`
- **`gmlst scheme create`**: Create custom schemes by merging public databases with novel data
  - Auto-numbering: custom_0, custom_2, ...
  - Based on existing schemes (e.g., saureus_0 → custom_1)
  - Stores metadata in `.meta.json`
- **`gmlst scheme update`**: Add more novel data to existing custom schemes
  - Continues numbering from where it left off (n2, n4... N3, N4...)
- **`gmlst scheme export --format grapetree`**: Export profiles for GrapeTree MST visualization

#### Custom Database Workflow
Complete pipeline for private/laboratory MLST databases:
```bash
# 0. Type samples and keep JSON output
gmlst typing -s saureus_0 --format json sample.fasta -o typing_results.json

# 1. Extract novel alleles/profiles from typing JSON
gmlst utils extract -i typing_results.json --novel-allele --novel-profile --data-dir novel_data/

# 2. Create custom scheme from novel data
gmlst scheme create -t mlst -s saureus_0 --data-dir novel_data/ --desc "Lab collection"

# 3. Update custom scheme with more data
gmlst scheme update-custom -s custom_0 --data-dir more_novel_data/

# 4. Export for GrapeTree analysis
gmlst scheme export -s custom_0 --format grapetree -o mst.tsv
```

#### Novel Sequence Extraction
- BLASTN aligner now extracts actual sequences from alignments
- Novel alleles (good coverage but low identity) capture sample sequence
- Sequences are saved in FASTA format: `>{locus}_n0 sample=isolate_001`

#### Local Provider Support
- Custom schemes use `provider: local`
- Listed in `gmlst scheme list -p local`
- Stored in `~/.cache/gmlst/local/custom_*/`

### Technical Details

#### Data Formats
- **Novel alleles**: `{locus}_n{number}` format (e.g., `dnaN_n0`)
- **Novel profiles**: `N{number}` ST format (e.g., `N0`, `N2`)
- **GrapeTree export**: TSV with `#Strain` header, compatible with MST visualization

#### File Structure
```
~/.cache/gmlst/local/custom_0/
├── {locus}.tfa          # Merged: original + novel alleles
├── custom_0.txt         # Merged: original + novel profiles
└── .meta.json           # Metadata: based_on, description, novel counts
```

### Code Quality Improvements

#### Security
- **Shell injection fix**: `gmlst config set` now uses `shlex.quote()` for config values
- **Credential file permissions**: `~/.config/gmlst/env.sh` is now created with `0600` permissions
- **SSRF gap closed**: `assert_public_url()` added to aria2c batch download path and all
  Enterobase direct `requests.get/head` calls (5 new guard points)
- **`gmlst config init` command**: Auto-adds source line to shell rc file (bash/zsh/fish),
  idempotent, for persistent environment variable loading

#### Test Quality
- **8 fake tests replaced**: `inspect.getsource()` string-matching tests rewritten as real
  behavior tests with mocked network calls (test_provider_errors.py, test_bigsdb_errors.py)
- **Pipeline tests added**: 9 behavior tests for core/pipeline.py orchestration functions
  (previously zero direct test coverage)
- **Aligner parsing tests**: 22 behavior tests for `_parse_coords` (nucmer) and
  `_parse_blast_output` (blastn) — previously completely untested
- **conftest.py created**: Shared test fixtures (DummyScheme, DummyCache, DummyAligner,
  DummySample) eliminating ~30 repeated class definitions
- **Frontend tests**: 27 new tests for mstApi.js, tableExport.js, sessionPersistence.js,
  fileInput.js (43→70 total frontend tests)

#### Code Deduplication
- `utc_now_iso()`: 6 inline copies → 1 shared helper
- `_load_blocked_schemes`: 2 implementations → 1 (common.py delegates to cache.py)
- `_env_int()` helper: 5 near-identical env-var parser functions → 1 helper
- `merge_fasta_files()`: 5 duplicated FASTA merge implementations → 1 shared helper
- Dead code removed: `count_sequences`, nucmer unreachable block, blastn wasted I/O

#### Modularity — God Module Split
- `visual/cli.py`: 995→689 lines (+ `_cli_helpers.py` 123 lines + `_cli_export.py` 210 lines)
- `commands/scheme.py`: 1588→896 lines (+ `scheme_common.py` 184 + `scheme_render.py` 133 + `scheme_custom.py` 423)
- `commands/utils.py`: 1006→365 lines (+ `utils_extract.py` 338 + `utils_benchmark.py` 343)

#### Type Safety
- **pyright errors: 121→0**
- `dict[str, object]` → `dict[str, Any]` across visual/app.py (65 errors fixed)
- `int(int|None)` → explicit None guards in chew_policy.py (12 errors fixed)
- 5 missing function annotations added
- ~27 bare `dict`/`list[dict]` generics annotated with type parameters
- All 7 `# type: ignore` comments now have explanatory notes

#### Error Handling
- 4 provider silent-exception sites escalated from `logger.debug` to `logger.warning`
- 11 `except...: pass`/`suppress()` sites annotated with explanatory comments
- `nucmer.py` malformed-line handler now logs skipped lines

#### Architecture
- **Layering violation fixed**: `ProdigalPredictor` moved from `schemefree/` to `core/`
  (eliminates core→schemefree circular dependency)
- Logger naming standardized to `logging.getLogger(__name__)` across 21 modules
- Schemefree temp directories now use `temp_dir()` (respects GMLST_TMPDIR)
- `print()` → `click.echo()` in benchmark report and output utilities
- Magic numbers extracted to named constants in allele.py, blastn.py, gene_predictor.py,
  assembly_engine.py

#### Documentation
- AGENTS.md module structure tree updated with all new split files
- `docs/en/architecture.md` and `docs/zh/architecture.md` module trees synchronized
- `docs/en/configuration.md` and `docs/zh/configuration.md` updated with `config init` usage
- README.md updated with `config init` workflow
- `dev/code_quality_audit.md` created with full evaluation report
- `dev/remain.md` created tracking deferred items for v0.2.0

## [0.1.2] - 2026-07-08

### Fixed
- **Download concurrency / 429 fix**: Decoupled aria2c `--split` and
  `--max-connection-per-server` from `--max-concurrent-downloads`. Previously a
  default of 8 concurrent files × 8 splits = 64 connections triggered nginx 429
  from PubMLST/Pasteur. Per-server connections are now capped at 2.
- **Partial-file cleanup**: `download_file_requests` and `download_required_files`
  now `unlink` partial/empty files on failure. `download_files_batch` skip logic
  checks `size > 0` instead of just `exists()`, preventing corrupt partial
  downloads from being treated as complete on retry.
- **Lowered default concurrency**: Provider defaults reduced from 8/16 to 4.
  CLI `--connections/-x` default changed from `None` (provider fallback) to `4`.

### Added
- **`gmlst config` command**: New command group (`env`, `show`, `get`, `set`)
  for inspecting and managing 29 environment variables. Writes to
  `~/.config/gmlst/env.sh`.
- **`gmlst scheme search` command**: Search across scheme name, organism,
  description, and provider with a positional PATTERN argument.

### Changed
- **Positional arguments**: `scheme download`, `export`, and `update-custom`
  now accept the scheme name as a positional argument. The `-s` flag is kept as
  a hidden deprecated alias for backward compatibility.
- **Scheme list highlighting**: Downloaded schemes are now shown in **bold**
  and sorted first in the table.

### Frontend
- Added `is_valid_fasta` to `fasta_io.py` for post-download validation.
- `scheme list` hint text updated to positional argument syntax.


## [0.1.1] - 2026-07-07

### Security
- **SSRF protection**: Added `url_guard.py` with private-network IP filtering for all
  outbound HTTP requests (`fetch_json`, `download_file`). Blocks loopback, RFC 1918,
  link-local, and metadata-service endpoints.
- **Path traversal fix**: `DatabaseCache.scheme_dir()` now validates scheme names and
  provider identifiers against a strict whitelist regex. Defense-in-depth check ensures
  `shutil.rmtree` can never operate outside the cache root.
- **Flask CSRF protection**: Added `before_request` Origin/Referer validation on all
  state-changing POST endpoints.
- **Security headers**: Added `Content-Security-Policy`, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` via `after_request`.
- **Flask SECRET_KEY**: Now set via `secrets.token_urlsafe(32)` at app factory time.
- **Docker non-root user**: Container now runs as `$MAMBA_USER` instead of root.
- **Client-side file size guard**: Frontend file inputs enforce 64 MiB limit before
  reading (`readFileWithSizeCheck`).

### Changed
- Split 3 core pipeline functions (301/282/272 lines) into focused phase helpers
  (orchestrators now 48–157 lines).
- Broke partial-initialization cycle in `core/adapters_*.py` — eliminated all 14
  deferred `import gmlst.core as core` statements across 4 adapter modules.
- Replaced `gzip.open`/`open` union pattern with typed `open_text` contextmanager,
  removing 6 `# type: ignore[call-overload]` comments.
- Promoted cross-module private symbols to public: `split_allele_id` → `aligners/base.py`,
  `generate_scheme_base_name` → `database/providers/base.py`.
- Converted 9-branch `elif` organism lookup in `enterobase.py` to ordered tuple table.
- Merged duplicate `_load_organism_mappings` functions and removed duplicate
  `_MAX_RETRIES` constant in `bigsdb.py`.

### Frontend
- Extracted 425 lines of pure functions from `App.vue` into `visualLayout.js` (with
  22 unit tests).
- Extracted file input and export logic into `fileInput.js` and `tableExport.js`.
- Extracted MST API fetch logic into `mstApi.js`.
- Extracted session persistence logic into `sessionPersistence.js`.
- Created 5 presentational Vue components: `EmptyState`, `DistanceMatrix`,
  `CompareTable`, `AlleleHeatmap`, `LegendBar`.
- `App.vue` reduced from 4176 → 3509 lines (−16%).

### Tests
- Added 84 path-traversal security tests (`test_cache_security.py`).
- Added 29 SSRF guard tests (`test_url_guard.py`).
- Added 8 Flask security header/CSRF tests.
- Total: 683 backend + 43 frontend tests, all passing.


## [0.1.0] - 2026-03-13

### Added
- Initial release of gmlst
- Multiple alignment backends: BLASTN, minimap2, nucmer
- Support for FASTA (assembled genomes) and FASTQ (raw reads) inputs
- Multiple database providers: PubMLST, Pasteur, Enterobase
- Batch processing capability
- CLI interface compatible with tseemann/mlst output format
- Configurable identity and coverage thresholds
- Thread support for BLASTN backend
- Caching system for schemes and alignment indexes

### Features
- **blastn**: NCBI BLASTN backend for assembled genomes
- **minimap2**: Fast aligner supporting both FASTA and FASTQ
- **nucmer**: MUMmer4 backend for sensitive distant matches
- **kmerhash**: Pure Python backend with no external dependencies (removed in later release)

[0.1.3]: https://github.com/indexofire/gmlst/releases/tag/v0.1.3
[0.1.2]: https://github.com/indexofire/gmlst/releases/tag/v0.1.2
[0.1.1]: https://github.com/indexofire/gmlst/releases/tag/v0.1.1
[0.1.0]: https://github.com/indexofire/gmlst/releases/tag/v0.1.0
