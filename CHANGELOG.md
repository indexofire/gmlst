# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `gmlst config set` wrote env.sh but nothing read it back unless the current
  shell had sourced the file: `config show`/`get` displayed empty values (and
  the `file` provenance in `config get --format json` could never appear),
  while authenticated PubMLST/Pasteur downloads silently ran without the
  configured API keys. The CLI now applies env.sh values into the
  environment at startup for keys not already set — explicit environment
  variables keep winning, and `X-API-Key` headers pick up file-configured
  credentials in unsourced shells.
- FASTQ depth subsampling returned paths into a temporary directory that was
  deleted before the typing run read them — deep Illumina runs (estimated
  depth above `--max-depth`, default 100x) failed with file-not-found.
  Subsampled files now live for the whole process (cleaned up at exit).
- Plasmid MLST schemes (`pmlst_1`..`pmlst_5`) were undownloadable: the
  scheme base "pmlst" is not a substring of any PubMLST database name.
  A seqdef alias resolves them to `pubmlst_plasmid_seqdef` — the audit
  across all 295 PubMLST/Pasteur catalog schemes now resolves 100%.

### Planned
- Cache storage optimization: support compressed scheme artifacts for downloaded
  allele/profile data to reduce disk usage.
- Keep backend typing behavior unchanged while adding compression support
  (indexing/typing should continue to use materialized local files).
- Design provider-specific incremental update strategy to avoid full re-downloads:
  - PubMLST/Pasteur (BigsDb): compare remote metadata and fetch only changed
    loci/profile assets when possible.
  - Enterobase/cgMLST: evaluate available metadata/headers and implement
    best-effort incremental sync.
- Extend `.meta.json` schema to track update metadata needed for incremental
  refresh (for example: timestamps/checksums/ETag-like fields).

## [0.5.1] - 2026-09-25

### Added
- All 54 multi-candidate (organism, type) groups now carry curated scheme
  preferences. Highlights from the display-name review: A. baumannii MLST
  prefers the Pasteur scheme over Oxford; Bacillus cereus cgMLST picks the
  B. cereus scheme (the previous natural-order default resolved to the
  B. anthracis scheme); cgMLST v2 variants, pubmlst mirrors, and
  species-specific schemes are preferred over genus-wide ones.

### Changed
- Fingerprint database grows to 145 organisms (+7: Brachyspira spp.,
  B. cepacia complex, Ca. Liberibacter solanacearum, Cutibacterium acnes,
  Gallibacterium anatis, Glaesserella parasuis, Helicobacter pylori).
  Plasmid MLST is deliberately excluded: plasmid k-mers are shared across
  species and its fingerprint would create false species hits.

### Fixed
- PubMLST seqdef resolution for species grouped under shared REST orgs: a
  pinned database-alias table resolves bcepacia / cacnes / cliberibacter /
  ganatis / gparasuis / hpylori to their true databases regardless of the
  org's arbitrary database list order (cutibacterium lists cavidum before
  pacnes). This also unblocks plain `scheme download` for those schemes.
- Docker release builds retry pip against the PyPI index propagation lag
  and strip the leading ``v`` from release tag names.

## [0.5.0] - 2026-09-25

### Added
- `--guess/-g` on `typing mlst` / `typing cgmlst`: unattended mixed-species
  typing. Every assembly is detected against the fingerprint database, one
  scheme is chosen per organism (curated preference order, then a lone cached
  candidate, then natural order), missing schemes download automatically, and
  the run never prompts. TSV output carries one section per scheme; JSON is a
  single envelope. Samples that cannot be resolved (unidentified species, no
  scheme of the requested type, FASTQ input, failed download) are skipped
  with per-sample reasons; the exit code is 1 only when nothing typed.
- Bare auto-detection now auto-selects the lone cached candidate after a
  unique species detection instead of re-prompting for every genome of the
  same species; interactive candidate lists mark cached schemes.
- Bundled `scheme_preferences.json`: curated scheme order per
  (organism, type) with organism aliases. E. coli MLST ships curated
  (Achtman 7-gene via pubmlst first, the enterobase mirror as fallback,
  Pasteur 8-locus last) and unifies the three historical E. coli organism
  keys. Fingerprint building and `--guess` both consume it.

### Changed
- Fingerprint building merges alias groups (one E. coli entry instead of
  three near-duplicates that deadlocked detection in ambiguity) and prefers
  classic (≥6-locus) MLST sources over the 2-5 locus partial schemes the
  rebuilt Pasteur catalog types as `mlst`. The bundled database was rebuilt
  from the canonical catalogs (140 organisms; the dead `escherichia_20`
  source reference is gone).
- `-s` provider resolution is mode-aware: `typing cgmlst -s <name>` resolves
  to the cgMLST-typed catalog entry when a differently-typed same-name
  scheme exists or is downloaded (the abaumannii_1 case).
- Detection-quality gate remains the existing margin rule; calibration on
  real collections showed absolute scores are species-dependent
  (B. pertussis ≈0.99 vs V. cholerae ≈0.06-0.38 for correct matches), so no
  additional absolute-score threshold was added.

## [0.4.0] - 2026-09-24

### Added
- Pipeline integration docs and examples: Docker usage (persistent scheme
  cache, batch parallelism), a minimal Nextflow process, and a Snakemake
  rule set under `examples/pipelines/`; see the new
  `docs/en/pipelines.md` / `docs/zh/pipelines.md`.
- ONT (nanopore) guidance in the backend docs, based on measured validation
  against matched hybrid assemblies: classic 7-gene MLST calls 5-6/7 loci
  exactly from Q20+ reads, single-locus flips are methylation-motif basecall
  errors, KMA `-bcNano` was evaluated and changed nothing on Q20+ pairs
  (so it is not enabled), and assembly-first typing is recommended for
  definitive ST calls.

### Fixed
- Docker image: alignment backends were missing from the runtime `PATH`
  (`blastn`, `minimap2`, `nucmer`, `kma` not found by gmlst inside the
  published image); `/opt/conda/bin` is now on `PATH`, `kmc` is included,
  the `GMLST_VERSION` build argument is actually honored (it was silently
  ignored), and the build smoke-tests `gmlst`, `blastn`, `minimap2`, and
  `kma` before pushing. Verified end-to-end: typing inside the container
  matches host output.

## [0.3.5] - 2026-09-24

### Added
- Per-sample quality scoring for `typing mlst` / `typing cgmlst`: every JSON
  result now carries `score` (0-100, mean of per-locus scores — exact calls
  are 100, novel/partial calls scale with the caller's existing confidence,
  missing and conflicting multi-copy loci are 0) and `status` (PERFECT /
  NOVEL / MIXED / MISSING / BAD / NONE, tseemann/mlst-style semantics).
- `--minscore <float>`: drop samples below a quality threshold from TSV and
  JSON output alike (default 0 keeps everything; scores are additive fields,
  the JSON envelope stays `gmlst-typing-v1`).

## [0.3.4] - 2026-09-24

### Added
- GenBank/EMBL flat-file input for all typing commands (`typing mlst`,
  `typing cgmlst`, `typing tgmlst`) and the `utils extract` TSV fallback:
  `.gbk`, `.gb`, `.gbff`, and `.embl` files (optionally gzipped) are converted
  to FASTA automatically in a temporary directory. Pure-Python parser, no new
  dependencies; validated allele-identical against equivalent FASTA input on
  real genomes.

### Fixed
- `open_text` (the shared text I/O helper) raised `AttributeError` when called
  with a `str` path instead of `pathlib.Path`; it now accepts both.

## [0.3.3] - 2026-09-23

### Changed
- Species fingerprints now use MLST schemes exclusively (7 housekeeping genes
  per species). cgMLST sources are excluded: they take minutes to download vs
  seconds for MLST and offer no better species-level discrimination. Build
  time drops from 30+ minutes to ~2 minutes.
- Fingerprint database stored as zlib-compressed JSON (~415 KB for 144
  species vs 80 MB uncompressed). A pre-built copy ships with the package
  at  with fallback lookup:
  user-built cache, then bundled copy, then interactive build prompt.
- Per-species fingerprint hash cap of 5,000 for uniform database size.

### Added
- : design rationale, coverage list,
  technical parameters, and regeneration instructions.

## [0.3.2] - 2026-09-22

### Added
- Species auto-detection for `typing mlst` / `typing cgmlst`: omit `-s` and
  gmlst identifies the organism from the genome via a local k-mer fingerprint
  database, resolves the matching scheme for the command's scheme type,
  downloads it, and types — with the selection and confidence reported on
  stderr. Ambiguous detections or multiple candidate schemes fall back to an
  interactive numbered selection (non-interactive: candidate list + exit 2).
- `-n/--organism` on `typing mlst` / `typing cgmlst`: resolve the scheme by
  organism or scheme-name substring; a unique match auto-selects, multiple
  matches print the candidate table and exit 2. Mutually exclusive with `-s`.
- `gmlst scheme update-fingerprints`: builds the species fingerprint database
  (one small MLST scheme per unique catalog organism, sketched; per-organism
  `--organisms` filter for partial builds). `typing` offers to build it
  interactively when missing.

### Changed
- `-s/--scheme` on `typing mlst` / `typing cgmlst` is now optional (omission
  triggers species auto-detection; FASTQ-only input instead asks for `-s` or
  `-n`).

## [0.3.1] - 2026-09-17

### Fixed
- Loci split across more than two contigs no longer fall back to "missing":
  joint fragment evidence now supports the partial call even when every
  single fragment is below the single-match rescue gate.
- A fully contained middle fragment no longer breaks three-fragment chain
  reconstruction; chaining now tests overlap against the running union.
- Novel-ST collection guards are now identical across all four collection
  paths (live typing, JSON extraction, TSV re-typing, plain TSV): profiles
  with a resolved ST, incomplete profiles, or conflicting multicopy loci
  are skipped everywhere. JSON extraction previously only checked the ST.
- Plain-TSV novel extraction now normalizes rendered allele values
  (`23*` multicopy marker, `--detail` position suffixes) instead of
  writing them into profiles_novel.txt.
- `scheme search` accepts `-p local` and the full scheme-type list
  (`rmlst`, `other`), matching `scheme list`.
- `--min-join-overlap` is honored in refinement re-call paths instead of
  silently reverting to the default.
- Fragment evidence is preserved when merging exact-hash matches into the
  alignment result, and through refinement recompute paths.
- blastn fragment allele coordinates are defensively normalized.

### Performance
- Scheme loading is memoized per process (allele sequences, exact-hash
  index, profile tables): worker-mode batch typing no longer re-parses the
  profile TSV and allele FASTAs for every sample (measured: profile reload
  1.14 s -> 0.018 s; ~1.5 s redundant work per sample removed).
- `load_scheme` uses set membership for loci discovery instead of an
  O(n^2) list scan; alignment parsers drop dead allocations and defer
  minimap2 fragment sequence slicing to post-cap.
- tgmlst JSON output no longer round-trips through a serialize-parse
  cycle.

### Changed
- Shared aligner helpers (fragment capping, best-hit selection, result
  assembly) live in `gmlst/aligners/base.py`; typing CLI option groups are
  built from shared factories, removing ~90 lines of duplicated option
  declarations. Behavior is locked by golden parser fixtures and CLI help
  snapshots.

### Removed
- Dead code found by a project-wide scan: the unused
  `gmlst/calling/confidence.py` module, the unused `exit_with_error`
  helper, and the write-only legacy `dna_hash_index.pkl` double-write.

## [0.3.0] - 2026-09-17

### Added
- Split-gene fragment joining for `typing mlst`/`cgmlst` with the `blastn` and
  `minimap2` backends: when a locus has no single valid call because the gene
  is broken across assembly contigs, per-contig fragment alignments are joined.
  Contigs overlapping inside the gene with agreeing sequence are tiled into one
  reconstructed alignment that can be called exactly; disjoint contigs never
  yield an exact call (a junction indel is invisible) but the partial call
  reports the combined coverage of all fragments.
- `--min-join-overlap INTEGER` on `typing mlst`/`cgmlst`: minimum
  allele-coordinate overlap (bp) required to join fragments (default 10,
  `0` = most permissive; overlap sequence must still agree exactly).
- Typing JSON now lists per-fragment evidence (`contig`, `allele_start`,
  `allele_end`) and the combined coverage for loci informed by joint evidence.

### Fixed
- `--novel-profile` no longer records profiles that the scheme already knows:
  collection now skips samples whose ST resolved (and incomplete or conflicting
  profiles), so `profiles_novel.txt` only contains genuine novel ST candidates.

### Changed
- Documentation: batch-typing performance guidance now recommends
  `--max-workers` (measured on 639 assemblies: minimap2 55 s → 9 s, blastn
  97 s → 31 s, nucmer 270 s → 76 s, kma 330 s → 48 s with 16 workers) and
  corrects the earlier claim that KMA benefits from `-t` on assemblies.

## [0.2.1] - 2026-09-17

### Fixed
- `typing tgmlst` de novo locus numbering is now deterministic: two runs on
  identical input produce byte-identical profiles. Parallel sample processing
  no longer orders genes by completion time, and locus IDs are assigned by a
  canonical cluster key instead of the order mmseqs emits cluster lines.
- `typing tgmlst --load-scheme` was a no-op for typing results (scheme data was
  never consulted); saved schemes now store per-allele sequence hashes plus one
  representative sequence per locus, and load-mode anchors genes to scheme loci
  with allele-ID reuse for byte-identical alleles and continued numbering for
  novel alleles/loci. Legacy scheme files still load, with a warning that
  locus anchoring is disabled until re-export.
- Load-mode typing pins a gene to its scheme locus directly when its sequence
  hash matches a scheme allele exactly, so borderline cluster assignments
  between paralogous loci cannot displace byte-identical matches. Verified on
  real genomes: re-typing a scheme-building sample reproduces its de novo
  profile at 99.98% (5010/5011 loci; the single residual is a shadowed
  paralog whose sequence is not part of the scheme).

### Added
- `typing tgmlst --stats` now reports `scheme_loci_anchored` and `novel_loci`
  when typing against a loaded scheme.

## [0.2.0] - 2026-09-16

The AI-agent friendliness release. JSON output is versioned, stdout carries
data only, and exit codes are stable and machine-checkable, so scripts and
AI agents can drive the CLI programmatically without parsing human-oriented
chatter.

### Added

#### `scheme remove`
- New command: `gmlst scheme remove <SCHEME>` deletes a downloaded scheme from
  the local cache
- Confirmation prompt before deletion; `--yes` (`-y`) skips it
  (same flag as `scheme update -a`)
- `-p/--provider` override (auto-detected from the cache by default)
- `--format text|json` completion summary; the JSON form reports
  `{"scheme", "provider", "path", "removed": true}` in a `gmlst-scheme-op-v1`
  envelope
- For `custom_N` schemes the local-catalog entry is removed as well

#### JSON summaries for scheme write operations
- `scheme download`, `scheme update`, `scheme create`, and
  `scheme update-custom` accept `--format json` completion summaries
  (envelope `gmlst-scheme-op-v1`):
  - download: `{scheme, provider, scheme_type, path, n_loci}`
  - update single scheme: `{scheme, provider, changed}`
  - `update -a`: `{total, updated, unchanged, failed, results: [{scheme,
    provider, status, error}]}`
  - create: includes the generated `custom_N` scheme name
  - update-custom: `{scheme, new_alleles_added}`

#### `scheme update -a` confirmation
- Updating all cached schemes now shows an interactive Y/N confirmation that
  lists the cached schemes first
- `--yes` (`-y`) skips the prompt for non-interactive use

#### `scheme search --format`
- `scheme search` now supports `text|table|csv|tsv|json` (previously table-only),
  matching `scheme list`

#### Result truncation control
- `scheme list` and `scheme search` accept `--limit N` to cap the number of
  schemes shown; a truncation note is printed on stderr
- `scheme list --pager` is documented as interactive-only (requires a terminal)

#### `config get --format json`
- Emits an enveloped snapshot (`gmlst-config-get-v1`) with `{name, value,
  source, is_default}`
- `source` reports provenance: `file` when the value matches an export in the
  `env.sh` config file, `env` when set any other way, `default` when unset

#### Visual commands accept stdin
- `visual mst`, `matrix`, `heatmap`, and `locus-diff` read profiles from stdin
  with `--input -`
- `visual compare` reads either side from stdin with `--left -` / `--right -`
- Enables piping, for example:
  `gmlst typing cgmlst -s vparahaemolyticus_3 *.fna --format tsv | gmlst visual mst --input - --format summary`

#### MST summary provenance
- `visual mst --format summary` now includes a provenance block: `method`,
  `include_missing`, `aggregate_profiles`, `cluster_edge_threshold` (15),
  `outlier_weight` (50), `cluster_count`, `unclustered_samples`, `truncated`

### Changed

#### JSON output envelopes (BREAKING)
- Every JSON document written to stdout or an output file is now wrapped as
  `{"schema_version": "<constant>", "data": <payload>}` so programs can
  version-check a payload before parsing it
- Constants live in `gmlst/schema_versions.py`: `gmlst-typing-v1`,
  `gmlst-tgmlst-profiles-v1`, `gmlst-tgmlst-stats-v1`, `gmlst-scheme-list-v1`,
  `gmlst-scheme-show-v1`, `gmlst-scheme-op-v1`, `gmlst-benchmark-v1`,
  `gmlst-visual-mst-v1`, `gmlst-visual-mst-summary-v1`, `gmlst-visual-matrix-v1`,
  `gmlst-visual-heatmap-v1`, `gmlst-visual-compare-v1`,
  `gmlst-visual-locus-diff-v1`, `gmlst-config-get-v1`
- TSV/CSV/text output is unchanged and not enveloped
- `utils extract -i <typing json>` still accepts the legacy bare list emitted
  by older gmlst versions

#### Stream discipline (BREAKING for parsers)
- stdout now carries data only
- Warnings, progress bars, spinners, and "Results written to" notices moved to
  stderr
- `typing tgmlst --stats` prints its stats JSON document to stderr
  (`gmlst-tgmlst-stats-v1`), keeping stdout data-only

#### Exit codes (BREAKING)
- 0: success, including partial tgmlst failures without `--fail-on-error`
- 1: runtime failure
- 2: usage error, including an invalid regex in `scheme list --name`
- 3/4/5/6: tgmlst stage failure for input/assembly/prediction/unknown
  (shifted from the previous 2-5 range to avoid colliding with click's
  usage-error exit 2)
- `scheme update` now exits 1 when any provider or scheme update fails
  (previously exited 0)

#### Deterministic `scheme show --format json`
- Volatile fields (`scheme_dir`, `downloaded_at`, `updated_at`) are stripped
  from the JSON payload so repeated runs produce identical output; other
  formats are unchanged

#### Secret masking in `config show`
- Values of secret-looking variables (`*_API_KEY`, tokens, secrets, passwords)
  are masked as `first4****last4` (fully masked when short); unset secrets are
  not masked

#### Network error reporting
- Downloads emit concise retry lines on stderr, for example
  `retry 1/3 [connection timeout] bigsdb.pasteur.fr — adk`
- Final failures are prefixed with `[network:<reason>]` for reliable grepping

#### MST default method
- Default MST method is now `grapetree_classic` (previously `grapetree_v2`)

#### Web UI redesign
- Refreshed visual web app built on design tokens with dark mode support
- Added PNG export, multi-select sample compare, run statistics view, and a
  timeline view

### Fixed

- **MST correctness**: `grapetree_v2` no longer produces an incorrect
  super-root in tree construction
- **Flask visual API**: HTTP-level 404/405/413 errors now return JSON bodies
  instead of HTML error pages; export schema version string unified to
  `gmlst-visual-export-v1`
- **`-v/--verbose` help text**: now correctly states it enables INFO-level
  logging
- **WCAG contrast**: fixed contrast ratios in the web UI to meet accessibility
  guidelines

### Performance

- **cgMLST overhaul**: default `typing cgmlst` runs about 5x faster
- **`scheme update`**: fail-fast error handling and parallel locus counting
- **`grapetree_v2` backend**: about 44% faster MST computation

### Security

- Additional SSRF and path-traversal defenses beyond the 0.1.1 hardening
- Visual web app validates the HTTP `Host` header against a local allowlist
  (`127.0.0.1`, `localhost`, `[::1]`) to defend against DNS rebinding

### Removed

- Dead legacy CLI code paths

## [0.1.5] - 2026-07-22

### Changed

#### cgMLST: Mode rename and simplification
- Removed `standard` mode (baseline without hash acceleration)
- Renamed modes for clarity:
  - `chew-fast` → `fast` (new default)
  - `chew-ultrafast` → `ultrafast`
  - `chew-balanced` → `balanced`
- 3 cgMLST modes remain: `fast`, `ultrafast`, `balanced`
- All documentation, examples, and tests updated to use new names

## [0.1.4] - 2026-07-21

### Added

#### cgMLST: `--call-policy chew-exact`
- New call policy that forces Prodigal single mode + CDS gate + chewBBACA-style classification
- Produces all chewBBACA-compatible labels: EXC, INF-N, LNF, NIPH, NIPHEM, LOTSC, PLOT3, PLOT5, ASM, ALM
- Designed for maximum compatibility with chewBBACA databases

#### Benchmark script (`scripts/cgmlst_benchmark.py`)
- Automated gmlst vs chewBBACA comparison with BLAST verification
- Verdict system: gmlst_correct, chew_correct, cds_boundary_diff, NIPH verified/unverified
- Length-based allele evaluation (which allele is longer / substring relationship)
- Multi-copy (NIPH) BLAST verification
- Runtime comparison with speedup calculation

### Changed

#### cgMLST: Removed protein hash pre-resolution
- `chew-bsr` cgMLST mode removed (was the only consumer of protein hash)
- Protein hash index, translation, and CODON_TABLE code removed from `exact_hash.py`
- DNA hash matching retained as the sole pre-resolution mechanism
- 4 cgMLST modes remain: standard, chew-fast, chew-ultrafast, chew-balanced

#### cgMLST: Call policy is now orthogonal to mode
- `--cgmlst-mode` (speed/alignment strategy) and `--call-policy` (output format/classification) can be combined freely
- `--call-policy chewbbaca --no-chew-cds-gate` for format conversion without CDS gate
- `--call-policy chew-exact` for full chewBBACA-compatible behavior

### Documentation
- `dev/cgmlst_modes.md` updated with call policy section, classification type table, benchmark usage
- `dev/cgmlst_diff_analysis.md` created with gmlst vs chewBBACA difference analysis report
- `docs/en/cgmlst_guide.md` and `docs/zh/cgmlst_guide.md` updated with chew-exact policy section

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

### cgMLST Improvements

#### New: `--call-policy chew-exact`
- Forces Prodigal single mode + CDS gate + chewBBACA-style classification
- Produces all chewBBACA-compatible labels: EXC, INF-N, LNF, NIPH, NIPHEM, LOTSC, PLOT3, PLOT5, ASM, ALM
- Use case: maximum compatibility with chewBBACA databases

#### Removed: protein hash pre-resolution
- `chew-bsr` cgMLST mode removed (was the only consumer of protein hash)
- Protein hash index, translation, and CODON_TABLE code removed from `exact_hash.py`
- DNA hash matching retained as the sole pre-resolution mechanism

#### Benchmark script (`scripts/cgmlst_benchmark.py`)
- Automated gmlst vs chewBBACA comparison with BLAST verification
- Verdict system: gmlst_correct, chew_correct, cds_boundary_diff, NIPH verified/unverified
- Length-based allele evaluation (which allele is longer / substring relationship)
- Multi-copy (NIPH) BLAST verification
- Runtime comparison with speedup calculation

#### Documentation
- AGENTS.md module structure tree updated with all new split files
- `docs/en/architecture.md` and `docs/zh/architecture.md` module trees synchronized
- `docs/en/configuration.md` and `docs/zh/configuration.md` updated with `config init` usage
- README.md updated with `config init` workflow
- `dev/code_quality_audit.md` created with full evaluation report
- `dev/cgmlst_modes.md` updated with call policy section and benchmark usage
- `dev/cgmlst_diff_analysis.md` created with gmlst vs chewBBACA difference analysis
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
