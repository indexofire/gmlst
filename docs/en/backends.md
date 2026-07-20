# Backend Comparison Guide

`gmlst` supports multiple alignment backends because MLST and cgMLST workloads are not all the same. Some runs need maximum confidence on assembled genomes, some need direct FASTQ support, and some need the fastest possible throughput on very large schemes. The best backend depends on your input type, scheme size, and whether you are optimizing for sensitivity, speed, or read mapping behavior.

In short, use `blastn` for classic MLST on assemblies, `kma` for FASTQ typing, `minimap2` for very fast FASTA cgMLST, and `nucmer` for divergent organisms.

## Backend Comparison Table

| Name | Input Types | Speed | Sensitivity | Best For | External Tool |
| --- | --- | --- | --- | --- | --- |
| `blastn` | FASTA | Moderate | Highest | Reference MLST, validation, assembled genomes | `blastn`, `makeblastdb` |
| `kma` | FASTA, FASTQ | Fast | High | FASTQ typing, routine MLST, cgMLST with reads | `kma` |
| `minimap2` | FASTA | Very fast | High | Large cgMLST schemes, high throughput FASTA typing | `minimap2` |
| `nucmer` | FASTA | Moderate | Very high on divergent matches | Distant organisms, sensitive cross-species matching | `nucmer`, `show-coords` |

## How to Choose

| Scenario | Recommended Backend | Why |
| --- | --- | --- |
| Small or routine MLST on assembled genomes | `blastn` | Highest confidence, simple behavior, familiar gold-standard path |
| FASTQ MLST or FASTQ cgMLST | `kma` | Direct paired-end support, read mapping workflow, strong routine behavior |
| Very large cgMLST on FASTA assemblies | `minimap2` | Fastest mainline path, multiple speed profiles, prefilter support |
| FASTQ typing with fast candidate generation and targeted validation | `minimap2` | Two-stage FASTQ path balances speed and confirmation |
| Divergent alleles or non-standard organisms | `nucmer` | Sensitive for distant sequence matches |
| Result confirmation after a fast pass | `blastn` | Useful as a slower second pass on flagged samples |

## BLASTN (`blastn`)

`blastn` is the conservative reference backend for assembled genomes. It only accepts FASTA input and uses the BLAST+ database workflow, so it is usually the easiest backend to trust when you want a validation run or a final comparison point.

### When to use

- Reference MLST on assembled genomes
- Validation after a fast screening pass
- Cases where you prefer sensitivity over raw speed
- Samples with borderline allele calls that need a familiar alignment path

### Example commands

```bash
# Standard MLST on an assembly
gmlst typing mlst -s saureus_1 -b blastn sample.fasta

# Batch typing with multiple threads
gmlst typing mlst -s saureus_1 -b blastn -t 8 samples/*.fasta -o results.tsv

# Targeted cgMLST re-check on a flagged assembly
gmlst typing cgmlst -s vparahaemolyticus_3 -b blastn flagged_sample.fasta
```

### Notes

- Input type: FASTA only
- Index builder: `makeblastdb`
- Threading: supported with `-t/--threads`
- Best role: highest-confidence typing on assemblies

### Performance tips

- Use `-t` for larger runs. BLASTN benefits from multiple threads.
- Prefer batch execution with `-o` to keep output handling simple.
- For large cgMLST schemes, BLASTN is often better as a fallback or review pass than as the first pass on every sample.

## KMA (`kma`)

`kma` is the strongest general-purpose backend for FASTQ typing. It supports both FASTA and FASTQ, but it is especially valuable for direct read mapping, paired-end workflows, and routine cgMLST from reads.

### When to use

- FASTQ MLST or cgMLST
- Paired-end read sets that you want to type directly
- Routine production workflows where speed and stable read mapping matter
- cgMLST runs where KMA behavior is preferred over minimap2 candidate scoring

### Example commands

```bash
# MLST from paired-end reads
gmlst typing mlst -s saureus_1 -b kma reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz

# cgMLST from FASTQ reads
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 8 reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz

# FASTA typing with KMA
gmlst typing mlst -s saureus_1 -b kma sample.fasta
```

### FASTQ behavior

- `gmlst` auto-detects common paired-end naming patterns such as `_R1/_R2`, `_1/_2`, and `.1/.2`.
- For FASTQ cgMLST, the CLI can auto-raise KMA threads with `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS` when the run would otherwise stay on one thread.
- `GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1` enables KMA `-mem_mode` for faster read mapping.
- `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI` controls a strict re-check stage for a limited number of `closest` loci after the fast `-mem_mode` pass.

### Notes

- Input type: FASTA and FASTQ
- Index builder: KMA index
- Threading: supported with `-t/--threads`
- Best role: preferred backend for FASTQ cgMLST and routine read-based typing

### Performance tips

- For cgMLST, avoid `-t 1` on large schemes. The CLI even warns that one-thread KMA can be very slow.
- If you want fast routine FASTQ typing, keep `GMLST_CGMLST_KMA_FASTQ_MEM_MODE=1`.
- If exact recovery matters more than speed, increase the strict re-check budget with `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI`.

## minimap2 (`minimap2`)

`minimap2` is the high-throughput backend for large cgMLST workloads. It supports both FASTA and FASTQ, but the internal path differs by input type.

For FASTA assemblies, `gmlst` uses a fast allele-to-genome path with optional exact-hash pre-resolution, representative prefiltering, adaptive rescue, and speed profiles. For FASTQ reads, `gmlst` uses a two-stage workflow: candidate generation first, then targeted remapping validation on uncertain loci.

### When to use

- Large cgMLST on FASTA assemblies
- High-throughput batch typing
- FASTQ typing where you want fast shortlist generation plus targeted confirmation
- chewBBACA-style cgMLST workflows on FASTA assemblies

### Example commands

```bash
# Default cgMLST on FASTA, minimap2 is the default backend here
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fasta

# Explicit minimap2 backend with a chew-compatible mode
gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 --cgmlst-mode chew-fast sample.fasta

# FASTQ typing with minimap2 candidate generation and targeted validation
gmlst typing mlst -s saureus_1 -b minimap2 reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz

# Ultrafast large-scale cgMLST tuning
GMLST_MINIMAP2_FASTA_SPEED_PROFILE=ultrafast \
gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 --cgmlst-mode chew-ultrafast samples/*.fasta -o cgmlst.tsv
```

### FASTA path

The FASTA path is where most minimap2 cgMLST acceleration lives.

- `GMLST_MINIMAP2_FASTA_SPEED_PROFILE=default|fast|ultrafast` tunes minimap2 seeding and chaining behavior.
- `GMLST_CGMLST_EXACT_HASH_PREFILTER=1` enables DNA exact-match pre-resolution before alignment.
- `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER=1` enables hash-first candidate reduction.
- `GMLST_CGMLST_PREFILTER_MAX_LOCI` skips prefiltering automatically when the scheme is too large for the configured threshold.
- `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI` adds targeted missing-locus refinement.
- `GMLST_CGMLST_MINIMAP2_HASH_LOCI_TOP_N` limits how many loci are carried forward from the hash stage.
- `GMLST_CGMLST_MINIMAP2_REPRESENTATIVE_MAIN_ALIGNMENT=1` uses representative-only main alignment, useful in ultrafast-style workflows.
- `GMLST_MINIMAP2_FASTA_EMIT_CIGAR=0` disables FASTA CIGAR emission, which can help speed in representative-focused workflows.

### FASTQ path

The FASTQ path has two stages.

1. Candidate generation from read mappings and k-mer support scoring.
2. Targeted remapping validation on uncertain loci before final allele calls.

Related knobs:

- `auto` prefers KMC when available and otherwise falls back to the built-in Python scorer.
- When `samtools` is installed, targeted validation can write BAM temp files.
- `GMLST_TMPDIR` controls where temporary files are created.

### chewBBACA-compatible cgMLST modes

`typing cgmlst` supports the following mode values:

| Mode | Typical role |
| --- | --- |
| `standard` | Conservative default behavior |
| `chew-fast` | Faster chew-style pipeline with exact-hash, hash prefilter, refinement, and fallback |
| `chew-ultrafast` | Most aggressive FASTA-oriented throughput mode with representative alignment and second-pass rescue |
| `chew-balanced` | Middle ground between speed and confirmation |

Important: these chew-style optimizations are FASTA-oriented. For FASTQ inputs, `typing cgmlst` auto-switches `-b minimap2` to `-b kma`, and `--cgmlst-mode` becomes compatibility-only behavior.

### Evidence fallback

Low-confidence loci can be sent to a targeted fallback backend.

- `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=none|blastn|kma|nucmer`
- `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI=<int>`

This is useful when you want minimap2 to handle the main throughput path but still want a limited second opinion on uncertain loci.

## MUMmer4 / nucmer (`nucmer`)

`nucmer` is the sensitive backend for FASTA assemblies when sequence divergence is a concern. It is a good fit for non-standard organisms, cross-species comparisons, and cases where allele matches may be more distant than usual MLST work.

### When to use

- Distant or divergent assemblies
- Non-standard organisms or exploratory work
- Cross-species comparison where exact reference behavior matters less than sensitive matching

### Example commands

```bash
# Sensitive MLST on a divergent assembly
gmlst typing mlst -s saureus_1 -b nucmer sample.fasta

# cgMLST review on a difficult assembly
gmlst typing cgmlst -s vparahaemolyticus_3 -b nucmer flagged_sample.fasta
```

### Notes

- Input type: FASTA only
- Index builder: nucmer reference index workflow
- Threading: limited compared with BLASTN and KMA, `gmlst` warns that thread settings may be ignored
- Best role: sensitive fallback for divergent sequences

## Backend Selection Guide

### Quick decision table

| If you have... | Choose... | Reason |
| --- | --- | --- |
| Assembled genomes, final reference calls | `blastn` | Highest-confidence classic path |
| Paired-end FASTQ reads | `kma` | Direct read mapping and strong routine behavior |
| Thousands of cgMLST loci on FASTA | `minimap2` | Best throughput and acceleration features |
| Divergent assemblies | `nucmer` | Sensitive matching for distant alleles |
| Fast screening, then selective confirmation | `minimap2` or `kma`, then `blastn` | Good speed first, slower validation second |

### Simple decision tree

1. Are your inputs FASTQ reads?
   - Yes: start with `kma`.
   - If you specifically want minimap2 FASTQ validation behavior, use `minimap2` for MLST. For cgMLST FASTQ, the CLI will still normalize toward KMA.
2. Are your inputs FASTA assemblies?
   - If you want the fastest large cgMLST path, use `minimap2`.
   - If you want a conservative reference path, use `blastn`.
   - If the organism or allele space looks more divergent than usual, try `nucmer`.

## Performance Tips

- Use `-t/--threads` on BLASTN, KMA, and minimap2 runs that process large schemes or batches.
- Use `--max-workers` for sample-level parallelism when typing many samples.
- For large cgMLST on FASTA, start with `minimap2` and only fall back on flagged loci or flagged samples.
- For FASTQ cgMLST with KMA, avoid single-thread runs unless you are debugging.
- Keep output on disk with `-o` during large runs instead of printing everything to the terminal.
- Reuse cached schemes and indexes for repeat typing. The first run pays the indexing cost, later runs are cheaper.
- If temporary storage is slow or cramped, move temp files with `GMLST_TMPDIR`.

## FASTQ-specific Notes

### Paired-end auto detection

`gmlst` auto-detects paired FASTQ files by common naming patterns:

- `sample_R1.fastq.gz` + `sample_R2.fastq.gz`
- `sample_1.fq.gz` + `sample_2.fq.gz`
- `sample.1.fastq.gz` + `sample.2.fastq.gz`

Example:

```bash
gmlst typing mlst -s saureus_1 -b kma reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
```

### k-mer support scoring


- `python`, built-in scorer
- `kmc`, KMC/KMC tools
- `auto`, prefer KMC when installed, otherwise use Python

### Targeted validation

minimap2 FASTQ mode is not just a single mapping pass. It builds candidate alleles, scores them, then remaps uncertain loci in a targeted validation stage. That makes it a good choice when you want speed without giving up all post-filter confirmation.

## Related call types

Backend choice changes how evidence is collected, but per-locus calls still end up in the same five categories:

| Call type | Rule |
| --- | --- |
| `exact` | identity `100%`, coverage `>= 1.0` |
| `closest` | identity `>= 95%`, coverage `>= 0.95` |
| `novel` | coverage `>= 0.95`, identity `< 95%` |
| `partial` | coverage `> 0` and `< 0.95` |
| `missing` | no match |
