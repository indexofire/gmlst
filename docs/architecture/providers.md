# Database Providers

The `Provider` protocol, the runtime registry, and the catalog naming rules that keep scheme names globally unique.

## Database provider architecture

### Provider protocol

`gmlst/database/providers/base.py` defines the `Provider` `Protocol`. Like the aligner contract, this is a structural interface.

Each provider must expose:

- `name`
- `label`
- `list_schemes()`
- `download_scheme()`
- `update_scheme()`

Each listed scheme is represented as `SchemeInfo` from `gmlst/database/providers/base.py`, which carries:

- `scheme_name`
- `display_name`
- `organism`
- `scheme_type`
- `n_loci`
- `provider`
- `extra` for provider-specific fields such as URLs or directory names

### Provider registry

`gmlst/database/providers/__init__.py` builds the runtime registry. It always registers:

- `pubmlst` via `gmlst/database/providers/bigsdb.py`
- `pasteur` via `gmlst/database/providers/bigsdb.py`
- `enterobase` via `gmlst/database/providers/enterobase.py`
- `cgmlst` via `gmlst/database/providers/cgmlst.py`

If `GMLST_PRIVATE_BIGSDB_URL` is set, the registry also creates a private BIGSdb provider entry at runtime.

### Catalog management and global uniqueness

`gmlst/database/cache.py` manages cached provider catalogs under `_catalog/`. It also guarantees that scheme names stay globally unique across providers.

This logic has two layers:

1. `_normalize_scheme_names()` normalizes names within one provider catalog.
2. `save_catalog()` compares those names with all other cached catalogs and bumps numeric suffixes when needed.

That is why names like `spneumoniae_1`, `spneumoniae_2`, and later `spneumoniae_3` can coexist across providers without collisions.

## Minimal provider skeleton

```python
from pathlib import Path

from gmlst.database.providers.base import SchemeInfo


class MyProvider:
    name = "myprovider"
    label = "My Provider"

    def list_schemes(self, scheme_type: str = "mlst") -> list[SchemeInfo]:
        return [
            SchemeInfo(
                scheme_name="myorg_1",
                display_name="My organism MLST",
                organism="My organism",
                scheme_type="mlst",
                n_loci=7,
                provider=self.name,
                extra={"locus_url": "https://example.org/loci"},
            )
        ]

    def download_scheme(self, scheme_name, dest_dir: Path, **kwargs) -> None:
        ...  # write <locus>.tfa, the profile table, and .meta.json

    def update_scheme(self, scheme_name, dest_dir: Path, **kwargs) -> bool:
        ...  # return True when remote content changed
```

## Catalog entry example

After `save_catalog()`, a provider catalog is a JSON array of scheme objects:

```json
[
  {
    "scheme_name": "saureus_1",
    "display_name": "Staphylococcus aureus MLST",
    "organism": "Staphylococcus aureus",
    "scheme_type": "mlst",
    "n_loci": 7,
    "provider": "pubmlst",
    "extra": {
      "scheme_url": "https://rest.pubmlst.org/db/pubmlst_saureus_seqdef/schemes/1"
    }
  }
]
```

## Naming walkthrough

Two providers both publish a 7-locus *S. pneumoniae* scheme:

```text
pubmlst  -> spneumoniae_1
pasteur  -> spneumoniae_2   # save_catalog() bumps the suffix
```

Names are recorded in `name_history`, so a later catalog refresh reuses the same
name even when upstream listing order changes. New schemes take the next free
number; retired names are never reused.
