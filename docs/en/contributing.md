# Contributing to gmlst

`gmlst` is a Python 3.12 CLI for bacterial genome typing across MLST, cgMLST, wgMLST, and scheme-free workflows. Contributions are welcome in code, docs, tests, provider integrations, backend integrations, and bug reports.

This guide explains how the repository is laid out, how to set up a local environment, and how to extend the project without fighting the existing architecture. For CLI behavior, use [commands.md](commands.md) as the authority. For execution-path boundaries, read [architecture.md](architecture.md).

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
| Typing commands | `gmlst/commands/typing.py` |
| Scheme commands | `gmlst/commands/scheme.py` |
| Utility commands | `gmlst/commands/utils.py` |
| Visual commands | `gmlst/visual/cli.py` |
| Backend protocol | `gmlst/aligners/base.py` |
| Backend registry | `gmlst/aligners/__init__.py` |
| Provider protocol | `gmlst/database/providers/base.py` |
| Provider registry | `gmlst/database/providers/__init__.py` |
| Cache and catalog naming | `gmlst/database/cache.py` |
| Typing architecture notes | `docs/architecture.md` |
| CLI behavior reference | `docs/commands.md` |

## Development Workflow

### 1. Create a branch

Create a focused branch from your local main branch.

```bash
git checkout main
git pull
git checkout -b docs/contributing-faq
```

Pick a branch name that reflects the change, for example:

- `fix/minimap2-fastq-warning`
- `feat/new-provider`
- `docs/faq-cache-behavior`
- `test/cgmlst-fastq-policy`

### 2. Make changes

Typical edit loops look like this:

```bash
pixi shell
pixi run start
pixi run gmlst --help
pixi run gmlst typing --help
```

For provider work, inspect current catalogs and scheme resolution:

```bash
pixi run gmlst scheme list -p pubmlst
pixi run gmlst scheme list -p enterobase -t cgmlst
```

For typing work, use small local examples or targeted tests. If you are changing output behavior, compare TSV and JSON output before and after your change.

### 3. Run formatting and linting

Use the project task, because it matches the documented workflow:

```bash
pixi run check
```

You can also run the steps separately while iterating:

```bash
pixi run lint
pixi run format
pixi run format-check
```

### 4. Run tests

Run the full test suite before opening a pull request:

```bash
pixi run test
```

Run a single file or test while iterating:

```bash
pixi run pytest test/test_typing.py
pixi run pytest test/test_typing.py -k cgmlst
pixi run pytest -v
```

### 5. Check docs and frontend when relevant

If you changed docs structure or internal docs rules:

```bash
pixi run internal-docs-check
```

If you changed the visual frontend in `gmlst/web/frontend/`:

```bash
pixi run visual-ui-build
```

### 6. Commit your work

This repository does not enforce a custom commit format in code, but conventional commit style works well and keeps history easy to scan.

Examples:

```text
feat: add provider override docs for private BIGSdb
fix: keep cgmlst FASTQ on kma backend
docs: expand contributing guide for backend protocol
test: cover blocked scheme filtering in list command
refactor: split typing output helpers
```

Typical flow:

```bash
git status
git add docs/contributing.md docs/faq.md docs/zh/contributing.md docs/zh/faq.md
git commit -m "docs: add contributing guide and FAQ"
```

## Code Style Guide

### Formatting rules

Formatting is controlled by Ruff in `pyproject.toml`.

- line length: 88
- indentation: 4 spaces
- quote style: double quotes
- trailing commas: yes, in multi-line collections
- target Python version: 3.12

Run:

```bash
pixi run lint
pixi run format
```

### Import conventions

- use absolute imports
- keep import order Ruff-compatible: stdlib, third-party, local
- no wildcard imports

Example:

```python
from pathlib import Path

import click

from gmlst.database.cache import DatabaseCache
```

### Naming conventions

| Construct | Convention | Example |
| --- | --- | --- |
| module | `snake_case` | `typing_output.py` |
| function | `snake_case` | `prepare_sample_inputs()` |
| variable | `snake_case` | `scheme_name` |
| class | `PascalCase` | `BlastnAligner` |
| constant | `UPPER_SNAKE_CASE` | `HELP_SETTINGS` |

### Type annotations

All function signatures should be annotated.

- use `list[str]`, not `typing.List[str]`
- use `X | Y`, not `Union[X, Y]`
- prefer `pathlib.Path` for filesystem paths

Example:

```python
def download_scheme(
    scheme_name: str,
    dest_dir: Path,
    scheme_type: str = "mlst",
) -> None:
    ...
```

### Error handling

- raise specific exceptions
- avoid bare `except`
- keep user-facing CLI errors in Click-friendly form when the failure is user input related
- preserve context with `raise ... from exc` where useful

Good places to copy from:

- `gmlst/commands/scheme.py`
- `gmlst/visual/cli.py`
- `gmlst/database/providers/base.py`

### CLI patterns

The project uses Click. Keep command functions thin.

- define groups and options in `gmlst/commands/` or the feature-local module such as `gmlst/visual/cli.py`
- keep orchestration in command files
- keep domain logic in library modules such as `gmlst/core/`, `gmlst/database/`, `gmlst/calling/`, `gmlst/visual/mst.py`
- register top-level groups in `gmlst/cli.py`

Examples to follow:

- typing group: `gmlst/commands/typing.py`
- scheme group: `gmlst/commands/scheme.py`
- utils group: `gmlst/commands/utils.py`
- visual group: `gmlst/visual/cli.py`

## Adding a New Alignment Backend

The alignment layer uses a protocol pattern. Start with `gmlst/aligners/base.py`.

### What the protocol requires

Every backend must satisfy the `Aligner` protocol:

- `name`
- `supports_fastq`
- `check_dependencies()`
- `index(allele_fastas, index_dir)`
- `align(sample, index_path, loci, input_type)`

The important design rule is this: backend-specific output should be normalized into `AlleleMatch` and `AlignmentResult`, so the calling code stays backend-agnostic.

### Step-by-step

1. Create a new module in `gmlst/aligners/`, for example `gmlst/aligners/mybackend.py`.
2. Implement a class such as `MyBackendAligner` that matches the `Aligner` protocol in `gmlst/aligners/base.py`.
3. Normalize hits into `AlleleMatch` records.
4. Return a full `AlignmentResult` with `sample_id`, `matches`, `failed_loci`, backend name, and runtime.
5. Add the backend to `_REGISTRY` in `gmlst/aligners/__init__.py`.
6. If the backend should be CLI-selectable, make sure it is exposed through `AVAILABLE_BACKENDS`, which Click choices in `gmlst/commands/typing.py` and `gmlst/commands/utils.py` already use.
7. Add tests under `test/`.
8. Update docs if user-visible behavior changes.

### Good examples to copy

- `gmlst/aligners/blastn.py`
- `gmlst/aligners/minimap2.py`
- `gmlst/aligners/kma.py`
- `gmlst/aligners/nucmer.py`

### Questions to answer before opening a PR

- does it support FASTA, FASTQ, or both?
- how are dependencies checked?
- what external files are written into `index_dir`?
- how are low-confidence, partial, and missing loci represented?
- does it behave correctly for multicopy hits and read depth, if applicable?

## Adding a New Data Provider

Provider integrations follow the same protocol-style idea. Start with `gmlst/database/providers/base.py`.

### What the protocol requires

Every provider must satisfy the `Provider` protocol:

- `name`
- `label`
- `list_schemes()`
- `download_scheme()`
- `update_scheme()`

The shared metadata container is `SchemeInfo`.

### Step-by-step

1. Create `gmlst/database/providers/<provider>.py`.
2. Implement a provider class that matches the `Provider` protocol.
3. Return `SchemeInfo` objects from `list_schemes()`.
4. Download allele FASTA files and profile files into the target directory in `download_scheme()`.
5. Implement `update_scheme()` so existing local content can be refreshed.
6. Register the provider in `gmlst/database/providers/__init__.py`.
7. Verify scheme listing, download, and update flows through `gmlst scheme list`, `gmlst scheme download`, and `gmlst scheme update`.
8. Add tests.
9. Update docs.

### Important cache and naming rule

Do not bypass catalog naming logic in `gmlst/database/cache.py`. `DatabaseCache.save_catalog()` normalizes names within a provider and then ensures global uniqueness across providers. If you add a provider, reuse the cache layer instead of assigning ad hoc final names yourself.

### Good examples to copy

- `gmlst/database/providers/bigsdb.py`
- `gmlst/database/providers/enterobase.py`
- `gmlst/database/providers/cgmlst.py`

### Useful manual checks

```bash
pixi run gmlst scheme list -p pubmlst
pixi run gmlst scheme list -p pasteur
pixi run gmlst scheme list -p enterobase -t cgmlst
pixi run gmlst scheme download -s saureus_1
pixi run gmlst scheme update -s saureus_1
```

## Adding CLI Commands

Most CLI work fits into an existing group.

### Existing top-level groups

- `typing`, defined in `gmlst/commands/typing.py`
- `scheme`, defined in `gmlst/commands/scheme.py`
- `utils`, defined in `gmlst/commands/utils.py`
- `visual`, defined in `gmlst/visual/cli.py`

These are registered in `gmlst/cli.py`.

### Step-by-step

1. Decide whether your command belongs in `typing`, `scheme`, `utils`, or `visual`.
2. Add a new Click command with `@cmd_typing.command(...)`, `@scheme_group.command(...)`, `@utils_group.command(...)`, or `@visual_group.command(...)`.
3. Keep parsing and validation in the Click layer.
4. Move heavy logic into a helper module or domain module.
5. Update `docs/commands.md` for user-visible command behavior.
6. Add tests for both success and failure cases.

### Pattern to follow

- user-facing help text should be clear and concrete
- option names should be consistent with current commands
- command functions should call domain helpers instead of embedding large workflows inline

## Testing Guidelines

The project uses pytest. The configured test root is `test/`, see `pyproject.toml`.

### Run tests

```bash
pixi run test
pixi run test-v
pixi run pytest test
pixi run pytest test/test_scheme.py
pixi run pytest -k provider
```

### Writing new tests

- put tests under `test/`
- keep one file focused on one area when practical
- add regression tests for bugs
- prefer small fixtures and narrow assertions
- cover CLI output markers when you change user-visible output

If you change any of these areas, add or update tests nearby:

- backends, test backend selection and output normalization
- providers, test scheme listing and download behavior
- commands, test help text, option validation, and exit paths
- cache, test naming and provider interactions

### Manual scenarios worth checking

```bash
pixi run gmlst --help
pixi run gmlst typing --help
pixi run gmlst scheme --help
pixi run gmlst utils --help
pixi run gmlst visual --help
```

## Documentation Rules

Documentation lives in several places. Use the right home for the right kind of content.

- user and developer docs: `docs/`
- internal active notes: `docs/internal/stable/`
- internal archive: `docs/internal/archive/`
- command behavior authority: `docs/commands.md`

When you change command behavior, update `docs/commands.md`. When you add or reorganize docs, check `docs/README.md` so the index stays accurate.

Useful docs to cross-reference:

- `docs/installation.md`
- `docs/quickstart.md`
- `docs/commands.md`
- `docs/architecture.md`

## Visual Web Frontend

The visualization feature combines Flask and Vue.

- command entry: `gmlst/visual/cli.py`
- Flask app: `gmlst/visual/app.py`
- MST logic: `gmlst/visual/mst.py`
- frontend source: `gmlst/web/frontend/`
- built assets: `gmlst/web/static/visual/dist/`

### Frontend workflow

```bash
pixi run visual-ui-build
pixi run gmlst visual web --help
pixi run gmlst visual web --open-browser
```

If you modify the frontend, rebuild the assets before opening the PR.

## Pull Request Process

Open a pull request once your branch is ready for review. The repository uses GitHub, so the PR description should be complete enough for a reviewer to understand the change without guessing.

### What to include in the PR description

- a short summary of the problem
- the approach you chose
- commands you ran for verification
- any behavior changes in CLI output, provider behavior, or backend selection
- screenshots only if you changed the visual web UI

### Review criteria

Reviewers will usually look for these things:

- architecture fit, especially protocol and registry consistency
- stable CLI behavior and help text
- tests for changed behavior
- docs for user-visible changes
- no hidden coupling between command code and domain logic

### Checks to run before opening the PR

```bash
pixi run check
pixi run test
pixi run internal-docs-check
```

If the PR touches `gmlst/web/frontend/`, also run:

```bash
pixi run visual-ui-build
```

## Release Process

If you are preparing a release, keep the release metadata in sync.

### Version locations

- `pixi.toml`, workspace version
- `pyproject.toml`, package version
- `gmlst/__init__.py`, runtime version if applicable in the current release flow
- `CHANGELOG.md`, release notes

### Typical release checklist

1. update version strings
2. update `CHANGELOG.md`
3. run checks and tests
4. create a release commit
5. create a Git tag such as `v0.1.0`
6. publish the GitHub release

Example commands:

```bash
pixi run check
pixi run test
git add pyproject.toml pixi.toml CHANGELOG.md gmlst/__init__.py
git commit -m "chore: prepare release v0.1.0"
git tag v0.1.0
```

If a release does not change one of those files in the current workflow, do not force an edit just to match the checklist. Keep release changes accurate to the actual repository state.

## Getting Help

If you are unsure where a change belongs, inspect the nearest existing module first and follow that pattern. For public-facing behavior, prefer updating docs and tests in the same pull request so the repository stays coherent.
