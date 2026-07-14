[← Command Reference](../commands.md)

# gmlst utils

Run extraction, sequence utility, dependency check, and benchmarking commands.

## extract

Extract called alleles or novel workflow data from typing results.

### Usage
```bash
gmlst utils extract [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-i, --input PATH` | Input FASTA, FASTQ, JSON, or TSV file. Required. | - |
| `-s, --scheme TEXT` | Scheme name for allele extraction or TSV fallback re-typing. | - |
| `-p, --provider TEXT` | Provider name when scheme resolution needs it. | - |
| `--allele TEXT` | Comma-separated locus filter for allele extraction. | - |
| `-b, --backend TEXT` | Backend used for sequence extraction and TSV fallback re-typing. | `blastn` |
| `--novel-allele` | Extract novel allele sequences. | `False` |
| `--novel-profile` | Extract complete novel profiles. | `False` |
| `--data-dir PATH` | Output directory for novel workflow files. | - |
| `--samples-dir DIRECTORY` | Directory containing original sample files for TSV fallback mode. | - |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst utils extract -i genome.fasta -s ecoli_1
gmlst utils extract -i genome.fasta -s ecoli_1 --allele dnaN,tsvA
gmlst utils extract -i typing_results.json --novel-allele --novel-profile --data-dir novel_data
gmlst utils extract -i typing_results.tsv -s ecoli_1 --novel-allele --novel-profile --samples-dir ./samples --data-dir novel_data
```

### Notes
- This command supports three main modes.
- Allele extraction from FASTA or FASTQ pulls called loci directly from a sample file, optionally limited with `--allele`.
- Novel extraction from JSON typing output is the preferred workflow because JSON preserves `novel_sequence` details.
- TSV fallback mode re-types against the original sample files, so it needs both `-s, --scheme` and `--samples-dir`.

---

## concat

Concatenate FASTA records into one sequence.

### Usage
```bash
gmlst utils concat [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-i, --input PATH` | Input FASTA file. Required. | - |
| `-o, --output PATH` | Write the concatenated FASTA to a file instead of stdout. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst utils concat -i genome_mlst.fasta
gmlst utils concat -i genome_mlst.fasta -o genome_mlst_concat.fasta
```

### Notes
- Records are concatenated in input order.
- This is useful after `utils extract` when you want one combined allele sequence per sample.

---

## check

Check whether a backend dependency is available.

### Usage
```bash
gmlst utils check [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-b, --backend [blastn\|kma\|minimap2\|nucmer]` | Backend to test. Required. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst utils check -b blastn
gmlst utils check -b minimap2
```

### Notes
- This command checks whether the selected backend is installed and callable.
- It exits with a non-zero status when the dependency is missing.

---

## benchmark

Benchmark backend performance, or run cgMLST gate-focused comparison.

### Usage
```bash
gmlst utils benchmark [OPTIONS] SAMPLES...
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-s, --scheme TEXT` | Scheme name to benchmark against. Required. | - |
| `-b, --backends TEXT` | Comma-separated backends to compare. | `blastn,kma,minimap2,nucmer` |
| `-r, --repeat INTEGER` | Number of repeated runs per backend. | `1` |
| `-f, --format [table\|tsv\|json]` | Output format. | `table` |
| `--cgmlst-gate` | Switch to cgMLST gate analysis mode. | `False` |
| `--gate-max-mismatches INTEGER` | Maximum mismatches allowed in gate analysis. | `0` |
| `--gate-details-output PATH` | Write detailed gate comparison results to a file. | - |
| `--gate-details-format [jsonl\|tsv]` | Format for detailed gate comparison output. | `jsonl` |
| `-o, --output PATH` | Write summary results to a file instead of stdout. | - |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `--force-reindex` | Rebuild cached indexes before benchmarking. | `False` |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst utils benchmark -s saureus_1 sample.fasta
gmlst utils benchmark -s saureus_1 -b blastn,kma,minimap2 sample.fasta
gmlst utils benchmark -s vparahaemolyticus_3 --cgmlst-gate --gate-details-output gate.jsonl sample.fna
```

### Notes
- Regular mode compares runtime and output across the selected backends.
- `--cgmlst-gate` switches the command into gate-analysis mode for cgMLST-oriented comparison workflows.
- `--gate-details-output` and `--gate-details-format` are useful when you need per-locus or per-sample review data, not only the summary table.
