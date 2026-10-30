# Cache Management

Where schemes, catalogs, and indexes live, how the cache root is resolved, and what makes offline operation possible.

## Cache management

`gmlst/database/cache.py` is the core cache manager. The cache root is resolved in order: explicit parameter, `GMLST_CACHE_DIR` env var, `$CONDA_PREFIX/share/gmlst` (conda), `$VIRTUAL_ENV/.cache/gmlst` (venv), or `~/.cache/gmlst` as fallback. Each conda or virtualenv environment gets its own isolated cache by default.

Typical layout:

```text
~/.cache/gmlst/
├── <provider>/
│   └── <scheme_name>/
│       ├── <locus>.tfa or <locus>.fasta
│       ├── <scheme_name>.txt or .tsv
│       └── .meta.json
├── _catalog/
│   └── <provider>.json
└── _indexes/
    └── <provider>/
        └── <backend>/
            └── <scheme_name>/
```

### Offline operation

Once a scheme and its indexes are cached, typing can reuse them without re-downloading provider content. The built-in catalog files under `gmlst/data/catalogs/` can also be copied into cache as defaults when no local catalog exists yet.

## Resolving the cache root

```bash
# 1. Explicit flag wins
gmlst scheme list --cache-dir /data/gmlst

# 2. Then GMLST_CACHE_DIR
export GMLST_CACHE_DIR=/data/gmlst

# 3. Then environment-specific defaults
conda run -n gmlst env | grep CONDA_PREFIX   # <prefix>/share/gmlst
echo "$VIRTUAL_ENV"                           # <venv>/.cache/gmlst

# 4. Finally ~/.cache/gmlst
```

Inspect what a command will use:

```bash
gmlst config get GMLST_CACHE_DIR --format json
```

```json
{"name": "GMLST_CACHE_DIR", "value": "/home/me/.cache/gmlst", "source": "default", "is_default": true}
```

## What each directory is for

| Path | Written by | Safe to delete? |
| --- | --- | --- |
| `<root>/<provider>/<scheme>/` | `scheme download`, `scheme update` | Yes; re-download later |
| `<root>/_catalog/<provider>.json` | `scheme list` refresh, `update --force` | Yes; rebuilt on demand |
| `<root>/_indexes/<provider>/<backend>/<scheme>/` | first typing run, `--force-reindex` | Yes; rebuilt automatically |
| `<root>/species_fingerprints.json.gz` | `scheme update-fingerprints` | Yes; the bundled copy remains |

## Offline run example

Prepare once, then disconnect:

```bash
gmlst scheme download saureus_1
gmlst typing mlst -s saureus_1 sample.fna   # builds the index
# later, with no network:
gmlst typing mlst -s saureus_1 another.fna  # scheme and index are reused
```

Typing fails offline only when the scheme or index is missing.
`--force-reindex` never needs the network; it only rebuilds local files.
