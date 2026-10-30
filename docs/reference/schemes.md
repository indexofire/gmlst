# Scheme Troubleshooting

Scheme names, download failures, cache locations, blocked entries, and self-hosted BIGSdb endpoints.

## Scheme Management Issues

### `Scheme 'X' not found in catalog`

The name must match the canonical `scheme_name`, not just the organism name.

Check available schemes:

```bash
gmlst scheme list
gmlst scheme list -p pubmlst
gmlst scheme list -p enterobase -t cgmlst
```

Then use the exact scheme name, for example:

```bash
gmlst scheme download -s saureus_1
```

### Scheme download fails

Typical causes:

- temporary network failure
- provider-side outage or rate limit
- a download tool that does not work well in your environment

Try a different download tool:

```bash
gmlst scheme download -s saureus_1 --download-tool curl
gmlst scheme download -s saureus_1 --download-tool requests
gmlst scheme download -s saureus_1 --download-tool wget
```

If you are behind a proxy or firewall, test provider access separately.

### Where is the cache stored?

The cache root is auto-detected: `$CONDA_PREFIX/share/gmlst` in conda environments, `$VIRTUAL_ENV/.cache/gmlst` in virtualenvs, or `~/.cache/gmlst` by default. Each environment gets its own isolated cache.

You can override it:

```bash
export GMLST_CACHE_DIR="$HOME/work/gmlst-cache"
gmlst scheme list
```

To share a cache across conda environments:

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
```

### I want to use a different cache directory for one command

Some commands also support `--cache-dir`.

```bash
gmlst scheme list --cache-dir /tmp/gmlst-cache
gmlst scheme download -s saureus_1 --cache-dir /tmp/gmlst-cache
```

### A scheme is missing from `scheme list`

It may be blocked by `gmlst/data/blocked_schemes.json`.

That file is used to hide or reject selected schemes in list, show, download, and update flows. If you are maintaining the project and need to change block policy, edit that JSON file carefully.

### Provider URL overrides for self-hosted BIGSdb

You can point `gmlst` at a custom BIGSdb host with environment variables.

```bash
export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
export GMLST_PRIVATE_BIGSDB_LABEL="Lab BIGSdb"
gmlst scheme list -p labdb
```

For built-in hosts you can also override base URLs:

```bash
export GMLST_PUBMLST_BASE_URL="https://rest.pubmlst.org/db"
export GMLST_PASTEUR_BASE_URL="https://bigsdb.pasteur.fr/api/db"
```

## Find the canonical name

```bash
gmlst scheme search aureus
gmlst scheme list -n aureus
```

Search matches scheme name, organism, description, and provider. The value in
the first column is what `-s/--scheme` expects.

## Recover from a partial download

```bash
gmlst scheme remove saureus_1 -y
gmlst scheme download saureus_1 --download-tool curl -x 2
```

`-x 2` caps concurrent connections, which helps with providers that return
HTTP 429 under load.

## Inspect a cached scheme

```bash
gmlst scheme show -s saureus_1
gmlst scheme show -s saureus_1 -a          # per-locus allele counts
gmlst scheme show -s saureus_1 -f json     # machine-readable
```

## Share one cache across environments

By default each conda/venv environment gets its own cache. To share downloads:

```bash
# in ~/.config/gmlst/env.sh
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"

gmlst scheme list            # all environments now see the same schemes
```

Run `gmlst config init` once so new shells load the file automatically.
