# Visualization

The Flask backend, MST computation, and Vue frontend, and the contract that keeps visualization decoupled from typing.

## Visualization architecture

The visualization stack has two main layers.

### Backend layer

- `gmlst/visual/cli.py` exposes export and server commands.
- `gmlst/visual/app.py` creates the Flask app and validates JSON payloads.
- `gmlst/visual/mst.py` computes distances, mismatch loci, aggregate nodes, and MST edges from typing output tables.

### Frontend layer

- `gmlst/web/frontend/` contains the Vue 3 + Vite source
- `gmlst/web/templates/` contains HTML templates used by Flask
- `gmlst/web/static/` contains built assets served by Flask

The visual stack is intentionally decoupled from the typing pipeline. It consumes exported TSV or JSON-like payloads instead of calling the alignment pipeline directly.

## Request flow

```text
browser
  -> Vue app (dist assets)
  -> POST /api/mst  {profiles, options}
  -> visual/app.py validates the payload and applies security hooks
  -> visual/mst.py builds distances and the graph
  -> JSON response {nodes, edges, meta}
  -> D3 renders the tree or radial layout
```

## Batch example without the browser

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 --format tsv *.fna > profiles.tsv
gmlst visual mst --input profiles.tsv --format summary
gmlst visual matrix --input profiles.tsv --format tsv -o distances.tsv
gmlst visual locus-diff --input profiles.tsv
```

Because the visual layer only consumes profile tables, it never imports the
typing pipeline. That is the boundary to preserve when adding new commands.
