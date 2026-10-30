# Testing

Running the suite, writing focused tests, and the manual scenarios worth checking before a pull request.

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

## Example test

```python
from pathlib import Path

from gmlst.readers.sample import detect_sample


def test_detect_paired_fastq(tmp_path: Path) -> None:
    r1 = tmp_path / "sample_R1.fastq.gz"
    r2 = tmp_path / "sample_R2.fastq.gz"
    r1.write_bytes(b"")
    r2.write_bytes(b"")

    sample = detect_sample(r1)

    assert sample.input_type == "fastq"
    assert sample.mate_path == r2
```

## Fixtures to prefer

| Fixture | Use |
| --- | --- |
| `tmp_path` | cache dirs, output files, fake schemes |
| `DummyScheme` / `DummyCache` | typing tests without network |
| `monkeypatch` | environment variables and tool lookups |

Avoid real downloads in tests. If a test needs a scheme, build a two-locus
fixture under `tmp_path` and point `--cache-dir` at it.

## Test layout

```text
test/
  conftest.py            shared fixtures
  test_typing.py         core typing behaviour
  test_scheme.py         scheme commands and catalog logic
  test_*_provider.py     provider parsing and downloads
  test_visual_command.py visual CLI and MST exports
  schemefree/            tgmlst-specific suite
```

Name the test after the behaviour, not the function:

```python
def test_cgmlst_fastq_forces_kma_backend(...): ...
def test_blocked_scheme_is_hidden_from_list(...): ...
```
