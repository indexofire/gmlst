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
gmlst scheme download saureus_1

# Type a sample
gmlst typing mlst -s saureus_1 sample.fasta
```

## Documentation

### English

| Section | Description |
|---------|-------------|
| [Installation](en/installation.md) | Setup and environment |
| [Quick Start](en/quickstart.md) | First-run workflow |
| [Commands](en/commands.md) | CLI reference |
| [Backends](en/backends.md) | Alignment backends |
| [Providers](en/providers.md) | Data sources |
| [Configuration](en/configuration.md) | Environment variables |
| [cgMLST Guide](en/cgmlst_guide.md) | cgMLST modes |
| [Novel Workflow](en/novel_workflow.md) | Novel allele pipeline |
| [Visualization](en/visual_guide.md) | MST visualization |
| [FAQ](en/faq.md) | Troubleshooting |

### 简体中文

| 章节 | 说明 |
|---------|-------------|
| [安装](zh/installation.md) | 安装与环境配置 |
| [快速入门](zh/quickstart.md) | 首次运行流程 |
| [后端](zh/backends.md) | 比对后端 |
| [数据源](zh/providers.md) | 数据来源 |
| [配置参考](zh/configuration.md) | 环境变量 |
| [cgMLST 指南](zh/cgmlst_guide.md) | cgMLST 模式 |
| [Novel 工作流](zh/novel_workflow.md) | 新等位基因流程 |
| [可视化](zh/visual_guide.md) | MST 可视化 |
| [FAQ](zh/faq.md) | 常见问题 |

## Links

- [GitHub Repository](https://github.com/indexofire/gmlst)
- [Report Issues](https://github.com/indexofire/gmlst/issues)
