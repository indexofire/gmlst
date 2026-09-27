"""Stable scheme names: refreshing a catalog must not renumber known schemes.

Names are derived from organism order on first save; afterwards each scheme
keeps its name keyed by upstream identity (scheme URL / Enterobase directory
/ cgmlst display name). Only schemes new to the catalog get a number, and
retired names are never reused — cached scheme directories are keyed by
name, so a shift would silently point a name at different data.
"""

from __future__ import annotations

import json
from pathlib import Path

from gmlst.database.cache import DatabaseCache


def _bigsdb(organism: str, url_id: int) -> dict:
    return {
        "scheme_name": "placeholder",
        "display_name": f"{organism} scheme {url_id}",
        "organism": organism,
        "scheme_type": "mlst",
        "n_loci": 7,
        "provider": "pubmlst",
        "extra": {"scheme_url": f"https://x.invalid/db/s/schemes/{url_id}"},
    }


def _names(cache: DatabaseCache, provider: str = "pubmlst") -> dict[str, str]:
    return {
        s["extra"]["scheme_url"].rsplit("/", 1)[-1]: s["scheme_name"]
        for s in cache.load_catalog(provider) or []
    }


def test_first_save_numbers_in_upstream_order(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", i) for i in (1, 2)])

    assert _names(cache) == {"1": "ecoli_1", "2": "ecoli_2"}


def test_upstream_insertion_does_not_shift_existing_names(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", i) for i in (1, 2)])

    # upstream adds scheme 9 *before* scheme 2 in listing order
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", i) for i in (1, 9, 2)])

    assert _names(cache) == {"1": "ecoli_1", "2": "ecoli_2", "9": "ecoli_3"}


def test_retired_name_is_not_reused(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", i) for i in (1, 2)])
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", 1)])
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", i) for i in (1, 5)])

    assert _names(cache) == {"1": "ecoli_1", "5": "ecoli_3"}


def test_returning_scheme_gets_its_old_name_back(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", i) for i in (1, 2)])
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", 1)])
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", i) for i in (2, 1)])

    assert _names(cache) == {"1": "ecoli_1", "2": "ecoli_2"}


def test_legacy_catalog_without_history_keeps_its_names(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    legacy = [_bigsdb("Escherichia coli", i) for i in (1, 2)]
    legacy[0]["scheme_name"], legacy[1]["scheme_name"] = "ecoli_2", "ecoli_1"
    path = tmp_path / "catalogs" / "pubmlst.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"provider": "pubmlst", "schemes": legacy}))
    cache_path = cache._catalog_path("pubmlst")
    if cache_path != path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(path.read_text())

    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", i) for i in (1, 2)])

    assert _names(cache) == {"1": "ecoli_2", "2": "ecoli_1"}


def test_cross_provider_rename_is_sticky(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    cgmlst = [
        {
            "scheme_name": "placeholder",
            "display_name": "Escherichia coli cgMLST",
            "organism": "Escherichia coli",
            "scheme_type": "cgmlst",
            "n_loci": 2513,
            "provider": "cgmlst",
            "extra": {},
        }
    ]
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", 1)])
    cache.save_catalog("cgmlst", [dict(s) for s in cgmlst])
    first = cache.load_catalog("cgmlst")[0]["scheme_name"]
    assert first != "ecoli_1"

    # pubmlst gains a second scheme; cgmlst's name must not move
    cache.save_catalog("pubmlst", [_bigsdb("Escherichia coli", i) for i in (1, 7)])
    cache.save_catalog("cgmlst", [dict(s) for s in cgmlst])

    assert cache.load_catalog("cgmlst")[0]["scheme_name"] == first
    assert set(_names(cache).values()) == {"ecoli_1", "ecoli_3"}
