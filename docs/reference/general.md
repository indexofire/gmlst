# General Questions

What gmlst is, how MLST differs from cgMLST, and what to include when reporting a problem.

### What is gmlst?

`gmlst` is a Python CLI for bacterial genome typing. It supports classical MLST, larger cgMLST and wgMLST schemes, and scheme-free typing with `gmlst typing tgmlst`.

### What is the difference between MLST and cgMLST?

- MLST usually uses a small number of housekeeping loci, often 7
- cgMLST uses a much larger set of core-genome loci
- wgMLST goes broader still, often including accessory loci

In practice, MLST is lighter and easier to compare quickly. cgMLST gives finer resolution, but needs more compute and more complete locus recovery.

### Why does gmlst support multiple alignment backends?

Different inputs and workloads need different tools.

- `blastn` is a good baseline for assembly-based MLST
- `kma` is well suited to read-based workflows and cgMLST FASTQ paths
- `minimap2` is fast and flexible for assemblies and some read workflows
- `nucmer` can be useful for assembly comparison and alternate evidence

The project keeps the output model normalized so downstream calling logic can stay consistent across backends.

## Still Stuck?

When reporting a bug or opening an issue, include:

- the exact command you ran
- your install method, pixi or pip
- input type, FASTA or FASTQ
- backend name
- scheme name
- relevant stderr output
- whether the problem happens again with `--format json`

That makes it much easier to reproduce and fix the issue.

## Diagnose before asking

Collect these three outputs first; they answer most questions on their own:

```bash
gmlst --version
gmlst config show            # values and sources, secrets masked
gmlst utils check -b blastn  # repeat for the backend you use
```

Then reproduce with JSON, which keeps per-locus evidence:

```bash
gmlst typing mlst -s saureus_1 --format json sample.fna -o debug.json
```

## Symptom-to-page map

| Symptom | Page |
| --- | --- |
| `command not found`, Python version errors | [Installation](installation.md) |
| `Scheme ... not found`, download errors | [Schemes](schemes.md) |
| `ST = -`, missing or partial loci | [Typing](typing.md) |
| Unexpected TSV markers or empty output | [Output](output.md) |
| Environment variables or temp files | [Configuration](configuration.md) |
| Slow runs or thread tuning | [Performance](performance.md) |
| Exit codes and one-line errors | [Errors](errors.md) |
