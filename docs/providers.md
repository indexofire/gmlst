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

The current source tree documents and implements PubMLST as an open BIGSdb REST provider. There is no dedicated PubMLST token configuration path in `gmlst/database/providers/bigsdb.py` today. If you need authenticated BIGSdb access, the supported route in this codebase is the private BIGSdb mechanism described below.

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

## Enterobase

### Summary

- Provider key: `enterobase`
- Implementation: `gmlst/database/providers/enterobase.py`
- Base URL: `https://enterobase.warwick.ac.uk/schemes`

### Delivery model

Enterobase is not implemented through BIGSdb in this project. Instead, `gmlst/database/providers/enterobase.py` uses direct HTTP downloads from known scheme directories.

The provider maintains an internal `_SCHEME_MAP` that maps public scheme names such as `ecoli_1` or `senterica_2` to upstream directory names.

### Scheme coverage

The implementation includes well-known Enterobase organisms and schemes such as:

- *Escherichia coli*
- *Salmonella enterica*
- *Yersinia enterocolitica*
- *Klebsiella pneumoniae*
- *Streptococcus pneumoniae*
- *Vibrio* spp.

It supports MLST, cgMLST, wgMLST, and some rMLST-style entries depending on the mapped directory.

### Download format

The provider downloads per-locus `.fasta.gz` files, decompresses them to `.tfa`, downloads `profiles.list.gz`, and writes metadata into `.meta.json`.

### Token note

`gmlst/commands/scheme.py` exposes a `--token` option with `ENTEROBASE_TOKEN` as an environment fallback for Enterobase-related commands. The current `gmlst/database/providers/enterobase.py` implementation is primarily direct HTTP download based, so token handling is limited in practice.

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

- `aria2c`
- `curl`
- `wget`
- Python `httpx`
- Python `requests`

Command-level options can select the tool explicitly, and provider code passes the requested download backend through.

### Parallel downloads

Providers that download many locus files, especially BIGSdb and Enterobase, use batch download helpers from `gmlst/database/providers/base.py` and `gmlst/database/download.py`. The CLI can pass `-x` or `--connections` to control connection count.

### Catalog freshness

Provider catalogs are cached. `gmlst scheme update` refreshes those cached catalogs through `DatabaseCache.update_catalog()` in `gmlst/database/cache.py`.

### Global uniqueness of scheme names

Provider names are not enough by themselves because several providers can host schemes for the same organism. `DatabaseCache.save_catalog()` in `gmlst/database/cache.py` normalizes names within one provider and then bumps suffixes across providers to keep names unique.

### Enterobase and auth

The CLI exposes token options for Enterobase-related commands, but the current provider implementation is still centered on direct HTTP download paths. If you rely on a protected Enterobase workflow, verify the remote endpoint requirements in your environment.

## Blocked schemes

Blocked schemes are controlled through `gmlst/data/blocked_schemes.json` and loaded by `_load_blocked_schemes()` in `gmlst/commands/common.py`.

The filter is applied in `gmlst/commands/scheme.py` when listing schemes and when resolving schemes for download or update.

This mechanism is used to hide entries that should not be exposed to normal users, for example:

- deprecated schemes
- problematic catalogs
- entries known to be unsuitable for standard workflows

## Related documentation

- [`docs/architecture.md`](architecture.md), system design and layering
- [`docs/commands.md`](commands.md), command syntax and options
- [`docs/quickstart.md`](quickstart.md), basic end-to-end usage
