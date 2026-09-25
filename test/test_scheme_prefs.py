"""Tests for the scheme preferences loader (gmlst.database.scheme_prefs)."""

from __future__ import annotations

import json
from pathlib import Path

from gmlst.database.scheme_prefs import (
    SchemePreference,
    load_scheme_preferences,
    resolve_preferred_scheme,
)


def test_load_reads_bundled_file() -> None:
    prefs = load_scheme_preferences()

    assert prefs, "bundled scheme_preferences.json must load"
    ecoli = [p for p in prefs if p.organism == "Escherichia spp." and p.type == "mlst"]
    assert len(ecoli) == 1
    assert ecoli[0].order == ["escherichia_1", "ecoli_1", "escherichia_2"]


def test_load_ignores_pending_entries(tmp_path: Path) -> None:
    # The bundled file is fully curated now; verify the skip semantics
    # with a synthetic file that still carries an order_suggested entry.
    payload = {
        "entries": [
            {
                "organism": "Pending spp.",
                "type": "mlst",
                "order_suggested": ["pending_1"],
            },
            {"organism": "Done spp.", "type": "mlst", "order": ["done_1"]},
        ]
    }
    path = tmp_path / "scheme_preferences.json"
    path.write_text(json.dumps(payload))

    prefs = load_scheme_preferences(path)

    assert [p.organism for p in prefs] == ["Done spp."]


def test_alias_matching_is_case_insensitive() -> None:
    prefs = load_scheme_preferences()

    matched = [
        p for p in prefs if p.matches_organism("ESCHERICHIA COLI") and p.type == "mlst"
    ]
    assert len(matched) == 1


def test_resolve_preferred_scheme_first_match_wins() -> None:
    pref = SchemePreference(
        organism="Escherichia spp.",
        type="mlst",
        order=["escherichia_1", "ecoli_1", "escherichia_2"],
        aliases=frozenset({"Escherichia", "Escherichia coli"}),
    )
    # escherichia_1 absent from the candidate set
    candidates = ["escherichia_2", "ecoli_1"]

    picked = resolve_preferred_scheme(candidates, "Escherichia coli", "mlst", [pref])
    assert picked == "ecoli_1"


def test_resolve_preferred_scheme_no_entry_returns_none() -> None:
    picked = resolve_preferred_scheme(["x_1", "x_2"], "Vibrio cholerae", "mlst", [])
    assert picked is None


def test_resolve_preferred_scheme_type_mismatch_returns_none() -> None:
    pref = SchemePreference(
        organism="Escherichia spp.",
        type="mlst",
        order=["escherichia_1"],
        aliases=frozenset(),
    )

    picked = resolve_preferred_scheme(
        ["escherichia_1"], "Escherichia spp.", "cgmlst", [pref]
    )
    assert picked is None


def test_provider_qualified_order_items(tmp_path: Path, monkeypatch) -> None:
    pref = SchemePreference(
        organism="Test spp.",
        type="mlst",
        order=[{"name": "test_1", "provider": "cgmlst"}, "test_2"],
        aliases=frozenset(),
    )

    assert pref.order_names == ["test_1", "test_2"]
    assert pref.provider_for("test_1") == "cgmlst"
    assert pref.provider_for("test_2") is None
