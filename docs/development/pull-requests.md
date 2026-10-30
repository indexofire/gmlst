# Pull Requests

What a good PR description contains, how changes are reviewed, and the checks to run first.

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

## PR description template

```markdown
## Problem
cgMLST FASTQ runs with `-b minimap2` silently used a FASTA-only index.

## Change
Enforce the KMA-first policy in `commands/typing.py` and warn when the
backend is rewritten.

## Verification
- `pixi run test`
- `gmlst typing cgmlst -s vparahaemolyticus_3 -b minimap2 reads_R{1,2}.fq.gz`

## Behaviour change
TSV/JSON output unchanged; stderr now notes the backend switch.
```

Keep the diff focused: one problem, one approach, tests and docs in the same
PR.

## Common review comments

| Comment | What it means |
| --- | --- |
| "This belongs in `core/`" | The logic is domain code, not CLI code |
| "Use the existing protocol" | Do not add a one-off backend/provider path |
| "Add a regression test" | The bug should fail before the fix and pass after |
| "Update the zh page too" | Bilingual docs are a requirement |
