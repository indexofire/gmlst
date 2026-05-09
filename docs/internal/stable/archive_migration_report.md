# Archive Migration Report Checklist

Use this checklist before moving any file from `stable/` to `archive/`.

## Preconditions

- [ ] Document status is no longer active
- [ ] Decisions are finalized
- [ ] Any required code/docs updates are complete

## Migration Steps

- [ ] Choose archive quarter directory (`archive/YYYY-QN/`)
- [ ] Rename file if release/version context is needed
- [ ] Add archive front matter:
  - [ ] `status: archived`
  - [ ] `archived_date`
  - [ ] `archived_from`
  - [ ] `archive_reason`
- [ ] Update `docs/internal/archive/README.md` index
- [ ] Remove/update links pointing to old `stable/` path

## Verification

- [ ] `pixi run internal-docs-check` passes
- [ ] Docs links validated manually for moved file
- [ ] Final commit message clearly states archive reason
