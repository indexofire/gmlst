# Visual Guide

This guide covers the local visualization workflow in `gmlst`, including the web server, supported input formats, MST building, layout choices, metadata coloring, and frontend build details. For export commands that produce compatible profile tables, see [novel_workflow.md](novel_workflow.md) and [commands.md](commands.md).

## Overview

The `visual` module provides a local web interface for turning MLST or cgMLST profile tables into an MST, or minimum spanning tree. It is designed for quick interactive exploration on your own machine.

The web UI is useful when you want to:

- inspect how isolates cluster by allele profile
- color nodes by metadata columns in a TSV file
- compare the effect of missing-value penalties
- export a publication-ready SVG snapshot

## Starting the Server

Start the local web app with:

```bash
gmlst visual web --open-browser
```

Common options:

- `--host`, default `127.0.0.1`
- `--port`, default `8787`

Examples:

```bash
# Start on the default local address and open a browser tab
gmlst visual web --open-browser

# Bind to a custom port
gmlst visual web --port 9000

# Bind to all interfaces when you explicitly need remote access
gmlst visual web --host 0.0.0.0 --port 8787
```

Only do that on a trusted network. The visual server is a local convenience interface, not a hardened authenticated deployment target.

Realistic startup log:

```text
Serving MST web app on http://127.0.0.1:8787
```

## Uploading Data

The UI accepts profile tables in two common shapes:

1. `gmlst` profile tables
2. GrapeTree-style files with `#Strain` as the first column

The parser can detect tab-, comma-, and semicolon-delimited input, so TSV is the normal choice but CSV-like exports also work.

That means you can either upload a typing result table or export a scheme in GrapeTree format first.

Example GrapeTree-style header:

```tsv
#Strain	dnaA	ftsZ	gyrB	...
ST1	12	44	109	...
ST2	12	44	111	...
```

Example metadata-aware table shape:

```tsv
#Strain	dnaA	ftsZ	gyrB	Source	Ward	Year
ST1	12	44	109	blood	ICU	2024
ST2	12	44	111	wound	WardA	2024
```

Metadata can either be embedded in the uploaded table or supplied as a separate metadata table keyed by sample ID.

## Building MST

Once a profile table is loaded, the UI builds a minimum spanning tree from the allele differences between samples.

Typical workflow:

1. start `gmlst visual web`
2. upload or paste a TSV profile table
3. choose MST settings
4. render the graph
5. export SVG if needed

Why MST matters here:

- it gives a compact view of nearest-neighbor relationships
- it works well for cgMLST profile tables where pairwise differences are the main signal
- it lets you explore clusters before moving to a larger phylogenetic workflow

## Layout Options

The web UI supports two layouts:

- `tree`
- `radial`

### Tree layout

Use tree layout when you want a more linear, branch-oriented view of cluster structure.

### Radial layout

Use radial layout when you want a central overview and more even distribution around a hub.

A practical rule:

- small or moderately sized outbreak sets often read well in `tree`
- more star-like or dense sets can be easier to inspect in `radial`

## Node Coloring

The UI can color nodes using metadata columns from the uploaded TSV.

Examples of useful coloring fields:

- source type
- hospital ward
- year
- region
- outbreak label

Why coloring helps:

- it reveals whether the allele clusters match known epidemiology
- it makes mixed-source clusters easy to spot
- it turns a plain MST into a more interpretable surveillance figure

## Missing Token Penalty

The visualization workflow includes a missing-token penalty toggle for values such as `LNF`, `NIPH`, and `NIPHEM`, which are special non-exact or missing-style locus tokens that can appear in profile tables.

This affects how missing or special-status loci contribute to distance in the MST.

Use it when you want to compare two views:

- a stricter distance that penalizes missing tokens
- a more tolerant distance that downweights their effect

That comparison is especially helpful when your dataset mixes high-quality assemblies with partial or lower-confidence profiles.

## Exporting

The UI supports SVG export for the rendered graph, and the frontend also exposes JSON and TSV exports for graph/session/table views.

Why SVG export matters:

- it scales cleanly in papers and slides
- it is easy to refine later in vector graphics tools
- it preserves label clarity better than screenshots

## GrapeTree Export CLI

If you want a profile table that is already shaped for MST tools, export it from the CLI first.

```bash
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

That file uses a `#Strain` header and is suitable for the visual workflow.

Example:

```tsv
#Strain	arcC	aroE	glpF	gmk	pta	tpi	yqiL
ST1	1	1	1	1	1	1	1
STN1	n1	7	3	9	4	2	1
```

## Architecture

The visualization stack is split into a small Python web backend and a Vue frontend.

Backend routes:

- `/`
- `/health`
- `/api/mst`
- `/api/distance-matrix`
- `/api/allele-heatmap`
- `/api/locus-diff`
- `/api/compare-results`

Frontend source:

```text
gmlst/web/frontend/
```

Built assets:

```text
gmlst/web/static/visual/dist/
```

In short:

- Flask serves the application and the MST API
- Vue 3 provides the browser UI
- Vite builds the frontend assets used by the packaged server

## Building Frontend

If you want to modify the UI, rebuild the frontend after your changes.

Preferred command:

```bash
pixi run visual-ui-build
```

Direct npm alternative:

```bash
npm --prefix gmlst/web/frontend run build
```

Use the pixi task when you want the project-managed environment. Use the direct npm command when you are working specifically on the frontend stack.

Users who only want the visualization server do not need to build the frontend manually, because the application serves prebuilt assets from `gmlst/web/static/visual/dist/`.
