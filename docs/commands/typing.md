[← Command Reference](../commands.md)

# gmlst typing

Type FASTA or FASTQ samples with MLST, cgMLST, or scheme-free workflows.

## mlst

Type samples against MLST schemes only.

### Usage
```bash
gmlst typing mlst [OPTIONS] SAMPLES...
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-s, --scheme TEXT` | Scheme name to type against. Required. | - |
| `-b, --backend [blastn\|kma\|minimap2\|nucmer]` | Alignment backend. | `blastn` |
| `--min-id FLOAT` | Minimum percent identity for confident allele calls. | `95.0` |
| `--min-cov FLOAT` | Minimum coverage fraction for confident allele calls. | `0.95` |
| `--min-depth FLOAT` | Minimum depth threshold for depth-aware workflows. | `10.0` |
| `--format [tsv\|json\|pretty]` | Output format. | `tsv` |
| `-o, --output PATH` | Write results to a file instead of stdout. | - |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `--force-reindex` | Rebuild cached indexes before typing. | `False` |
| `--no-header` | Omit the header row in TSV output. | `False` |
| `-t, --threads INTEGER` | Backend thread count. | `1` |
| `--max-workers INTEGER` | Number of samples to process in parallel. | `1` |
| `--count-same-copy` | Report same-allele multicopy events such as `1,1` when supported. | `False` |
| `-q, --quiet` | Reduce console output. | `False` |
| `--novel-allele` | Save novel allele candidates during typing. | `False` |
| `--novel-profile` | Save complete novel profiles. Requires `--novel-allele`. | `False` |
| `--data-dir, --output-dir PATH` | Directory for novel allele and profile outputs. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst typing mlst -s saureus_1 sample.fasta
gmlst typing mlst -s saureus_1 --format json samples/*.fasta -o results.json
gmlst typing mlst -s saureus_1 -b kma reads/sample_R1.fastq.gz reads/sample_R2.fastq.gz
gmlst typing mlst -s saureus_1 --novel-allele --novel-profile --data-dir novel_data sample.fasta
```

### Notes
- `typing mlst` accepts assembled FASTA input and backend-supported FASTQ input.
- Paired FASTQ files are auto-detected when names match common patterns such as `_R1/_R2`, `_1/_2`, or `.1/.2`, including `.fastq`, `.fq`, and `.gz` variants.
- `--novel-allele` saves high-coverage non-public calls for later review. `--novel-profile` adds complete novel profiles and only works together with `--novel-allele`.
- JSON output is the best input for downstream novel extraction with `gmlst utils extract`.

---

## cgmlst

Type samples against cgMLST/wgMLST schemes only.

### Usage
```bash
gmlst typing cgmlst [OPTIONS] SAMPLES...
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-s, --scheme TEXT` | Scheme name to type against. Required. | - |
| `-b, --backend [blastn\|kma\|minimap2\|nucmer]` | Alignment backend. | `minimap2` |
| `--cgmlst-mode [standard\|chew-fast\|chew-ultrafast\|chew-bsr\|chew-balanced]` | Runtime mode for cgMLST FASTA workflows. | `standard` |
| `--min-id FLOAT` | Minimum percent identity for confident allele calls. | `95.0` |
| `--min-cov FLOAT` | Minimum coverage fraction for confident allele calls. | `0.95` |
| `--min-depth FLOAT` | Minimum depth threshold for depth-aware workflows. | `10.0` |
| `--format [tsv\|json\|pretty]` | Output format. | `tsv` |
| `-o, --output PATH` | Write results to a file instead of stdout. | - |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `--force-reindex` | Rebuild cached indexes before typing. | `False` |
| `--no-header` | Omit the header row in TSV output. | `False` |
| `-t, --threads INTEGER` | Backend thread count. | `1` |
| `--max-workers INTEGER` | Number of samples to process in parallel. | `1` |
| `--count-same-copy` | Report same-allele multicopy events such as `1,1` when supported. | `False` |
| `-q, --quiet` | Reduce console output. | `False` |
| `--prefilter-k INTEGER` | K-mer size used by the prefilter. | `31` |
| `--prefilter-top-n INTEGER` | Number of candidate loci to keep during prefiltering. | `20` |
| `--prefilter-min-loci-fraction FLOAT` | Minimum retained locus fraction needed to keep the prefilter active. | `0.3` |
| `--no-prefilter` | Disable prefiltering explicitly. | `False` |
| `--novel-allele` | Save novel allele candidates during typing. | `False` |
| `--novel-profile` | Save complete novel profiles. Requires `--novel-allele`. | `False` |
| `--data-dir, --output-dir PATH` | Directory for novel allele and profile outputs. | - |
| `--cds-coordinates-out PATH` | Export predicted CDS coordinates as TSV. | - |
| `--call-policy [default\|chewbbaca]` | Per-locus reporting policy. | `default` |
| `--chew-cds-gate / --no-chew-cds-gate` | Enable or disable CDS-gated chewBBACA-style classification. | `chew-cds-gate` |
| `-h, --help` | Show the help message and exit. | - |

### cgMLST Modes

| Mode | Description |
| --- | --- |
| `standard` | Conservative baseline. |
| `chew-fast` | Exact-hash + minimap2 prefilter with targeted rescue. |
| `chew-ultrafast` | Aggressive speed profile with bounded second-pass rescue. |
| `chew-bsr` | Protein-level exact-hash on top of `chew-fast`. |
| `chew-balanced` | Hash-first with targeted `blastn` fallback. |

### Examples
```bash
gmlst typing cgmlst -s vparahaemolyticus_3 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --cgmlst-mode chew-fast sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --prefilter-k 31 --prefilter-top-n 20 sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 --call-policy chewbbaca --cds-coordinates-out cds.tsv sample.fna
gmlst typing cgmlst -s vparahaemolyticus_3 -b kma -t 8 reads_R1.fastq.gz reads_R2.fastq.gz
```

### Notes
- `typing cgmlst` is tuned for large locus sets, where the per-locus profile matters more than a compact legacy ST.
- FASTA assemblies use the full cgMLST mode system. FASTQ input follows a KMA-first path. If you request `-b minimap2` with FASTQ files, `gmlst` auto-switches to `-b kma` and treats `--cgmlst-mode` as compatibility-only `standard` behavior.
- `--call-policy chewbbaca` requires FASTA assemblies. Raw calls stay unchanged, while output labels follow chewBBACA-style classes.
- CDS-gated classification is enabled by default for `--call-policy chewbbaca`. Use `--no-chew-cds-gate` only when you want classification from any matched sequence context.
- Prefiltering is most useful for FASTA assembly workflows. For `-b kma` and the default `-b minimap2` path, `gmlst` can skip prefiltering and use its persistent full-index route instead.

### Environment Variables

| Variable | Purpose |
| --- | --- |
| `GMLST_MINIMAP2_FASTA_SPEED_PROFILE` | Select minimap2 FASTA speed profile for cgMLST FASTA runs. |
| `GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI` | Control the rescue budget for the `chew-ultrafast` second pass. |
| `GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS` | Auto-raise KMA threads for cgMLST FASTQ runs when possible. |
| `GMLST_CGMLST_KMA_FASTQ_MEM_MODE` | Toggle KMA `-mem_mode` for cgMLST FASTQ mapping. |
| `GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI` | Limit strict KMA confirmation after the FASTQ mem-mode pass. |
| `GMLST_CGMLST_PREFILTER_MAX_LOCI` | Auto-skip prefiltering above a configured locus count. |
| `GMLST_CGMLST_EXACT_HASH_PREFILTER` | Enable chewBBACA-style DNA exact-hash pre-resolution. |
| `GMLST_CGMLST_MINIMAP2_HASH_PREFILTER` | Enable experimental minimap2 hash-first prefiltering. |
| `GMLST_CGMLST_CDS_PREDICTION_MODE` | Set Pyrodigal CDS prediction mode. |
| `GMLST_CGMLST_CDS_TRAINING_FILE` | Use a fixed Pyrodigal training file. |
| `GMLST_CGMLST_CDS_CLOSED_ENDS` | Control Pyrodigal closed-end CDS prediction behavior. |
| `GMLST_CGMLST_CDS_COORDINATES_OUT` | Export predicted CDS coordinates through an environment override. |
| `GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI` | Limit second-pass minimap2 refinement when no mode override sets it. |
| `GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND` | Pick the targeted low-confidence fallback backend. |
| `GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI` | Limit how many loci go through targeted fallback. |

---

## tgmlst

Run scheme-free typing pipeline (tgMLST).

### Usage
```bash
gmlst typing tgmlst [OPTIONS] SAMPLES...
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `--format [tsv\|json\|pretty]` | Output format. | `tsv` |
| `-o, --output PATH` | Write results to a file instead of stdout. | - |
| `--no-header` | Omit the header row in TSV output. | `False` |
| `-q, --quiet` | Reduce console output. | `False` |
| `--hash-strategy [safe\|fast\|ultra\|strict\|blast]` | Hash and rescue strategy for scheme-free calling. | `safe` |
| `--save-scheme PATH` | Save the discovered scheme for reuse. | - |
| `--load-scheme PATH` | Reuse a previously saved tgMLST scheme. | - |
| `--stats` | Print extra summary statistics. | `False` |
| `--max-workers INTEGER` | Number of samples to process in parallel. | - |
| `-t, --threads INTEGER` | Backend thread count. | - |
| `--assemble-timeout FLOAT` | Timeout for assembly-related steps. | - |
| `--error-report PATH` | Write per-sample errors to a report file. | - |
| `--fail-on-error` | Stop on the first processing error. | `False` |
| `--summary-report PATH` | Write a summary report file. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst typing tgmlst sample.fna
gmlst typing tgmlst --stats sample.fna
gmlst typing tgmlst --save-scheme discovered_scheme.json sample.fna
gmlst typing tgmlst --load-scheme discovered_scheme.json another_sample.fna --format json
```

### Notes
- `tgmlst` is scheme-free. It discovers loci from the data instead of requiring a named public scheme up front.
- `--save-scheme` and `--load-scheme` make the workflow reusable. A common pattern is to discover a scheme on one batch, save it, then load it for later related samples.
- `--format json`, `--summary-report`, and `--error-report` are the best fit when you need structured downstream processing.

---

## Common typing notes

### Output format details

`typing mlst` and `typing cgmlst` use compact allele markers in TSV output.

| Marker | Meaning |
| --- | --- |
| `23` | Exact known allele call. |
| `~23` | Non-exact high-coverage call, usually the closest allele or a novel-style locus represented by the nearest allele ID. |
| `15?` | Partial call with insufficient coverage for a confident full call. |
| `-` | Locus not found. |

JSON output is the best choice when you need structured per-locus metadata, including `novel_sequence` fields for downstream extraction.

### Multicopy loci

- Conflicting multicopy calls can appear as comma-separated values such as `1,2`.
- Same-allele copy counts such as `1,1` are optional and currently exposed through `--count-same-copy`.
- When conflicting multicopy loci are present, `ST` is reported as `-` so the final profile is not overcalled.
- A practical review pattern is a fast first pass, followed by a targeted `blastn` rerun with `--count-same-copy` for flagged samples.
