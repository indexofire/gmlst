# Development Setup

How to install the toolchain, verify the environment, and find the module that owns the behavior you want to change.

## Welcome

The project aims to keep one command-line interface across multiple typing styles, multiple alignment backends, and multiple public scheme providers. Good contributions usually have these traits:

- keep CLI behavior predictable
- keep domain logic out of thin Click wrappers
- reuse existing protocols and registries instead of adding one-off code paths
- preserve machine-readable outputs such as TSV and JSON
- add or update tests when behavior changes
- update docs when user-visible behavior changes

You do not need to start with a large feature. Useful first contributions include:

- improving a doc in `docs/`
- adding a focused test in `test/`
- fixing an error message in `gmlst/commands/`
- improving provider parsing in `gmlst/database/providers/`
- improving backend normalization in `gmlst/aligners/`

## Development Environment Setup

### Recommended setup with pixi

Pixi is the canonical development environment because it manages Python packages and external bioinformatics tools together.

```bash
git clone https://github.com/indexofire/gmlst.git
cd gmlst
pixi install
pixi shell
```

Install the editable package inside the pixi environment:

```bash
pixi run install-dev
```

### Verify the environment

Run these checks before you start editing code:

```bash
pixi run gmlst --version
pixi run gmlst --help
pixi run gmlst utils check -b blastn
pixi run gmlst utils check -b minimap2
pixi run gmlst utils check -b kma
pixi run gmlst utils check -b nucmer
```

### Core development tasks

The main tasks are defined in `pixi.toml`.

```bash
pixi run start
pixi run lint
pixi run format
pixi run check
pixi run test
pixi run test-v
pixi run internal-docs-check
pixi run visual-ui-build
```

### Python and packaging details

- Python version: 3.12
- package manager: pixi
- build backend: hatchling, see `pyproject.toml`
- CLI entry point: `gmlst.cli:main`
- formatter and linter: Ruff
- test framework: pytest

## Project Structure

This is the main repository layout contributors will touch most often.

```text
gmlst/
├── aligners/          # Backend adapters, normalize native output into AlleleMatch
├── calling/           # Allele calling, confidence, ST lookup
├── commands/          # Click command groups for typing, scheme, and utils
├── core/              # Shared pipeline pieces such as indexing, prefilter, ranking, refinement
├── data/              # Packaged static data, catalogs, blocked schemes
├── database/          # Cache layer, downloads, provider implementations
├── novel/             # Novel allele extraction and custom-scheme support
├── readers/           # FASTA, FASTQ, and sample input readers
├── schemefree/        # tgmlst workflow and helpers
├── visual/            # Flask-side visualization entry points and MST logic
├── web/               # Vue + Vite frontend source and built web assets
test/                  # pytest test suite
scripts/               # Development, analysis, and validation scripts
docs/                  # User and developer documentation
```

Useful starting points by task:

| Contribution target | Start here |
| --- | --- |
| Top-level CLI registration | `gmlst/cli.py` |
| Typing commands | `gmlst/commands/typing.py` (tgmlst: `typing_schemefree.py`, `--guess`: `typing_guess_run.py`) |
| Scheme commands | `gmlst/commands/scheme.py` (`update`: `scheme_update.py`, `update-fingerprints`: `scheme_fingerprints.py`) |
| Utility commands | `gmlst/commands/utils.py` |
| Visual commands | `gmlst/visual/cli.py` |
| Backend protocol | `gmlst/aligners/base.py` |
| Backend registry | `gmlst/aligners/__init__.py` |
| Provider protocol | `gmlst/database/providers/base.py` |
| Provider registry | `gmlst/database/providers/__init__.py` |
| Cache and catalog naming | `gmlst/database/cache.py` |
| Typing architecture notes | `docs/architecture/typing-pipeline.md` |
| CLI behavior reference | `docs/usage/cli/index.md` |

## Alternative: conda environment file

If you prefer conda over Pixi, the bundled `environment.yml` installs the same
toolchain:

```bash
conda env create -f environment.yml
conda activate gmlst
pip install -e .            # install the checkout in editable mode
```

## First contribution walkthrough

```bash
git checkout -b docs/installation-notes
# edit docs/installation/guide.md and docs/installation/guide.zh.md
pixi run mkdocs build --strict
pixi run check
git add docs/installation/guide.md docs/installation/guide.zh.md
git commit -m "docs: clarify pixi install steps"
```

Small docs and test changes are the easiest way to learn the layout before
touching the pipeline.

## Environment checklist

| Check | Command | Expected |
| --- | --- | --- |
| Python version | `pixi run python --version` | `Python 3.12.x` |
| CLI entry point | `pixi run gmlst --version` | package version |
| Backend availability | `pixi run gmlst utils check -b blastn` | `[OK]` |
| Editable install | `pixi run pip show gmlst` | location points at the checkout |
