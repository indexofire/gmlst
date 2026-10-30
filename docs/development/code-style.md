# Code Style

Formatting, imports, naming, type annotations, error handling, and CLI patterns, with examples.

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

## Error handling example

```python
# Good: specific exception, context preserved
try:
    data = path.read_text()
except FileNotFoundError as exc:
    raise FileNotFoundError(f"Input file not found: {path}") from exc

# Bad: swallows the cause
try:
    data = path.read_text()
except Exception:
    return None
```

## CLI example

```python
@typing_group.command("mlst")
@click.argument("samples", nargs=-1, required=True)
@click.option("--scheme", "-s", help="Scheme name.")
def cmd_mlst(samples: tuple[str, ...], scheme: str | None) -> None:
    """Type assemblies with classical MLST."""
    if scheme is None and not samples:
        raise click.UsageError("provide at least one sample")
    run_typing(samples=samples, scheme=scheme)
```

Parsing and validation live in the Click function; `run_typing()` owns the
workflow. A reviewer should be able to read the command body in one screen.

## Docstring and typing example

```python
def normalise_call(match: AlleleMatch, threshold: float = 0.95) -> str:
    """Render one allele call in tseemann-compatible notation.

    Parameters
    ----------
    match:
        Normalised backend hit for a single locus.
    threshold:
        Minimum coverage for a partial call to be considered complete.

    Returns
    -------
    str
        ``"23"``, ``"~23"``, ``"15?"``, or ``"-"``.
    """
```
