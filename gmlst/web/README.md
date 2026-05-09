# Web Asset Layout (gmlst visual)

This directory contains all web-facing assets for `gmlst visual web`.

## Purpose

- Keep visual web assets co-located with the Python package for simple runtime
  loading by Flask.
- Keep command/backend/frontend boundaries explicit.

## Structure

- `templates/visual/` — Flask/Jinja templates (entry HTML shell)
- `frontend/` — Vue + Vite source project
- `static/visual/dist/` — built frontend assets served by Flask

## Ownership Boundaries

- CLI entry: `gmlst/visual/cli.py`
- Flask backend app + routes: `gmlst/visual/app.py`
- MST/domain logic: `gmlst/visual/mst.py`
- Frontend source edits: `gmlst/web/frontend/src/*`

## Build Contract

Build frontend assets with:

```bash
pixi run visual-ui-build
```

`gmlst/visual/app.py` serves static files from `gmlst/web/static/` and templates
from `gmlst/web/templates/`.
