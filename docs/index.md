# gmlst documentation

`gmlst` is a fast Python 3.12 CLI for bacterial genome typing with classical
MLST, large cgMLST and wgMLST schemes, and scheme-free discovery. It types
assembled genomes and paired-end reads, drives several alignment backends,
downloads schemes from multiple public providers, and ships a local MST
visualizer.

## Start here

| I want to… | Read |
| --- | --- |
| Install gmlst and run a first sample | [Quick start](installation/quick-start.md) |
| Install every external tool at once | [Installation guide](installation/guide.md) |
| Configure caches, provider endpoints, API keys | [Configuration](installation/configuration.md) |
| Run gmlst in Docker, Nextflow, or Snakemake | [Pipelines](installation/pipelines.md) |
| Learn every CLI flag | [CLI reference](usage/cli/index.md) |
| Understand the `typing` command | [Typing](usage/cli/typing.md) |
| Pick an alignment backend | [Alignment backends](usage/backends.md) |
| Browse or download schemes | [Data providers](usage/providers.md) |
| Tune large cgMLST runs | [cgMLST guide](usage/cgmlst.md) |
| Extract novel alleles and build custom schemes | [Novel workflow](usage/novel-workflow.md) |
| Build an MST in the browser | [Visualization](usage/visualization.md) |
| Auto-detect species without `-s` | [Fingerprint database](usage/fingerprint-database.md) |
| Consume JSON output safely | [JSON output envelope](usage/cli/index.md#json-output-envelope) |
| Troubleshoot a problem | [FAQ](reference/index.md) |

## What gmlst does

```text
FASTA assembly / paired FASTQ
        │
        ▼
   k-mer prefilter ── blastn · minimap2 · nucmer · kma
        │
        ▼
   allele calls (exact · novel · partial) ── ST lookup ── TSV / JSON
```

Two typing entry points share one engine:

- `gmlst typing mlst|cgmlst` — scheme-based typing against public, cached, or
  custom schemes.
- `gmlst typing tgmlst` — scheme-free allele discovery, optionally saved as a
  reusable scheme.

## Installation at a glance

```bash
pip install gmlst                 # Python 3.12

# or one shot with every external tool, from a checkout
conda env create -f environment.yml
```

The four alignment backends (`blastn`, `minimap2`, `nucmer`, `kma`) are
external tools. See the [installation guide](installation/guide.md) for the
full list and per-platform notes.

## Design principles

- **Backend-agnostic calls.** One normalized result model sits behind every
  aligner, so calls and ST assignment do not depend on the backend.
- **Evidence over guesses.** Exact, novel, partial, and conflicting calls are
  reported distinctly, and every sample carries a 0–100 quality score.
- **Cache-first.** Schemes and indexes are reused, so repeated and offline runs
  need no network.
- **Automation friendly.** Versioned JSON envelopes, data-only stdout, and
  stable exit codes make the CLI safe to script and drive from agents.
- **Unattended where possible.** `--guess` types mixed-species batches without
  prompting.

## Project layout

```text
gmlst/
  cli.py            Click entry point
  commands/         typing, scheme, utils, config, visual commands
  core/             pipeline, prefilter, exact hash, refinement, ranking
  aligners/         blastn, minimap2, nucmer, kma adapters
  calling/          allele calling, confidence, ST lookup
  database/         providers, catalog cache, downloads
  schemefree/       tgmlst engine
  visual/           MST builder and Flask API
  web/              Vue frontend and templates
docs/               English/Chinese documentation
test/               unit and integration tests
```

## License

MIT. See the [repository](https://github.com/indexofire/gmlst) for the project
overview and the [changelog](https://github.com/indexofire/gmlst/blob/main/CHANGELOG.md).
