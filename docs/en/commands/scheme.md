[← Command Reference](../commands.md)

# gmlst scheme

Manage scheme catalogs, downloads, updates, and local custom schemes.

## list

List schemes from cached catalogs, local custom schemes, or remote providers.

### Usage
```bash
gmlst scheme list [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-p, --provider [pubmlst\|pasteur\|enterobase\|cgmlst\|local\|all]` | Filter by provider. | `all` |
| `-t, --type [mlst\|cgmlst\|wgmlst\|all]` | Filter by scheme type. | `all` |
| `-n, --name TEXT` | Filter by scheme name. | - |
| `-f, --format [text\|table\|csv\|tsv\|json]` | Output format. | `table` |
| `-a, --available` | Show remotely available schemes, not only cached ones. | `False` |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst scheme list
gmlst scheme list -p pubmlst -t mlst
gmlst scheme list -p local
gmlst scheme list --available -f json
```

### Notes
- Table output adapts to the terminal and is the normal human-readable view.
- `--available` refreshes the view toward provider catalogs so you can inspect schemes that are not yet downloaded locally.
- Listings are filtered through `gmlst/data/blocked_schemes.json`, which hides blocked `scheme_name` values by provider.

---

## download

Download one scheme into the local cache.

### Usage
```bash
gmlst scheme download [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-s, --scheme TEXT` | Scheme name to download. Required. | - |
| `--force` | Re-download even if the scheme is already cached. | `False` |
| `-q, --quiet` | Reduce console output. | `False` |
| `--download-tool [auto\|aria2c\|curl\|wget\|httpx\|requests]` | Download backend. | `auto` |
| `-x, --connections INTEGER` | Number of parallel download connections. | - |
| `--token TEXT` | Authentication token when the provider supports it. | - |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst scheme download -s saureus_1
gmlst scheme download -s ecoli_1 --download-tool aria2c -x 16
gmlst scheme download -s saureus_1 --force
```

### Notes
- Use `--download-tool` to pick the transfer backend explicitly, or leave it on `auto` to let `gmlst` choose.
- `-x, --connections` is most useful for providers that fetch many locus files.
- Blocked schemes are rejected before download.

---

## update

Refresh one cached scheme or refresh provider catalogs.

### Usage
```bash
gmlst scheme update [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-s, --scheme TEXT` | Scheme name to update. | - |
| `-a, --all` | Update all cached schemes. | `False` |
| `-f, --force` | Force catalog or scheme refresh. | `False` |
| `--token TEXT` | Authentication token when the provider supports it. | - |
| `--download-tool [auto\|aria2c\|curl\|wget\|httpx\|requests]` | Download backend. | `auto` |
| `-x, --connections INTEGER` | Number of parallel download connections. | - |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst scheme update
gmlst scheme update -s saureus_1
gmlst scheme update -a --force
```

### Notes
- Without `-s`, `scheme update` refreshes provider catalogs.
- `-a, --all` updates all cached schemes.
- `-s` and `-a` are mutually exclusive. Use one or the other.
- `--force` is the way to refresh catalogs or cached schemes even when local metadata looks current.
- Blocked schemes are rejected before update.

---

## show

Display detailed metadata for one scheme, or fall back to a list view.

### Usage
```bash
gmlst scheme show [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-s, --scheme TEXT` | Scheme name to inspect. | - |
| `-f, --format [text\|table\|csv\|tsv\|json]` | Output format. | `table` |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst scheme show -s saureus_1
gmlst scheme show -s saureus_1 -f json
gmlst scheme show
```

### Notes
- With `-s`, this command shows one scheme in detail, including fields such as `downloaded_at`, `updated_at`, and `n_profiles` when that metadata is available.
- Without `-s`, it prints guidance and falls back to list-style output so you still get a useful catalog view.

---

## create

Create a local custom scheme from extracted novel allele data.

### Usage
```bash
gmlst scheme create [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-t, --type [mlst]` | Scheme type to create. Required. | - |
| `-s, --source TEXT` | Source public scheme used as the base. Required. | - |
| `--data-dir, --datadir DIRECTORY` | Directory containing extracted novel data. Required. | - |
| `--desc TEXT` | Free-text description for the new custom scheme. | - |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data --desc "Lab collection 2024"
```

### Notes
- The custom scheme is named automatically as `custom_1`, `custom_2`, and so on.
- Creation merges the original public scheme content with the extracted novel alleles and profiles, so the result stays typeable against both old and newly discovered data.

---

## update-custom

Extend an existing local custom scheme with new novel allele data.

### Usage
```bash
gmlst scheme update-custom [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-s, --scheme TEXT` | Local custom scheme to update. Required. | - |
| `--data-dir, --datadir DIRECTORY` | Directory containing extracted novel data. Required. | - |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data
```

### Notes
- This command only works with local custom schemes.
- New allele and profile numbering continues from the existing custom scheme instead of restarting from `n1` or `N1`.

---

## export

Export a cached scheme in MST-friendly or original profile format.

### Usage
```bash
gmlst scheme export [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-s, --scheme TEXT` | Scheme name to export. Required. | - |
| `--format [grapetree\|original]` | Export format. Required. | - |
| `-o, --output PATH` | Output file path. Required. | - |
| `--cache-dir PATH` | Override the scheme cache directory. | - |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
gmlst scheme export -s saureus_1 --format original -o saureus_1.txt
```

### Notes
- `grapetree` writes a TSV profile table with an `ST`-style first column that is compatible with GrapeTree workflows.
- `original` writes a copy of the scheme's original profile file.

---

## Provider endpoint environment variables

These variables let you point the scheme commands at alternate BIGSdb endpoints or register a private BIGSdb provider.

| Variable | Purpose |
| --- | --- |
| `GMLST_PUBMLST_BASE_URL` | Override the PubMLST BIGSdb API base URL. |
| `GMLST_PASTEUR_BASE_URL` | Override the Pasteur BIGSdb API base URL. |
| `GMLST_PRIVATE_BIGSDB_URL` | Register a private BIGSdb instance as an additional provider. |
| `GMLST_PRIVATE_BIGSDB_NAME` | Set the provider key used for the private BIGSdb instance. |
| `GMLST_PRIVATE_BIGSDB_LABEL` | Set the display label shown for the private BIGSdb provider. |

Example:

```bash
export GMLST_PUBMLST_BASE_URL="http://127.0.0.1:8000/api/db"
gmlst scheme list -p pubmlst

export GMLST_PRIVATE_BIGSDB_URL="http://127.0.0.1:9000/api/db"
export GMLST_PRIVATE_BIGSDB_NAME="labdb"
gmlst scheme list -p labdb
```
