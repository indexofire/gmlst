# Frontend

The Flask/Vue split, the files involved, and the build commands for visualization changes.

## Visual Web Frontend

The visualization feature combines Flask and Vue.

- command entry: `gmlst/visual/cli.py`
- Flask app: `gmlst/visual/app.py` (factory + security hooks)
- JSON API: `gmlst/visual/api_routes.py` (Blueprint), helpers in `gmlst/visual/_api_helpers.py`
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

## Local development loop

```bash
# rebuild the bundle Flask serves
pixi run visual-ui-build

# start the Flask app and open it
pixi run gmlst visual web --open-browser
```

`npm --prefix gmlst/web/frontend run dev` runs the Vite dev server when you need
hot reload; point it at the Flask API during development.

## Contract to keep

- the frontend never imports Python code; it consumes JSON from `/api/mst`
- MST and distance logic stays in `gmlst/visual/mst.py`
- new payload fields are additive and documented in
  `docs/usage/visualization.md`

## Where to make a change

| Change | File |
| --- | --- |
| Node colours, labels, layout controls | `gmlst/web/frontend/src/App.vue` |
| Global styles | `gmlst/web/frontend/src/style.css` |
| API payload or validation | `gmlst/visual/api_routes.py` |
| Distance or MST algorithm | `gmlst/visual/mst.py` |
| CLI export formats | `gmlst/visual/_cli_export.py` |

Do not add npm dependencies without approval, and keep `App.vue`'s `<style>`
block empty; styles belong in `style.css`.
