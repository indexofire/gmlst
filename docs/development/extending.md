# Extending gmlst

Step-by-step recipes for new alignment backends, data providers, and CLI commands, including the questions reviewers will ask.

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
5. Update `docs/usage/cli/index.md` for user-visible command behavior.
6. Add tests for both success and failure cases.

### Pattern to follow

- user-facing help text should be clear and concrete
- option names should be consistent with current commands
- command functions should call domain helpers instead of embedding large workflows inline

## Backend checklist

```text
[ ] class satisfies the Aligner protocol (name, supports_fastq,
    check_dependencies, index, align)
[ ] native output normalised into AlleleMatch (identity in %, coverage 0-1)
[ ] AlignmentResult.failed_loci populated for loci without hits
[ ] registered in gmlst/aligners/__init__.py
[ ] added to CLI choices via AVAILABLE_BACKENDS
[ ] unit test with a tiny allele set
```

## Provider checklist

```text
[ ] name / label properties
[ ] list_schemes() returns SchemeInfo objects
[ ] download_scheme() writes <locus>.tfa, the profile table, and .meta.json
[ ] update_scheme() returns True when content changed
[ ] registered in gmlst/database/providers/__init__.py
[ ] never assigns final names itself (DatabaseCache does that)
[ ] manual check: scheme list / download / update
```

## CLI command example

```python
@utils_group.command("count-loci")
@click.argument("scheme")
def cmd_count_loci(scheme: str) -> None:
    """Print the number of loci in a cached scheme."""
    info = DatabaseCache().get_scheme(scheme)
    click.echo(info.n_loci)
```

Then add a test in `test/test_utils_commands.py` and document the command in
`docs/usage/cli/index.md` plus its `.zh.md` sibling.

## Backend protocol, in one glance

```python
class Aligner(Protocol):
    name: str
    supports_fastq: bool

    def check_dependencies(self) -> None: ...
    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path: ...
    def align(self, sample, index_path, loci, input_type) -> AlignmentResult: ...
```

If your class satisfies this shape, the pipeline can use it without importing
your module directly.
