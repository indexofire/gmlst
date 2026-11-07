"""Scheme display/compute classification.

Display type drives `scheme list -t`; compute type drives `typing`.
Lineage-scoped MLST-like schemes are `other` + `mlst`; non-typing panels are
`other` + empty.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from rich.console import Console

from gmlst.commands.typing_scheme import (
    resolve_scheme_type,
    validate_scheme_mode,
)
from gmlst.database.cache import DatabaseCache
from gmlst.database.providers.bigsdb import (
    _classify_scheme_type,
    _compute_scheme_type,
)


@pytest.mark.parametrize(
    ("description", "display", "compute"),
    [
        ("Staphylococcus aureus MLST", "mlst", "mlst"),
        ("Campylobacter jejuni/coli MLST", "mlst", "mlst"),
        ("Neisseria spp. eMLST (20 locus partial genes)", "mlst", "mlst"),
        ("Blastocystis spp. ST3 MLST", "other", "mlst"),
        ("Vibrio cholerae MLST (O1 and O139)", "other", "mlst"),
        ("Bordetella pertussis Autotransporters", "other", ""),
        ("Klebsiella pneumoniae Virulence genes", "other", ""),
        ("Plasmid MLST IncI1 MLST", "other", ""),
        ("Listeria monocytogenes PCR-serogroup", "other", ""),
        ("Salmonella enterica cgMLST", "cgmlst", "cgmlst"),
        ("Escherichia coli wgMLST", "wgmlst", "wgmlst"),
    ],
)
def test_classification(description: str, display: str, compute: str) -> None:
    assert _classify_scheme_type(description) == display
    assert _compute_scheme_type(description) == compute


def test_package_catalogs_have_no_mislabelled_mlst() -> None:
    root = Path(__file__).resolve().parents[1] / "gmlst" / "data" / "catalogs"
    for provider in ("pubmlst", "pasteur"):
        data = json.loads((root / f"{provider}.json").read_text())
        for scheme in data["schemes"]:
            expected = _classify_scheme_type(scheme["display_name"])
            assert scheme["scheme_type"] == expected, scheme["scheme_name"]
            assert scheme.get("compute_type") == _compute_scheme_type(
                scheme["display_name"]
            ), scheme["scheme_name"]


def test_lineage_scoped_mlst_is_other_with_mlst_compute() -> None:
    root = Path(__file__).resolve().parents[1] / "gmlst" / "data" / "catalogs"
    data = json.loads((root / "pubmlst.json").read_text())
    by_name = {s["scheme_name"]: s for s in data["schemes"]}
    for name in ("blastocystis_1", "blastocystis_2", "vcholerae_2"):
        assert by_name[name]["scheme_type"] == "other"
        assert by_name[name]["compute_type"] == "mlst"


def test_non_typing_pasteur_panel_is_other_without_compute() -> None:
    root = Path(__file__).resolve().parents[1] / "gmlst" / "data" / "catalogs"
    data = json.loads((root / "pasteur.json").read_text())
    by_name = {s["scheme_name"]: s for s in data["schemes"]}
    for name in ("bpertussis_2", "lmonocytogenes_4", "kpneumoniae_20"):
        assert by_name[name]["scheme_type"] == "other"
        assert by_name[name]["compute_type"] == ""


def test_load_catalog_reclassifies_legacy_entries(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    path = cache._catalog_path("pubmlst")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "provider": "pubmlst",
                "schemes": [
                    {
                        "scheme_name": "blastocystis_1",
                        "display_name": "Blastocystis spp. ST3 MLST (mlst)",
                        "organism": "Blastocystis spp.",
                        "scheme_type": "mlst",
                        "n_loci": 5,
                        "provider": "pubmlst",
                        "extra": {},
                    },
                    {
                        "scheme_name": "bpertussis_2",
                        "display_name": "Bordetella pertussis Autotransporters",
                        "organism": "Bordetella pertussis",
                        "scheme_type": "mlst",
                        "n_loci": 5,
                        "provider": "pubmlst",
                        "extra": {},
                    },
                ],
            }
        )
    )
    loaded = {s["scheme_name"]: s for s in cache.load_catalog("pubmlst") or []}
    assert loaded["blastocystis_1"]["scheme_type"] == "other"
    assert loaded["blastocystis_1"]["compute_type"] == "mlst"
    assert loaded["bpertussis_2"]["scheme_type"] == "other"
    assert loaded["bpertussis_2"]["compute_type"] == ""


class _FakeCache:
    def __init__(self, entry: dict) -> None:
        self.entry = entry

    def load_catalog(self, provider: str):
        return [self.entry] if provider == "pubmlst" else []


def test_resolve_scheme_type_prefers_compute_type() -> None:
    cache = _FakeCache(
        {
            "scheme_name": "blastocystis_1",
            "scheme_type": "other",
            "compute_type": "mlst",
        }
    )
    assert resolve_scheme_type(cache, "blastocystis_1", None) == "mlst"


def test_resolve_scheme_type_returns_other_for_non_typeable() -> None:
    cache = _FakeCache(
        {
            "scheme_name": "bpertussis_2",
            "scheme_type": "other",
            "compute_type": "",
        }
    )
    assert resolve_scheme_type(cache, "bpertussis_2", None) == "other"


def test_validate_rejects_non_typeable_other() -> None:
    console = Console(file=io.StringIO())
    with pytest.raises(SystemExit):
        validate_scheme_mode(
            scheme="bpertussis_2",
            scheme_type="other",
            mode="mlst",
            err_console=console,
        )
