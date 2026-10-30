# Documentation

Where each kind of document belongs, the bilingual file convention, and how to keep the index accurate.

## Documentation Rules

Documentation lives in several places. Use the right home for the right kind of content.

- user and developer docs: `docs/`
- internal active notes: `docs/internal/stable/`
- internal archive: `docs/internal/archive/`
- command behavior authority: `docs/usage/cli/index.md`

Pages are organized by topic, mirroring the `gside` layout:

```text
docs/
  index.md              documentation home
  installation/         install guide, quick start, configuration, pipelines
  usage/                CLI reference, backends, providers, and guides
  architecture/         system design
  reference/            FAQ
  development/          contributing
```

Every page has a Chinese sibling with a `.zh.md` suffix (`quick-start.md` →
`quick-start.zh.md`); the i18n plugin builds `/zh/` from those files. Section
landing pages are `index.md` and use Material grid cards to link their children.

When you change command behavior, update `docs/usage/cli/index.md`. When you add or reorganize docs, check `docs/index.md` so the index stays accurate.

Useful docs to cross-reference:

- `docs/installation/guide.md`
- `docs/installation/quick-start.md`
- `docs/usage/cli/index.md`
- `docs/architecture/index.md`

## Adding a page

1. Create `docs/<section>/<page>.md` and `docs/<section>/<page>.zh.md`.
2. Add both to `nav` in `mkdocs.yml` with a label.
3. Add the label to `nav_translations` for the `zh` locale if it is new.
4. Link it from the section `index.md` / `index.zh.md` card grid.
5. Run `pixi run mkdocs build --strict` and `pixi run check`.

## Bilingual pair example

```text
docs/usage/backends.md
docs/usage/backends.zh.md
```

The zh page links to `.zh.md` siblings; the i18n plugin rewrites language
selection automatically during the build.

## Section map

| Section | Holds |
| --- | --- |
| `installation/` | install, quick start, configuration, pipelines |
| `usage/` | CLI reference and task guides |
| `architecture/` | internal design |
| `reference/` | troubleshooting and error reference |
| `development/` | contributor workflow |

## Review checklist for docs PRs

```text
[ ] English and Chinese pages both updated
[ ] nav + nav_translations entries added
[ ] section index card links to the new page
[ ] mkdocs build --strict passes
[ ] commands in examples actually run
```
