# Novel and Scheme-free Workflows

How novel alleles become reusable custom schemes, and how the scheme-free `tgmlst` engine is structured.

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

## End-to-end novel allele loop

```bash
# 1. Type with JSON so novel sequences are captured
gmlst typing mlst -s saureus_1 --format json samples/*.fna -o results.json

# 2. Extract novel alleles and profiles
gmlst utils extract -i results.json --novel-allele --novel-profile --data-dir novel

# 3. Inspect what was written
ls novel/
# arcC_novel.fasta  aroE_novel.fasta  profiles_novel.txt

# 4. Build a local scheme
gmlst scheme create -t mlst -s saureus_1 --data-dir novel --desc "Lab 2026"

# 5. Type new samples against it
gmlst typing mlst -s custom_1 new_sample.fna
```

A novel allele record in typing JSON carries the extracted sequence:

```json
{
  "locus": "arcC",
  "call": "~23",
  "identity": 98.7,
  "coverage": 1.0,
  "novel_sequence": "ATG..."
}
```

## Scheme-free typing data flow

```text
reads/assembly
  -> (optional) assembly
  -> gene prediction
  -> gene clustering (mmseqs2, hash fallback)
  -> allele hashing
  -> profile table
  -> optional --save-scheme JSON
```

Reusing a discovered scheme keeps hashes stable across runs:

```bash
gmlst typing tgmlst sample.fna --save-scheme tgmlst_scheme.json
gmlst typing tgmlst other.fna --load-scheme tgmlst_scheme.json --format json
```

## Where each step lives

| Step | Module |
| --- | --- |
| Novel collection during typing | `gmlst/novel/service.py` |
| Sequence and profile writers | `gmlst/novel/writer.py` |
| Custom scheme creation | `gmlst/commands/scheme_custom.py` |
| Gene prediction | `gmlst/core/gene_predictor.py` |
| Clustering | `gmlst/schemefree/cluster_engine.py` |
| Hashing | `gmlst/schemefree/hasher.py` |
| tgmlst orchestration | `gmlst/schemefree/typing_engine.py` |
