"""Tests for globally unique scheme names across provider catalogs.

The abaumannii_1 collision (pubmlst MLST vs cgmlst-source cgMLST)
exposed two defects: ``save_catalog`` renumbered whole name groups
unconditionally (order-dependent name shifts), and stale cached
catalogs written before the uniqueness machinery never got repaired.
"""

from __future__ import annotations

import json
from pathlib import Path

from gmlst.database.cache import DatabaseCache
from gmlst.database.providers import AVAILABLE_PROVIDERS


def _scheme(organism: str, stype: str = "mlst", loci: int = 7) -> dict:
    return {
        "scheme_name": "placeholder",
        "organism": organism,
        "scheme_type": stype,
        "n_loci": loci,
    }


def _names(cache: DatabaseCache, provider: str) -> list[str]:
    return [s["scheme_name"] for s in (cache.load_catalog(provider) or [])]


# ---------------------------------------------------------------------------
# save_catalog: conflict-only renaming
# ---------------------------------------------------------------------------


def test_save_catalog_without_conflict_keeps_normalized_names(
    tmp_path: Path,
) -> None:
    cache = DatabaseCache(tmp_path)
    cache.save_catalog(
        "pubmlst",
        [_scheme("Acinetobacter baumannii"), _scheme("Acinetobacter baumannii")],
    )

    assert _names(cache, "pubmlst") == ["abaumannii_1", "abaumannii_2"]


def test_lower_priority_provider_yields_on_next_load(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    cache.save_catalog(
        "cgmlst",
        [
            _scheme("Acinetobacter baumannii", "cgmlst", 2390),
            _scheme("Acinetobacter baumannii", "cgmlst", 1000),
        ],
    )
    assert _names(cache, "cgmlst") == ["abaumannii_1", "abaumannii_2"]

    # pubmlst (higher priority) saves its own abaumannii_1..3 and keeps
    # them all; the collision is resolved when cgmlst's catalog loads next.
    cache.save_catalog(
        "pubmlst",
        [
            _scheme("Acinetobacter baumannii"),
            _scheme("Acinetobacter baumannii"),
            _scheme("Acinetobacter baumannii"),
        ],
    )

    assert _names(cache, "pubmlst") == ["abaumannii_1", "abaumannii_2", "abaumannii_3"]
    assert _names(cache, "cgmlst") == ["abaumannii_4", "abaumannii_5"]


def test_save_catalog_higher_priority_refresh_keeps_its_names(
    tmp_path: Path,
) -> None:
    cache = DatabaseCache(tmp_path)
    cache.save_catalog("pubmlst", [_scheme("Acinetobacter baumannii")])
    # Simulate a stale lower-priority catalog holding the same name.
    stale = {
        "provider": "cgmlst",
        "schemes": [
            {
                "scheme_name": "abaumannii_1",
                "organism": "Acinetobacter baumannii",
                "scheme_type": "cgmlst",
                "n_loci": 2390,
            }
        ],
    }
    catalog_dir = tmp_path / "_catalog"
    catalog_dir.mkdir(exist_ok=True)
    (catalog_dir / "cgmlst.json").write_text(json.dumps(stale))

    # pubmlst refresh must NOT yield to the lower-priority stale owner.
    cache.save_catalog("pubmlst", [_scheme("Acinetobacter baumannii")])

    assert _names(cache, "pubmlst") == ["abaumannii_1"]


# ---------------------------------------------------------------------------
# load_catalog: self-healing of stale colliding catalogs
# ---------------------------------------------------------------------------


def _write_stale_colliding_catalogs(tmp_path: Path) -> None:
    def payload(provider: str, stype: str, loci: int) -> str:
        return json.dumps(
            {
                "provider": provider,
                "schemes": [
                    {
                        "scheme_name": "abaumannii_1",
                        "organism": "Acinetobacter baumannii",
                        "scheme_type": stype,
                        "n_loci": loci,
                    }
                ],
            }
        )

    catalog_dir = tmp_path / "_catalog"
    catalog_dir.mkdir(exist_ok=True)
    (catalog_dir / "pubmlst.json").write_text(payload("pubmlst", "mlst", 7))
    (catalog_dir / "cgmlst.json").write_text(payload("cgmlst", "cgmlst", 2390))


def test_load_catalog_heals_stale_collision_in_lower_priority_provider(
    tmp_path: Path,
) -> None:
    _write_stale_colliding_catalogs(tmp_path)
    cache = DatabaseCache(tmp_path)

    schemes = cache.load_catalog("cgmlst")

    assert [s["scheme_name"] for s in (schemes or [])] == ["abaumannii_2"]
    on_disk = json.loads((tmp_path / "_catalog" / "cgmlst.json").read_text())
    assert on_disk["schemes"][0]["scheme_name"] == "abaumannii_2"
    # The higher-priority owner keeps its name, on disk untouched.
    pubmlst = json.loads((tmp_path / "_catalog" / "pubmlst.json").read_text())
    assert pubmlst["schemes"][0]["scheme_name"] == "abaumannii_1"


def test_load_catalog_does_not_touch_higher_priority_provider(
    tmp_path: Path,
) -> None:
    _write_stale_colliding_catalogs(tmp_path)
    cache = DatabaseCache(tmp_path)

    schemes = cache.load_catalog("pubmlst")

    assert [s["scheme_name"] for s in (schemes or [])] == ["abaumannii_1"]
    cgmlst = json.loads((tmp_path / "_catalog" / "cgmlst.json").read_text())
    # heals on its own load, not pubmlst's
    assert cgmlst["schemes"][0]["scheme_name"] == "abaumannii_1"


# ---------------------------------------------------------------------------
# bundled default catalogs: copy behavior must converge to unique names
# ---------------------------------------------------------------------------


def test_default_catalogs_copy_to_unique_names_regardless_of_order(
    tmp_path: Path,
) -> None:

    for order in (
        list(AVAILABLE_PROVIDERS),
        list(reversed(AVAILABLE_PROVIDERS)),
    ):
        cache_root = tmp_path / f"cache_{'_'.join(order)}"
        cache_root.mkdir()
        cache = DatabaseCache(cache_root)
        for provider in order:
            assert cache.load_catalog(provider) is not None

        names: dict[str, str] = {}
        for provider in AVAILABLE_PROVIDERS:
            for scheme in cache.load_catalog(provider) or []:
                stype = (scheme.get("scheme_type") or "").lower()
                if stype not in ("mlst", "cgmlst", "wgmlst", "rmlst"):
                    continue
                name = scheme["scheme_name"]
                owner = names.setdefault(name, provider)
                assert owner == provider, (
                    f"'{name}' duplicated between {owner} and {provider} "
                    f"after copying defaults in order {order}"
                )

        pubmlst_names = [s["scheme_name"] for s in cache.load_catalog("pubmlst") or []]
        assert "abaumannii_1" in pubmlst_names
