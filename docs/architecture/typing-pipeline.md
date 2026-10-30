# Typing Pipeline

The end-to-end path from a command to a result: scheme resolution, indexing, prefiltering, alignment, calling, ST lookup, and the FASTA versus FASTQ split.

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

- `fast`
- `ultrafast`
- `balanced`

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

For FASTQ cgMLST, `gmlst/commands/typing.py` forces these mode choices back to `fast`.

## Worked example: one MLST sample

Given `saureus_1` (7 loci) and `sample.fna`, the stages look like this:

| Stage | Input | Output |
| --- | --- | --- |
| Scheme resolution | `saureus_1` | allele FASTA files and profile table in the cache |
| Detection | `sample.fna` | `SampleInput(path=..., input_type="fasta")` |
| Indexing | allele FASTAs | backend index, reused on later runs |
| Alignment | sample + index | `AlleleMatch` per locus |
| Calling | matches | `23`, `~23`, `15?`, or `-` per locus |
| ST lookup | allele profile | `ST = 1`, or `-` when no exact profile exists |
| Rendering | calls | one TSV row |

```text
FILE        SCHEME      ST  arcC  aroE  glpF  gmk  pta  tpi  yqiL
sample.fna  saureus_1   1   1     1     1     1    1    1    1
```

## Pipeline order in code

`run_typing_impl()` is intentionally linear; each step is a call you can test in
isolation:

```python
cache = DatabaseCache(cache_dir)
scheme = cache.ensure_scheme(scheme_name)
aligner = build_aligner(backend)

for sample in samples:
    sample_input = detect_sample(sample)
    index = ensure_index(aligner, scheme, force_reindex)
    result = align_and_call(aligner, sample_input, index, scheme)
    result.st = lookup_st(result.allele_profile, scheme.profiles)
```

The real implementation inserts prefiltering, exact-hash resolution, and
refinement between alignment and ST lookup, but the ordering above is the
contract to preserve when refactoring.

## Stage failure cheat sheet

| Symptom | Likely stage | Where to look |
| --- | --- | --- |
| `Scheme 'X' not found` | scheme resolution | `database/cache.py` |
| All loci missing | detection or index | `readers/sample.py`, `core/indexing.py` |
| Many partial calls | alignment thresholds | `commands/common.py`, `calling/allele.py` |
| Calls present but `ST = -` | ST lookup | `calling/st_lookup.py` |
| Rows missing from output | rendering or `--minscore` | `commands/typing_output.py` |

## Where the FASTA/FASTQ decision is made

The split is decided once, in `commands/typing.py`, and then expressed as
concrete options passed to the pipeline:

```text
FASTA  -> prefilter allowed, exact-hash allowed, minimap2 representative path allowed
FASTQ  -> KMA-first for cgMLST, assembly-grade shortcuts gated off
```

If a new optimisation is assembly-only, gate it on `input_type == "fasta"` at
the same place instead of letting backends guess.
