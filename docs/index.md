# gmlst

**gmlst** is a fast Python 3.12 CLI for bacterial genome typing with classical MLST, large cgMLST and wgMLST schemes, and scheme-free discovery workflows.

## Features

- **Broad typing support**: `mlst`, `cgmlst`, and `tgmlst` from the same CLI
- **Multiple backends**: BLAST+, KMA, minimap2, MUMmer4, and a pure-Python kmer-hash engine
- **FASTA and FASTQ input**: assembled genomes and paired-end raw reads
- **Multiple providers**: PubMLST, Pasteur BIGSdb, Enterobase, cgmlst.org, and local custom schemes
- **Novel allele workflow**: detect novel alleles, extract profiles, build custom databases
- **Scheme-free typing**: de novo allele discovery without a preselected scheme
- **Local visualization**: Flask + Vue web app with MST visualization

## Quick Start

```bash
# Install
pip install gmlst

# List and download a scheme
gmlst scheme list
gmlst scheme download -s saureus_1

# Type a sample
gmlst typing mlst -s saureus_1 sample.fasta
```

## Documentation

| Section | Description |
|---------|-------------|
| [Installation](installation.md) | Setup and environment |
| [Quick Start](quickstart.md) | First-run workflow |
| [Commands](commands.md) | CLI reference |
| [Backends](backends.md) | Alignment backends |
| [Providers](providers.md) | Data sources |
| [cgMLST Guide](cgmlst_guide.md) | cgMLST modes |
| [Novel Workflow](novel_workflow.md) | Novel allele pipeline |
| [Visualization](visual_guide.md) | MST visualization |
| [FAQ](faq.md) | Troubleshooting |

## Links

- [GitHub Repository](https://github.com/indexofire/gmlst)
- [Report Issues](https://github.com/indexofire/gmlst/issues)
