# Novel Allele Workflow Guide

This guide covers the private MLST workflow in `gmlst`, from novel allele detection during typing to building a reusable custom scheme. For the core command reference, see [commands.md](commands.md). For a shorter getting-started example, see [quickstart.md](quickstart.md).

## Overview

Novel allele detection helps you capture sequences that are close enough to a target locus to be trusted, but too different from the public database to be called as a known allele. That matters when you are working with local collections, outbreak sets, or long-running surveillance projects where your lab sees diversity before it appears in a public scheme.

The workflow has two goals:

1. save novel allele sequences and complete novel profiles from typing output
2. turn those discoveries into a private custom scheme that you can type against later

`gmlst` keeps that workflow CLI-first and file-based, so you can inspect every intermediate artifact and decide when to promote novel data into a reusable local scheme.

## Complete Pipeline

```bash
# 1. Type samples and write machine-readable results
gmlst typing mlst -s saureus_1 --format json *.fasta -o typing_results.json

# 2. Extract novel alleles and complete novel profiles
gmlst utils extract -i typing_results.json --novel-allele --novel-profile \
  --data-dir novel_data/

# 3. Create a private custom scheme from the extracted data
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data/ \
  --desc "Lab collection 2024"

# 4. Add more novel data later
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data/

# 5. Export the custom scheme for MST visualization
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

Typical result layout after the workflow:

```text
novel_data/
├── arcC_novel.fasta
├── glpF_novel.fasta
└── profiles_novel.txt

~/.cache/gmlst/local/custom_1/
├── arcC.tfa
├── aroE.tfa
├── glpF.tfa
├── custom_1.txt
└── .meta.json
```

## Step 1: Typing with Novel Detection

Start by typing your samples against a public MLST scheme and keep the output in JSON. JSON is the preferred input for downstream extraction because it preserves per-locus details, including novel sequence data.

```bash
gmlst typing mlst -s saureus_1 --format json *.fasta -o typing_results.json
```

If you want typing plus extraction-ready flags in one run, use:

```bash
gmlst typing mlst -s saureus_1 --format json \
  --novel-allele --novel-profile \
  --data-dir novel_data/ \
  *.fasta -o typing_results.json
```

Why these flags matter:

- `--novel-allele` saves loci with good coverage but low identity as novel candidates
- `--novel-profile` records complete profiles that include those novel alleles
- `--data-dir` keeps the novel outputs in a dedicated directory instead of mixing them with your typing table

Novel allele detection follows this rule of thumb:

- good coverage, but identity below 95 percent, becomes a novel allele candidate

Representative JSON-style example:

```json
{
  "sample_id": "isolate_042",
  "scheme": "saureus_1",
  "st": null,
  "allele_calls": {
    "arcC": {"allele_id": "1", "call_type": "exact"},
    "aroE": {"allele_id": "7", "call_type": "exact"},
    "glpF": {
      "allele_id": "19",
      "call_type": "novel",
      "novel_sequence": "ATGAAACT..."
    }
  }
}
```

## Step 2: Extracting Novel Data

Once you have typing output, extract the novel alleles and complete novel profiles into a reusable data directory.

### From JSON typing output

```bash
gmlst utils extract -i typing_results.json --novel-allele --novel-profile \
  --data-dir novel_data/
```

Typical output:

```text
Novel alleles written:
  glpF: novel_data/glpF_novel.fasta
  gmk: novel_data/gmk_novel.fasta
Novel profiles written: novel_data/profiles_novel.txt
```

### From TSV typing output

TSV works as a fallback when JSON is not available. In that case, `gmlst` needs the scheme name and access to the original sample FASTA files so it can recover the underlying sequence context.

```bash
gmlst utils extract -i typing_results.tsv -s ecoli_1 \
  --novel-allele --novel-profile \
  --samples-dir ./samples \
  --data-dir novel_data/
```

Use the TSV path when you already have a typing table from an earlier run, but did not save JSON at the time.

### Naming rules

- novel alleles use `{locus}_n{number}`, for example `dnaN_n1`
- novel profiles use `N{number}`, for example `N1`
- allele numbering is per locus, while profile numbering is global within the output set

Important behavior across repeated runs:

- `profiles_novel.txt` is append-safe across runs
- `{locus}_novel.fasta` files are generated fresh per run, so use a new `--data-dir` for each batch or regenerate from a combined JSON file

## Step 3: Creating Custom Schemes

After extraction, build a private scheme that merges the original public database with your new allele and profile data.

```bash
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data/ \
  --desc "Lab collection 2024"
```

Why this step matters:

- it turns ad hoc novel files into a typeable scheme
- it preserves the original public alleles and STs
- it lets later samples match your lab-specific alleles directly

Custom schemes are auto-numbered as `custom_1`, `custom_2`, and so on. They are stored under the `local` provider and show up in the normal scheme list.

```bash
gmlst scheme list -p local
```

Realistic output:

```text
PROVIDER  TYPE  SCHEME     DESCRIPTION
local     mlst  custom_1   Lab collection 2024
```

The resulting scheme directory looks like this:

```text
~/.cache/gmlst/local/custom_1/
├── arcC.tfa
├── aroE.tfa
├── glpF.tfa
├── custom_1.txt
└── .meta.json
```

## Step 4: Updating Custom Schemes

When new isolates produce more novel alleles, update the existing custom scheme instead of creating a fresh one.

```bash
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data/
```

This keeps numbering and metadata continuity in one place. It is the right choice when you are extending the same internal project or surveillance collection.

Typical update pattern:

```bash
# Type the next batch
gmlst typing mlst -s saureus_1 --format json batch2/*.fasta -o batch2.json

# Extract new novel data
gmlst utils extract -i batch2.json --novel-allele --novel-profile \
  --data-dir more_novel_data/

# Merge it into the existing custom scheme
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data/
```

After the update, `custom_1` can be used for typing like any other scheme:

```bash
gmlst typing mlst -s custom_1 new_isolate.fasta
```

## Step 5: Exporting for Visualization

Once your custom scheme contains the profile set you need, export it in GrapeTree-compatible TSV format for MST work.

```bash
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

That output is designed for downstream visualization, including the local web UI described in [visual_guide.md](visual_guide.md).

Representative first lines of the exported file:

```tsv
#Strain	arcC	aroE	glpF	gmk	pta	tpi	yqiL
ST1	1	1	1	1	1	1	1
STN1	n1	7	3	9	4	2	1
```

The first column is a strain label derived from the profile identifier. Known alleles remain numeric, while novel alleles remain in `nX` form in the exported table.

## Allele Extraction

The same `utils extract` command can also pull called alleles directly from a sample FASTA. This is useful when you want a per-sample MLST allele FASTA for inspection, alignment, or downstream analysis.

```bash
gmlst utils extract -i genome.fasta -s ecoli_1 > genome_mlst.fasta
```

To restrict extraction to specific loci:

```bash
gmlst utils extract -i genome.fasta -s ecoli_1 --allele dnaN,tsvA,abcN
```

Realistic output:

```fasta
>dnaN_12 sample=genome
ATGGCTAACAAAGT...
>tsvA_4 sample=genome
ATGCGTATCGGTTA...
>abcN_18 sample=genome
ATGGATTTACCGAA...
```

## Sequence Concatenation

If you want a concatenated allele sequence for phylogenetic or distance-based workflows, use `utils concat` on the extracted FASTA records.

```bash
gmlst utils concat -i genome_mlst.fasta -o genome_mlst_concat.fasta
```

This gives you one combined sequence per sample, which is often easier to pass into tree-building or alignment pipelines.

## File Formats

### Novel allele FASTA

File name pattern:

```text
{locus}_novel.fasta
```

Example:

```fasta
>dnaN_n1 sample=isolate_A1
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG
>dnaN_n2 sample=isolate_B2
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCA
```

### Novel profile file

File name:

```text
profiles_novel.txt
```

Example:

```tsv
ST	sample	dnaN	gyrB	abcZ
N1	isolate_A1	n1	5	12
N2	isolate_B2	n2	5	12
```

### Custom scheme metadata

File name:

```text
.meta.json
```

Representative schema:

```json
{
  "scheme": "custom_1",
  "provider": "local",
  "based_on": "saureus_1",
  "based_on_provider": "pubmlst",
  "scheme_type": "mlst",
  "description": "Lab collection 2024",
  "loci": ["arcC", "aroE", "glpF", "gmk", "pta", "tpi", "yqiL"],
  "novel_alleles": {"arcC": ["n1"], "glpF": ["n1", "n2"]},
  "novel_profiles": ["N1", "N2"],
  "last_allele_number": {"arcC": 1, "glpF": 2}
}
```

The exact metadata can grow over time, but you should expect it to record where the custom scheme came from and how much novel content has been merged.

## Best Practices

- Prefer JSON typing output for novel workflows. It preserves `novel_sequence` and avoids re-typing.
- Keep one `novel_data/` directory per project or batch series, not one giant shared scratch folder.
- If you process multiple batches, keep separate allele extraction directories or rebuild from a combined JSON file, because novel allele FASTA files are not append-safe across runs.
- Add clear `--desc` text when creating a custom scheme so the local catalog stays readable.
- Reuse one custom scheme with `scheme update-custom` when you are extending the same collection.
- Export GrapeTree TSV only after the custom scheme reflects the allele set you want to compare.
- Keep raw typing output, extracted novel data, and final custom schemes together in your project record.

## Troubleshooting

### `--novel-profile` did not produce a profile file

`--novel-profile` depends on `--novel-allele`, and only complete profiles can be written. If a sample has missing or partial loci, it will not become a novel profile.

### My novel allele FASTA files changed between runs

That is expected if you reuse the same `--data-dir` across separate extractions. `profiles_novel.txt` appends safely, but `{locus}_novel.fasta` files are rewritten for each run.

Recommended fix:

```bash
# Keep each batch separate
gmlst utils extract -i batch1.json --novel-allele --novel-profile --data-dir novel_batch1/
gmlst utils extract -i batch2.json --novel-allele --novel-profile --data-dir novel_batch2/
```

### I only have a TSV typing file

Use the TSV fallback path with both `--samples-dir` and `-s/--scheme`:

```bash
gmlst utils extract -i typing_results.tsv -s ecoli_1 \
  --novel-allele --novel-profile \
  --samples-dir ./samples --data-dir novel_data/
```

### `custom_1` does not appear in my normal scheme list

List local schemes explicitly:

```bash
gmlst scheme list -p local
```

Custom schemes belong to the `local` provider.

### I want to compare samples in a tree

Export the custom scheme in GrapeTree format:

```bash
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

Then load that TSV into the visual workflow in [visual_guide.md](visual_guide.md).
