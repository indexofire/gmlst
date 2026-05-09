from __future__ import annotations

from gmlst.database.providers.bigsdb import _generate_scheme_base_name
from gmlst.database.providers.enterobase import _resolve_enterobase_scheme_name


def test_generate_scheme_base_name_species_abbreviation_preserved() -> None:
    assert _generate_scheme_base_name("Staphylococcus aureus") == "saureus"
    assert _generate_scheme_base_name("Escherichia coli") == "ecoli"
    assert _generate_scheme_base_name("Salmonella enterica") == "senterica"


def test_generate_scheme_base_name_spp_uses_genus_only() -> None:
    assert _generate_scheme_base_name("Neisseria spp.") == "neisseria"
    assert _generate_scheme_base_name("Vibrio spp.") == "vibrio"


def test_generate_scheme_base_name_slash_species_uses_genus_only() -> None:
    assert _generate_scheme_base_name("Campylobacter jejuni/coli") == "campylobacter"
    assert _generate_scheme_base_name("Streptococcus bovis/equinus") == "streptococcus"


def test_enterobase_legacy_vibriospp_alias_still_resolves() -> None:
    assert _resolve_enterobase_scheme_name("vibrio_1", "mlst") == "vibrio_1"
    assert _resolve_enterobase_scheme_name("vibriospp_1", "mlst") == "vibrio_1"
    assert _resolve_enterobase_scheme_name("vibriospp_2", "cgmlst") == "vibrio_2"
