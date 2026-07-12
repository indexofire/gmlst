# Providers

This document describes the scheme providers supported by `gmlst`, how they are implemented, and where provider-specific behavior lives in the code. For the overall system design, see [`docs/architecture.md`](architecture.md).

## Overview

Providers are the data sources behind `gmlst scheme list`, `gmlst scheme download`, and `gmlst scheme update`. Each provider exposes a catalog of typing schemes and a way to download the allele FASTA files plus profile data needed by the typing pipeline.

`gmlst` supports multiple providers because no single upstream source covers every organism, every naming convention, or every scheme style. The provider layer lets one CLI and one typing engine work across:

- public BIGSdb instances
- direct-download catalogs
- cgMLST-specific bulk ZIP sources
- local custom schemes created from novel allele workflows
- self-hosted BIGSdb deployments

## Provider comparison table

| Provider | Code path | Upstream URL | Main scheme types | Override env var |
|---|---|---|---|---|
| PubMLST | `gmlst/database/providers/bigsdb.py` | `https://rest.pubmlst.org/db` | MLST, some cgMLST, some wgMLST | `GMLST_PUBMLST_BASE_URL` |
| Pasteur | `gmlst/database/providers/bigsdb.py` | `https://bigsdb.pasteur.fr/api/db` | MLST, some cgMLST, some wgMLST | `GMLST_PASTEUR_BASE_URL` |
| Enterobase | `gmlst/database/providers/enterobase.py` | `https://enterobase.warwick.ac.uk/schemes` | MLST, cgMLST, wgMLST, rMLST | none |
| cgMLST.org | `gmlst/database/providers/cgmlst.py` | `https://www.cgmlst.org/ncs/1000` | cgMLST | none |
| Local | `gmlst/commands/scheme.py` + `gmlst/database/cache.py` | local cache only | custom MLST/cgMLST/wgMLST | `GMLST_CACHE_DIR` for cache root |
| Private BIGSdb | `gmlst/database/providers/bigsdb.py` via registry | user-supplied BIGSdb URL | depends on host | `GMLST_PRIVATE_BIGSDB_URL` |

## Shared provider architecture

### Provider interface

All provider implementations follow the `Provider` `Protocol` in `gmlst/database/providers/base.py`. Each provider must define:

- `name`
- `label`
- `list_schemes()`
- `download_scheme()`
- `update_scheme()`

`SchemeInfo` from the same file is the normalized scheme metadata object used across the CLI and catalog cache.

### Registry and runtime selection

`gmlst/database/providers/__init__.py` creates the runtime registry. `gmlst/database/cache.py` calls `get_provider()` from that registry whenever it needs to list, download, or update schemes.

### Catalog caching

Provider catalogs are cached as JSON in:

```text
~/.cache/gmlst/_catalog/<provider>.json
```

The cache manager in `gmlst/database/cache.py` also rewrites names if necessary so scheme names remain globally unique across providers.

## PubMLST

### Summary

- Provider key: `pubmlst`
- Registry path: `gmlst/database/providers/__init__.py`
- Implementation: `gmlst/database/providers/bigsdb.py`
- Default base URL: `https://rest.pubmlst.org/db`
- Override: `GMLST_PUBMLST_BASE_URL`

### API model

PubMLST is accessed through the BIGSdb REST interface implemented by `BigSdbProvider` in `gmlst/database/providers/bigsdb.py`.

The provider flow is:

1. query the BIGSdb root URL for organism groups
2. discover `seqdef` databases for each organism
3. query `/schemes` for scheme metadata
4. resolve loci and profile URLs
5. download allele FASTA files from `<locus_url>/alleles_fasta`
6. download profile data from `profiles_csv` when available

### Scheme coverage

PubMLST is the main source for classic MLST coverage and includes many organism-specific schemes. Scheme types are inferred in `gmlst/database/providers/bigsdb.py` from BIGSdb descriptions and locus counts.

### Naming behavior

Within the provider, `BigSdbProvider.list_schemes()` generates short names from normalized organism names. Global uniqueness is then enforced by `DatabaseCache.save_catalog()` in `gmlst/database/cache.py`.

### Authentication notes

PubMLST runs on the BIGSdb platform. Since **1 January 2025**, PubMLST requires authentication to access alleles, profiles, and isolates added after 31 December 2024. Pre-2025 data remains accessible anonymously.

#### How to obtain a PubMLST API key

1. Register an account at [pubmlst.org](https://pubmlst.org)
2. Log in and navigate to your profile page
3. Go to **Preferences** → **API keys**
4. Click **Create new API key**
5. Copy the generated key (format: `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`)

- **Auth method**: Personal API Key, passed as `X-API-Key: <key>` header (note: BIGSdb documents both `Authorization: Bearer` and OAuth, but PubMLST's actual server only accepts `X-API-Key`)

#### How to use the API key in gmlst

```bash
gmlst config set GMLST_PUBMLST_API_KEY your-key-here
source ~/.config/gmlst/env.sh
```

All PubMLST requests will include the `X-API-Key` header automatically. Without a key, only pre-2025 data is accessible (truncated profiles and alleles).

#### References

- [BIGSdb API authentication docs](https://bigsdb.readthedocs.io/en/latest/rest.html#api-oauth)
- [PubMLST data access policy change](http://pubmlst.org/change-data-access-policy)

## Pasteur

### Summary

- Provider key: `pasteur`
- Registry path: `gmlst/database/providers/__init__.py`
- Implementation: `gmlst/database/providers/bigsdb.py`
- Default base URL: `https://bigsdb.pasteur.fr/api/db`
- Override: `GMLST_PASTEUR_BASE_URL`

### API model

Pasteur uses the same `BigSdbProvider` implementation as PubMLST. The code path is shared because both sites expose the same BIGSdb REST shape.

### Scheme coverage

Pasteur provides MLST and some larger schemes. Classification into `mlst`, `cgmlst`, and `wgmlst` is still done by `gmlst/database/providers/bigsdb.py` based on scheme description keywords.

### Name mapping

`gmlst/database/providers/bigsdb.py` loads organism name mappings from `gmlst/data/organism_mapping.json` so catalog entries can use consistent organism labels across providers.

### Authentication notes

Pasteur runs the same BIGSdb platform as PubMLST and has adopted the **same data access policy**: since **1 January 2025**, data curated after 31 December 2024 requires authentication. The auth mechanism is identical to PubMLST (`X-API-Key` header).

#### How to obtain a Pasteur BIGSdb API key

The process requires human review and takes longer than PubMLST:

**Step 1: Create an account**

Register at [bigsdb.pasteur.fr/register/](https://bigsdb.pasteur.fr/register/)

**Step 2: Register to specific databases**

After logging in, register to each species database you need access to (e.g. Bordetella, E. coli, Listeria). API key access is **only granted for databases you have registered to**.

**Step 3: Request the API key by email**

Contact the Pasteur team with the required information:

| Your sector | Contact email |
|---|---|
| Academic / Non-profit / Public health | [bigsdb@pasteur.fr](mailto:bigsdb@pasteur.fr) |
| Commercial / For-profit | [bigsdb-policy@pasteur.fr](mailto:bigsdb-policy@pasteur.fr) |

Email template:

```
Subject: API Key Request for gmlst typing pipeline

BIGSdb-Pasteur Username: <your username>
Affiliation: <your institution>
Email address: <your email>
Sector: Academic / Non-profit
Database(s) you intend to use:
  - <species 1, e.g. Bordetella>
  - <species 2, e.g. E. coli>
Motivation:
  I use gmlst (https://github.com/indexofire/gmlst), a bacterial genome
  typing CLI tool, for automated MLST/cgMLST typing. I need API access
  to download scheme allele sequences and ST profiles for integration
  into our typing pipeline.
```

The team will review your request and respond with the API key (typically within a few business days).

**Step 4: Set the key in gmlst**

```bash
gmlst config set GMLST_PASTEUR_API_KEY your-pasteur-key
source ~/.config/gmlst/env.sh
```

Verify:

```bash
gmlst config get GMLST_PASTEUR_API_KEY
```

After this, all Pasteur requests will include the `X-API-Key` header automatically. Without a key, only pre-2025 data is accessible.

#### References

- [Pasteur API key request page](https://bigsdb.pasteur.fr/requesting-api-key/)
- [Pasteur data access policy](https://bigsdb.pasteur.fr/news/novel-data-access-policy/)
- [BIGSdb API authentication docs](https://bigsdb.readthedocs.io/en/latest/rest.html#api-oauth)

## Enterobase

### Summary

- Provider key: `enterobase`
- Implementation: `gmlst/database/providers/enterobase.py`
- Base URL: `https://enterobase.warwick.ac.uk/schemes`

### Delivery model

Enterobase is not implemented through BIGSdb in this project. Instead, `gmlst/database/providers/enterobase.py` uses direct HTTP downloads from the Enterobase open scheme directory at `https://enterobase.warwick.ac.uk/schemes/`.

### Scheme discovery

`list_schemes()` dynamically scans the Enterobase `/schemes/` HTTP directory index to discover available scheme directories. This means new schemes added by Enterobase are automatically visible after `gmlst scheme update --force` without requiring a code update. If the network is unavailable, the provider falls back to a static `_SCHEME_MAP` defined in the source file.

Scheme directory names are used directly as `scheme_name` in the catalog (e.g. `Salmonella.Achtman7GeneMLST`). The catalog's `extra.directory` field carries this directory name through to `download_scheme()` and `update_scheme()` so downloads always resolve to the correct remote path.

### Scheme coverage

The Enterobase provider discovers schemes across multiple organisms including:

- *Escherichia coli* / *Shigella*
- *Salmonella enterica*
- *Yersinia enterocolitica*
- *Klebsiella pneumoniae*
- *Streptococcus pneumoniae*
- *Vibrio* spp.
- *Moraxella catarrhalis*
- *Clostridium botulinum*
- *Photorhabdus luminescens*

It supports MLST, cgMLST, wgMLST, and rMLST scheme types depending on what directories are available on the server.

### Download format

The provider downloads per-locus `.fasta.gz` files, decompresses them to `.tfa`, downloads `profiles.list.gz`, and writes metadata into `.meta.json`.

### Token note

Enterobase uses a **completely different authentication system** from PubMLST/Pasteur BIGSdb. Its REST API has always required authentication.

- **Auth method**: API Token, passed as `Authorization: Basic <token>` header (note: Basic auth, not Bearer — different from BIGSdb)
- **How to obtain**:
  1. Register at [enterobase.warwick.ac.uk](https://enterobase.warwick.ac.uk)
  2. **Email enterobase@warwick.ac.uk** requesting API access for your database of interest
  3. Token is displayed under "Important information" in the database dashboard
- **API docs**: [Enterobase API getting started](https://enterobase.readthedocs.io/en/latest/api/api-getting-started.html)
- **Usage restrictions**:
  - Add a 1–2 second pause between API requests
  - Do **not** perform large-scale bulk downloads through the API
  - rMLST allele data is copyrighted by University of Oxford and **cannot be downloaded**
  - Commercial use requires explicit licensing from University of Warwick

`gmlst/commands/scheme.py` exposes a `--token` option with `ENTEROBASE_TOKEN` as an environment fallback. The token is passed through the cache layer to the Enterobase provider, which includes it as `Authorization: Basic <token>` in all HTTP requests (directory listings, locus counts, and file downloads).

> **Note**: Some Enterobase scheme directories (e.g. `Vibrio.Lan7Gene`) return HTTP 403 even without authentication requirements — this is a server-side restriction on specific directories. In such cases, use the equivalent scheme from another provider (e.g. PubMLST).

## cgMLST.org

### Summary

- Provider key: `cgmlst`
- Implementation: `gmlst/database/providers/cgmlst.py`
- Catalog definitions: `gmlst/database/providers/cgmlst_schemes.py`
- Base URL: `https://www.cgmlst.org/ncs/1000`

### Delivery model

`gmlst/database/providers/cgmlst.py` does not use a REST catalog API. Instead it uses a pre-defined local catalog in `gmlst/database/providers/cgmlst_schemes.py`, then downloads a bulk ZIP from the schema page and extracts locus FASTA files.

### Scheme coverage

This provider is focused on cgMLST. Scheme metadata includes `schema_id`, display labels, organism names, and expected locus counts.

### Integrity checks

After extraction, the provider checks the reported locus count from the schema status page and fails if the download appears incomplete.

## Local provider

### What it is

The `local` provider is not implemented as a remote provider class. It is a local catalog namespace managed through `gmlst/commands/scheme.py` and stored by `gmlst/database/cache.py`.

### Where data lives

Custom schemes are created under the cache root, usually:

```text
~/.cache/gmlst/local/custom_<n>/
```

Each local scheme directory contains:

- per-locus allele FASTA files
- a profile file such as `custom_1.txt`
- `.meta.json`

### How local schemes are created

`gmlst scheme create` in `gmlst/commands/scheme.py` builds local schemes from extracted novel alleles and profiles. Metadata helpers live in `gmlst/novel/service.py`.

### Listing local schemes

Local schemes are included when catalog lookups include `local`, for example in `gmlst/commands/typing_scheme.py` and parts of `gmlst/commands/scheme.py`.

## Private BIGSdb

### Purpose

Private BIGSdb support lets `gmlst` talk to a self-hosted BIGSdb instance without adding a separate provider module.

### Configuration

`gmlst/database/providers/__init__.py` creates the provider dynamically when:

- `GMLST_PRIVATE_BIGSDB_URL` is set

Optional related variables are:

- `GMLST_PRIVATE_BIGSDB_NAME`
- `GMLST_PRIVATE_BIGSDB_LABEL`

### Behavior

The private provider still uses `BigSdbProvider` from `gmlst/database/providers/bigsdb.py`. That means it inherits the same scheme discovery, type classification, and download flow as PubMLST and Pasteur.

## Provider-specific notes

### Download backends

`gmlst/database/download.py` supports multiple download tools. The provider layer can use:

- `aria2c` (default, with retry: `--max-tries=5 --retry-wait=3`)
- `curl`
- `wget`
- Python `httpx`
- Python `requests`

Command-level options can select the tool explicitly, and provider code passes the requested download backend through.

### Parallel downloads

Providers that download many locus files, especially BIGSdb and Enterobase, use batch download helpers from `gmlst/database/providers/base.py` and `gmlst/database/download.py`. The CLI can pass `-x` or `--connections` (default: 4) to control connection count. Per-server connections are capped at 2 to avoid triggering upstream rate limits (HTTP 429).

### Catalog lifecycle

Catalogs are the central index that connects scheme names to provider data. The full lifecycle is:

1. **Discovery**: Each provider's `list_schemes()` queries its upstream source:
   - PubMLST/Pasteur: BIGSdb REST API (`GET /db` → schemes → loci)
   - Enterobase: dynamic HTTP scrape of `/schemes/` directory index
   - cgMLST.org: static catalog in `gmlst/database/providers/cgmlst_schemes.py`
2. **Blocking**: Schemes listed in `gmlst/data/blocked_schemes.json` are filtered out during `save_catalog()`, so the cached catalog JSON never contains blocked entries. Blocking matches both `scheme_name` and `extra.directory`.
3. **Caching**: `DatabaseCache.save_catalog()` writes `_catalog/<provider>.json` with globally unique scheme names (cross-provider suffix de-duplication).
4. **Display**: `gmlst scheme list` reads from the cached catalog JSON. No network calls during listing.
5. **Refresh**: `gmlst scheme update --force` re-runs `list_schemes()` for all providers and overwrites the catalog JSON. This is the only way to pick up newly added upstream schemes.

### Global uniqueness of scheme names

Provider names are not enough by themselves because several providers can host schemes for the same organism. `DatabaseCache.save_catalog()` in `gmlst/database/cache.py` normalizes names within one provider and then bumps suffixes across providers to keep names unique. For Enterobase, the directory name (e.g. `Salmonella.Achtman7GeneMLST`) is used directly as the scheme name, so there is no ambiguity between the catalog and the download path.

### Enterobase auth model

Enterobase has two data access paths:

| Path | URL | Auth | Coverage |
|---|---|---|---|
| `/schemes/` directory | `enterobase.warwick.ac.uk/schemes/` | None (open) | 24 scheme directories, daily updated |
| REST API v2.0 | `enterobase.warwick.ac.uk/api/v2.0/` | Token (Basic auth) | All website databases (M. tuberculosis, Enterococcus, etc.) |

The current implementation uses the `/schemes/` directory exclusively. The `--token` option and `ENTEROBASE_TOKEN` environment variable are wired through to all HTTP requests as `Authorization: Basic <token>` headers. When a token is provided, it is sent with every Enterobase HTTP request (directory listings, locus counts, file downloads).

API-based scheme download (for species not in `/schemes/`) is planned for a future release.

### Enterobase data freshness

The `/schemes/` directory is updated daily by an Enterobase automated script. All allele FASTA and profile files carry the current date, even for species that are not featured on the Enterobase website UI (e.g. Streptococcus, Photorhabdus, Clostridium botulinum). The directory-level modification date shown in the HTTP index is the directory creation date and can be years old; the individual files inside are regenerated daily.

## Blocked schemes

Blocked schemes are controlled through `gmlst/data/blocked_schemes.json` and loaded by `_load_blocked_schemes()` in both `gmlst/commands/common.py` (CLI layer) and `gmlst/database/cache.py` (data layer).

Filtering is applied at two layers:

1. **Catalog write time** (`save_catalog`): Blocked schemes are removed before the catalog JSON is written, so the cached catalog is always clean.
2. **CLI display time** (`scheme list`, `scheme search`, `scheme download`): A defense-in-depth filter catches any blocked entries that might exist in old cached catalogs from before the write-time filter was added.

Blocking matches both `scheme_name` (e.g. `salmonella_1`) and `extra.directory` (e.g. `clostridium.Griffiths_MLST`), so it works regardless of cross-provider renumbering.

Use cases for blocking:

- Deprecated or abandoned schemes (e.g. `clostridium.Griffiths_MLST` — last curated 2019, empty profiles)
- Problematic catalogs with known data quality issues
- Entries known to be unsuitable for standard workflows

## Scheme metadata (.meta.json)

Each downloaded scheme directory contains a `.meta.json` file with download metadata:

```json
{
    "scheme": "saureus_1",
    "provider": "pubmlst",
    "scheme_type": "mlst",
    "downloaded_at": "2026-07-10T12:00:00Z",
    "loci": ["arcC", "aroE", "glpF", "gmk", "pta", "tpi", "yqiL"],
    "profiles_remote": { "etag": "...", "last_modified": "..." },
    "locus_remote": { "arcC": { "etag": "...", "last_modified": "..." } }
}
```

The metadata records the download/update timestamp and remote file headers (ETag, Last-Modified) for incremental update detection. Allele counts per locus are not currently stored; this is planned for a future release to enable post-download validation.

## Related documentation

- [`docs/architecture.md`](architecture.md), system design and layering
- [`docs/commands.md`](commands.md), command syntax and options
- [`docs/quickstart.md`](quickstart.md), basic end-to-end usage
