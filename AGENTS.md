# AGENTS.md

Agent guidance for this repository. Read this before writing or editing any code.

---

## Project Overview

- **Language**: Python 3.12 (CLI tool with Flask web visualization)
- **Frontend**: Vue 3 + Vite + D3 (in `gmlst/web/frontend/`)
- **Package manager**: [pixi](https://pixi.sh) — manages environments, tasks, and dependencies via `pixi.toml`
- **Linter + Formatter**: [ruff](https://docs.astral.sh/ruff/)
- **Testing**: pytest (540+ tests in `test/`)

---

## Environment Setup

```bash
# Install pixi (if not already installed)
curl -fsSL https://pixi.sh/install.sh | bash

# Install all dependencies and activate environment
pixi install

# Run a shell inside the pixi environment
pixi shell
```

All commands below assume you are inside the pixi environment (`pixi shell`) or prefixed with `pixi run`.

---

## Build / Run Commands

```bash
# Run the CLI
pixi run start

# Or run directly
pixi run python -m gmlst

# Install the package in editable mode
pixi run install-dev
```

Check `pixi.toml` for the canonical task definitions — prefer `pixi run <task>` over ad-hoc commands.

---

## Frontend Build

```bash
# Build frontend assets (Vue + Vite → gmlst/web/static/visual/dist/)
pixi run visual-ui-build

# Or directly
npm --prefix gmlst/web/frontend run build

# Frontend dev server
npm --prefix gmlst/web/frontend run dev
```

Built assets are served by Flask from `gmlst/web/static/visual/dist/`.

---

## Lint / Format Commands

```bash
# Check for lint errors (do not auto-fix)
pixi run lint

# Auto-fix lint errors
pixi run lint-fix

# Format code
pixi run format

# Check formatting without writing (CI mode)
pixi run format-check

# Run both lint + format checks in one pass (dry-run, does not modify files)
pixi run check

# Auto-fix lint errors and format code
pixi run fix
```

**Always run ruff before committing.** Fix all lint errors; do not use `# noqa` suppression unless unavoidable, and always add a comment explaining why.

---

## Testing Commands

```bash
# Run all tests
pixi run test

# Run a single test file
pixi run pytest test/test_foo.py

# Run a single test by name
pixi run pytest test/test_foo.py::test_bar_function

# Run with verbose output
pixi run test-v

# Run with stdout captured (useful for debugging)
pixi run pytest -s

# Run only tests matching a keyword
pixi run pytest -k "keyword"
```

---

## Code Style Guidelines

### Formatting
- Line length: **88 characters** (ruff default; adjust in `pyproject.toml` if needed)
- Indentation: **4 spaces** (never tabs)
- Trailing commas in multi-line collections: **yes**
- String quotes: **double quotes** (`"..."`) — ruff enforces this by default

### Imports
- Use **absolute imports** only; avoid relative imports except within packages
- Import order enforced by ruff (isort-compatible): stdlib → third-party → local
- No wildcard imports (`from module import *`)
- Group imports with a blank line between each group

```python
# Good
import sys
from pathlib import Path

import click

from gmlst.core.pipeline import run
```

### Naming Conventions
| Construct | Convention | Example |
|---|---|---|
| Module/file | `snake_case` | `file_parser.py` |
| Package/dir | `snake_case` | `gmlst/` |
| Function | `snake_case` | `parse_input()` |
| Variable | `snake_case` | `file_path` |
| Class | `PascalCase` | `SequenceParser` |
| Constant | `UPPER_SNAKE_CASE` | `DEFAULT_TIMEOUT` |
| Private | leading underscore | `_internal_helper()` |
| Type alias | `PascalCase` | `SequenceList = list[str]` |

### Type Annotations
- **Always annotate** function signatures (parameters + return type)
- Use built-in generics (`list[str]`, `dict[str, int]`) over `typing.List` / `typing.Dict` (Python 3.9+)
- Use `X | Y` union syntax over `Union[X, Y]` (Python 3.10+)
- Use `from __future__ import annotations` at top of file if targeting Python < 3.10

```python
# Good
def parse_file(path: Path, strict: bool = False) -> list[str]:
    ...

# Bad
def parse_file(path, strict=False):
    ...
```

### Error Handling
- Raise specific exceptions (`ValueError`, `FileNotFoundError`, custom subclasses) — never `Exception` or bare `raise`
- Never silence exceptions with empty `except` blocks
- Use `contextlib.suppress` only for truly ignorable errors, with a comment
- Prefer `pathlib.Path` over `os.path` for filesystem operations
- Log errors before re-raising when context would be lost

```python
# Good
try:
    data = path.read_text()
except FileNotFoundError as e:
    raise FileNotFoundError(f"Input file not found: {path}") from e

# Bad
try:
    data = path.read_text()
except Exception:
    pass
```

### CLI Patterns
- Use [Click](https://click.palletsprojects.com/) for CLI interfaces (or Typer if preferred)
- Keep `main()` thin — delegate logic to library functions
- Use `if __name__ == "__main__": main()` as entry point
- Validate input early; emit clear error messages to stderr

### File & Module Organization
```
gmlst/
├── __init__.py           # Public API exports only
├── __main__.py           # Entry point: calls main()
├── cli.py                # Click commands / argument parsing
├── core/                 # Core typing pipeline
│   ├── pipeline.py       #   Orchestration
│   ├── prefilter.py      #   k-mer prefilter
│   ├── exact_hash.py     #   Exact hash matching
│   ├── indexing.py        #   Index building
│   ├── refinement.py     #   Refinement pass
│   ├── ranking.py        #   Result ranking
│   ├── cds.py            #   CDS prediction integration
│   └── ...               #   Adapters, config, types, sequences
├── commands/             # CLI command implementations
│   ├── typing.py         #   typing command group
│   ├── scheme.py         #   scheme command group
│   ├── utils.py          #   Output utilities
│   └── ...
├── visual/               # Flask web visualization
│   ├── app.py            #   Flask API routes + helpers
│   ├── cli.py            #   visual CLI subcommand
│   ├── mst.py            #   MST builder (public API)
│   ├── mst_shared.py     #   Shared types + parsing
│   ├── mst_edmonds.py    #   Edmonds MST backend
│   └── mst_grapetree.py  #   GrapeTree layout backend
├── web/                  # Frontend + templates
│   ├── frontend/         #   Vue 3 + Vite source
│   │   └── src/
│   │       ├── App.vue        # Main SPA component
│   │       ├── style.css      # All styles (keep App.vue <style> empty)
│   │       └── visualSelection.js  # Pure utility functions
│   ├── templates/        #   Jinja2 templates
│   └── static/           #   Built assets (dist/)
├── aligners/             # Alignment backend adapters
├── calling/              # Allele calling logic
├── database/             # Schema providers + cache
├── novel/                # Novel allele workflow
├── schemefree/           # tgmlst scheme-free typing
├── readers/              # FASTA/FASTQ readers
├── data/                 # Catalog JSON files
├── tools/                # External tool wrappers
├── utils.py              # Shared utilities
├── fasta_io.py           # FASTA I/O
├── kmer_prefilter.py     # k-mer hash prefilter
├── metadata_io.py        # Metadata parsing
└── core_config.py        # Global configuration
test/
├── conftest.py           # Shared fixtures (if present)
├── test_<module>.py      # One test file per module
└── schemefree/           # Scheme-free test suite
```

- Keep modules focused and small (< 300 lines as a guideline)
- Pure logic lives in `core/`; I/O and side effects are isolated
- No circular imports
- Frontend styles go to `style.css` — keep `App.vue` `<style>` tag empty
- Do not add npm dependencies without explicit approval

---

## pyproject.toml Conventions

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.pytest.ini_options]
testpaths = ["test"]
addopts = "-v"
```

---

## Key Rules for Agents

1. **Run `pixi run check` after every code change** — it is a dry-run check; use `pixi run fix` to auto-fix
2. **Never use `# type: ignore` or `# noqa` without an explanatory comment**
3. **Never commit secrets** — use environment variables or `.env` files (gitignored)
4. **Prefer `pathlib.Path` over `os.path`** for all filesystem operations
5. **All functions must have type annotations** — no untyped signatures
6. **One responsibility per module** — don't let files grow into god-modules
7. **Don't add dependencies without updating `pixi.toml`** — use `pixi add <pkg>`
8. **Frontend: do not add npm dependencies** without explicit approval
9. **Frontend: all styles go to `style.css`** — keep App.vue `<style>` tag empty
10. **Do not modify `visualSelection.js` or `visualSelection.test.js`** unless explicitly asked
