# Development Workflow

Branching, the edit loop, linting, tests, docs and frontend checks, and commit conventions.

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
git add docs/development/setup.md docs/reference/installation.md \
  docs/development/setup.zh.md docs/reference/installation.zh.md
git commit -m "docs: add contributing guide and FAQ"
```

## Full example session

```bash
git checkout main && git pull
git checkout -b fix/minimap2-fastq-warning

# edit code and tests
pixi run check                 # ruff lint + format check
pixi run pytest test/test_typing.py -q
pixi run test                  # full suite before the PR

git status
git add gmlst/commands/typing.py test/test_typing.py
git commit -m "fix: keep cgmlst FASTQ on kma backend"
git push -u origin fix/minimap2-fastq-warning
```

## What to run for each change type

| Change | Minimum checks |
| --- | --- |
| Docs only | `pixi run mkdocs build --strict` |
| Python only | `pixi run check && pixi run test` |
| Frontend | `pixi run visual-ui-build` |
| CLI behaviour | tests plus updated `docs/usage/cli/` |
| Provider | manual `scheme list/download/update` plus tests |

## Commit message examples

```text
feat: add private BIGSdb provider label
fix: keep cgmlst FASTQ on kma backend
docs: split architecture guide by topic
test: cover blocked scheme filtering
refactor: extract typing run helpers
```
