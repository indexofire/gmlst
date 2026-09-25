"""Tests for mode-aware provider detection (detect_provider prefer_type)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gmlst.database.cache import DatabaseCache


def _catalog(provider: str, entries: list[dict]) -> str:
    return json.dumps({"provider": provider, "schemes": entries})


def _write_catalogs(tmp_path: Path, providers: dict[str, list[dict]]) -> None:
    catalog_dir = tmp_path / "_catalog"
    catalog_dir.mkdir(exist_ok=True)
    for provider, entries in providers.items():
        (catalog_dir / f"{provider}.json").write_text(_catalog(provider, entries))


def _entry(name: str, stype: str, organism: str = "Test test") -> dict:
    return {
        "scheme_name": name,
        "organism": organism,
        "scheme_type": stype,
        "n_loci": 7,
    }


@pytest.fixture(autouse=True)
def _no_self_heal(monkeypatch):
    """Simulate a stale cache: keep same-name entries un-renamed on load."""
    from gmlst.database.cache import DatabaseCache as _C

    monkeypatch.setattr(_C, "_heal_cross_provider_collisions", lambda self, p, s: None)


def test_detect_provider_scan_order_without_hint(tmp_path: Path) -> None:
    _write_catalogs(
        tmp_path,
        {
            "pubmlst": [_entry("abaumannii_1", "mlst", "Acinetobacter baumannii")],
            "cgmlst": [_entry("abaumannii_1", "cgmlst", "Acinetobacter baumannii")],
        },
    )
    cache = DatabaseCache(tmp_path)

    assert cache.detect_provider("abaumannii_1") == "pubmlst"


def test_detect_provider_prefers_matching_type(tmp_path: Path) -> None:
    _write_catalogs(
        tmp_path,
        {
            "pubmlst": [_entry("abaumannii_1", "mlst", "Acinetobacter baumannii")],
            "cgmlst": [_entry("abaumannii_1", "cgmlst", "Acinetobacter baumannii")],
        },
    )
    cache = DatabaseCache(tmp_path)

    assert cache.detect_provider("abaumannii_1", prefer_type="cgmlst") == "cgmlst"
    assert cache.detect_provider("abaumannii_1", prefer_type="mlst") == "pubmlst"


def test_detect_provider_type_hint_outranks_downloaded_mismatch(
    tmp_path: Path,
) -> None:
    _write_catalogs(
        tmp_path,
        {
            "pubmlst": [_entry("abaumannii_1", "mlst", "Acinetobacter baumannii")],
            "cgmlst": [_entry("abaumannii_1", "cgmlst", "Acinetobacter baumannii")],
        },
    )
    downloaded = tmp_path / "cgmlst" / "abaumannii_1"
    downloaded.mkdir(parents=True)
    (downloaded / ".meta.json").write_text("{}")
    cache = DatabaseCache(tmp_path)

    # The downloaded copy belongs to the cgMLST scheme; an mlst-mode lookup
    # must still resolve to the pubmlst MLST entry.
    assert cache.detect_provider("abaumannii_1", prefer_type="mlst") == "pubmlst"
    # And the cgmlst mode happily uses its downloaded copy.
    assert cache.detect_provider("abaumannii_1", prefer_type="cgmlst") == "cgmlst"


def test_detect_provider_hint_with_no_type_match_falls_back(
    tmp_path: Path,
) -> None:
    _write_catalogs(tmp_path, {"pubmlst": [_entry("x_1", "mlst", "Xest xest")]})
    cache = DatabaseCache(tmp_path)

    assert cache.detect_provider("x_1", prefer_type="cgmlst") == "pubmlst"
    assert cache.detect_provider("missing_1", prefer_type="mlst") is None
