# Configuration

The environment variables that matter most and where temporary files are written.

## Configuration Questions

### Which environment variables matter most?

Common ones are:

- `GMLST_CACHE_DIR`, override cache root (auto-detected from conda/venv by default)
- `GMLST_TMPDIR`, override temporary working directory
- provider URL overrides, such as `GMLST_PUBMLST_BASE_URL`

Example:

```bash
export GMLST_CACHE_DIR="$HOME/.cache/gmlst"
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
```

### Where are temporary files written?

By default they go to the system temporary area. Override with:

```bash
export GMLST_TMPDIR="$PWD/.tmp/gmlst"
```

## Inspect, don't guess

```bash
gmlst config show                         # grouped table, secrets masked
gmlst config get GMLST_CACHE_DIR          # value from env/file/default
gmlst config get GMLST_CACHE_DIR --format json
gmlst config env                          # sourceable export lines
```

| Variable | Default | Use it when |
| --- | --- | --- |
| `GMLST_CACHE_DIR` | environment-specific dir | sharing one cache across environments |
| `GMLST_TMPDIR` | system temp | large batches on a scratch disk |
| `GMLST_PUBMLST_API_KEY` | unset | accessing post-2024 PubMLST data |
| `GMLST_PASTEUR_API_KEY` | unset | accessing post-2024 Pasteur data |
| `GMLST_PRIVATE_BIGSDB_URL` | unset | self-hosted BIGSdb provider |

Secrets are written to `~/.config/gmlst/env.sh` with mode 600 and are masked in
`config show` / `config get` unless `--reveal` is passed.

## Persist a setting

```bash
gmlst config set GMLST_TMPDIR /scratch/gmlst
gmlst config init          # add the source line to your shell rc once
source ~/.config/gmlst/env.sh
```

Provider URL variables are read at import time, so `source` the file before
running gmlst.
