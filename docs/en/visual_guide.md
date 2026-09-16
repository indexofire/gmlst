# Visual Guide

This guide covers the local visualization workflow in `gmlst`, including the web server, supported input formats, MST building, layout choices, metadata coloring, CLI export, agent-facing summary output, and frontend build details. For export commands that produce compatible profile tables, see [novel_workflow.md](novel_workflow.md) and [commands.md](commands.md).

## Overview

The `visual` module provides a local web interface for turning MLST or cgMLST profile tables into an MST, or minimum spanning tree. It is designed for quick interactive exploration on your own machine.

The web UI is useful when you want to:

- inspect how isolates cluster by allele profile
- color nodes by metadata columns in a TSV file
- compare the effect of missing-value penalties
- export a publication-ready SVG snapshot

The CLI subcommands are useful when you want to:

- build MST payloads without a browser
- produce JSON for downstream tools or AI agents
- get a compact analytical summary readable in one context window

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

### Automatic metadata detection

Columns whose values never look like allele calls (numbers, `LNF`, `~2`, `1?`, `NIPH`, comma-separated multi-alleles) are automatically reclassified as metadata instead of loci. This means a table mixing loci with free-text columns such as `clade`, `source`, or `isolation_site` is handled without manual splitting.

One caveat: purely numeric columns such as `year` are indistinguishable from allele numbers and stay as loci. Pass those through the separate `--metadata` file when needed.

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

### MST Methods

Three MST algorithms are available:

| Method | Algorithm | Optimizes | Best for | Scalability |
|---|---|---|---|---|
| `grapetree_classic` **(default)** | Kruskal MST on Hamming distance | Minimum total Hamming distance | **Large datasets (500+ samples)** | O(n² log n) — 1000 samples in ~37s |
| `grapetree_v2` | Edmonds + branch recrafting (harmonic/eBurst weights) | Composite population-structure metric | **Matching GrapeTree software output** | O(n²) distance matrix — 1000 samples in ~255s, ~3.5GB RAM |
| `edmonds` | Edmonds arborescence + subtree recraft | Minimum total Hamming distance | Small datasets (≤100 samples), deterministic results | O(n³) — **do not use for n>200** |

Measured on 992 samples × 100 loci:

| Method | Time | Peak memory | Total weight |
|---|---|---|---|
| `grapetree_classic` | 37s | 230 MB | 8824 |
| `grapetree_v2` | 255s | 3.5 GB | ~2× classic |
| `edmonds` | >20 min (timeout) | — | — |

Key behavioral differences:

- **edmonds** produces the lowest total weight (0.4% better than classic on small datasets) thanks to its subtree-aware recrafting, but the per-root loop makes it O(n³) and unusable beyond ~200 samples.
- **grapetree_v2** uses a composite metric (normalized distance + harmonic weights + eBurst weights) and produces trees whose total Hamming weight can be up to 2× the minimum, but whose topology better reflects population clustering. It requires O(n²) memory for the distance matrix.
- **grapetree_classic** is a standard Kruskal minimum spanning tree: identical weight to edmonds (within tie-breaking), fast, memory-light. It is the default since v0.1.6.

On simple datasets (≤6 samples, no weight ties), all three methods produce identical trees. On larger or more polymorphic datasets, `grapetree_v2` diverges due to its composite optimization target, and `edmonds` finds marginally better trees than `classic` via recrafting.

## CLI MST Commands

### Piping typing results

The `mst`/`matrix`/`heatmap`/`compare`/`locus-diff` file options accept `-` to read from stdin, so typing output can be piped straight into tree building without a temp file:

```bash
gmlst typing cgmlst -s vparahaemolyticus_3 *.fna --format tsv | gmlst visual mst --input - --format summary
```

### Full JSON output

```bash
gmlst visual mst --input profiles.tsv --metadata meta.tsv --output result.json
```

Produces the complete MST payload (nodes, edges, metadata, mismatch loci) as JSON. For 1000 samples this is ~750KB–1.1MB — **too large to read into an LLM context window** (~290K tokens). Use this for tool-based processing or as the web frontend's data source.

### Summary output (agent-friendly)

```bash
gmlst visual mst --input profiles.tsv --metadata meta.tsv --format summary --output summary.json
```

Produces a compact analytical summary (~7KB for 1000 samples, ~1K tokens) that an AI agent can read directly. The summary contains:

| Field | Content | Analytical value |
|---|---|---|
| `mst_summary` | Edge count, weight min/median/max, zero-weight pairs | Overall tree shape and data quality |
| `clusters` | Connected components (edge weight ≤ `cluster_edge_threshold`), size, dominant metadata, purity | Group structure and clonal complex assignment |
| `cluster_count` | Number of detected clusters (each ≥5 members, capped at 20) | Completeness check for `clusters` |
| `unclustered_samples` | Samples not in any reported cluster | Fraction of unclustered diversity |
| `truncated` | `true` when cluster reporting stopped at the 20-cluster cap | Whether `cluster_count` is a lower bound |
| `top_variable_loci` | Most frequently mismatched loci | Discriminant marker candidates |
| `outliers` | Nodes connected by high-weight edges (> `outlier_weight`) | Divergent/imported strains, data quality flags |
| `method` | MST method that built the tree (`edmonds`, `grapetree_classic`, `grapetree_v2`) | Provenance — required to reproduce the tree |
| `include_missing` | Whether asymmetric missing-token mismatches were counted | Distance-metric provenance |
| `aggregate_profiles` | Whether duplicate profiles were collapsed before tree building | Explains node count vs. sample count |
| `cluster_edge_threshold` | Max edge weight joining samples into one cluster (15) | Interpreting cluster semantics |
| `outlier_weight` | Edge weight above which a node is flagged as outlier (50) | Interpreting outlier flags |
| `suggested_analysis` | Actionable next steps | Analysis roadmap |

Example summary for a 991-sample dataset:

```json
{
  "sample_count": 991,
  "method": "grapetree_classic",
  "include_missing": false,
  "aggregate_profiles": true,
  "cluster_edge_threshold": 15,
  "outlier_weight": 50,
  "mst_summary": {
    "edges": 990, "weight_min": 0, "weight_median": 5,
    "weight_max": 95, "zero_weight_pairs": 72
  },
  "clusters": [
    {"id": "C1", "size": 82, "clade_dominant": "CC08",
     "clade_purity": 1.0,
     "source_composition": {"env": 23, "blood": 22, "water": 19}}
  ],
  "cluster_count": 14,
  "unclustered_samples": 133,
  "truncated": false,
  "top_variable_loci": [["L086", 105], ["L041", 100]],
  "outliers": [{"node": "S0280", "max_edge_weight": 95}],
  "suggested_analysis": ["Check outliers for imported strains", "..."]
}
```

### Other MST-related commands

```bash
# Pairwise distance matrix
gmlst visual matrix --input profiles.tsv --output dist.json

# Allele heatmap payload
gmlst visual heatmap --input profiles.tsv --output heatmap.json

# Compare two typing results
gmlst visual compare --left run1.tsv --right run2.tsv

# Locus-level diff between two samples
gmlst visual locus-diff --input profiles.tsv --left-label s1 --right-label s2
```

## Agent Integration Pattern

For AI agents (or scripts) consuming MST results, use a two-tier approach:

```
Tier 1 (context):  --format summary  →  ~7KB, read directly
Tier 2 (tools):    --format json     →  ~1MB, process with Python
```

A typical agent workflow:

1. Run `gmlst visual mst --format summary` and read the JSON into context.
2. Reason about clusters, outliers, and marker loci from the summary alone.
3. When per-sample or per-edge detail is needed, run a Python script against the full JSON and return only the extracted answer.

This pattern keeps the LLM context small while preserving access to full-resolution data.

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
- `/api/mst` (POST: `{tsv, metadata_tsv?, method?, include_missing?, aggregate_profiles?}`)
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

MST implementation files:

```text
gmlst/visual/mst.py            Public API: build_mst_from_tsv
gmlst/visual/mst_shared.py     Parsing, distances, validation, shared helpers
gmlst/visual/mst_edmonds.py    Edmonds arborescence + subtree recrafting
gmlst/visual/mst_grapetree.py  GrapeTree v2 (composite metric) + classic (Kruskal)
gmlst/visual/mst_summary.py    Compact summary for agent/context consumption
```

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
