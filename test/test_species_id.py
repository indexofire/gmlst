"""Unit tests for gmlst.core.species_id (species fingerprint logic)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from gmlst.core.species_id import (
    DETECT_MARGIN_FACTOR,
    DETECT_MIN_CONTAINMENT,
    FINGERPRINT_K,
    FINGERPRINT_SAMPLE_RATE,
    build_fingerprints,
    detect_species,
    fingerprints_path,
    is_unique_detection,
    load_fingerprints,
    save_fingerprints,
    schemes_for_organism,
    sketch_fasta_sample,
    sketch_sequence,
)
from gmlst.database.schema import Scheme


class _FakeCatalogCache:
    """Cache stub exposing only the catalog API used by species_id."""

    def __init__(self, catalogs: dict[str, list[dict[str, Any]]]) -> None:
        self._catalogs = catalogs
        self.root = Path(".")

    def load_catalog(self, provider: str) -> list[dict[str, Any]] | None:
        return self._catalogs.get(provider)


# ---------------------------------------------------------------------------
# sketch_sequence
# ---------------------------------------------------------------------------


def test_sketch_sequence_is_deterministic_and_case_insensitive() -> None:
    seq = "ACGTACGTACGTTTACGGGCATA"
    assert sketch_sequence(seq) == sketch_sequence(seq)
    assert sketch_sequence(seq.lower()) == sketch_sequence(seq)


def test_sketch_sequence_skips_kmers_with_non_acgt_chars() -> None:
    # The GTN window crossing N is dropped; the surviving ACG/CGT windows
    # collapse to one strand-neutral canonical code.
    assert sketch_sequence("ACGTN", k=3, sample_rate=1) == sketch_sequence(
        "ACGT", k=3, sample_rate=1
    )
    assert len(sketch_sequence("AANAA", k=3, sample_rate=1)) == 0


def test_sketch_sequence_is_strand_neutral() -> None:
    seq = "AACCTTAGGCA"
    reverse_complement = "TGCCTAAGGTT"
    assert sketch_sequence(seq, k=3, sample_rate=1) == sketch_sequence(
        reverse_complement, k=3, sample_rate=1
    )


def test_sketch_sequence_samples_every_nth_kmer() -> None:
    seq = "ACCTGATCGGTACAGCTAAGGCTT" * 3
    dense = sketch_sequence(seq, k=5, sample_rate=1)
    sampled = sketch_sequence(seq, k=5, sample_rate=3)
    assert sampled < dense  # proper subset: only codes divisible by 3


def test_sketch_containment_is_offset_invariant() -> None:
    gene = "ACCTGATCGGTACAGCTAAGGCTTGCAATCGGTACAGGCTTAACCGGATCCAATG" * 3
    flank = "TTGCAAGGCATTGCAAGGCATTGCAA" * 5
    for offset in range(7):
        genome = flank + "G" * offset + gene + flank
        assert sketch_sequence(gene) <= sketch_sequence(genome)


def test_sketch_sequence_distinct_sequences_share_little() -> None:
    first = "ACCTGA" * 40
    second = "TTGCAA" * 40 + "ACCTGA"
    overlap = sketch_sequence(first, k=21) & sketch_sequence(second, k=21)
    assert len(overlap) < 5


def test_sketch_sequence_rejects_invalid_params() -> None:
    with pytest.raises(ValueError):
        sketch_sequence("ACGT", k=0)
    with pytest.raises(ValueError):
        sketch_sequence("ACGT", sample_rate=0)


def test_sketch_fasta_sample_caps_total_bases(tmp_path: Path) -> None:
    fasta = tmp_path / "genome.fna"
    first = "A" * 50 + "CGT" * 50
    second = "TTAAGGCCTTAGGCAATCGGTCAAGGTTAC" * 7
    fasta.write_text(">c1\n" + first + "\n>c2\n" + second + "\n")
    full = sketch_fasta_sample(fasta, cap_bp=10_000)
    capped = sketch_fasta_sample(fasta, cap_bp=60)  # stops after c1 (200 bp)
    assert full
    assert capped < full


def test_sketch_fasta_sample_accepts_str_path(tmp_path: Path) -> None:
    fasta = tmp_path / "genome.fna"
    seq = "TTAAGGCCTTAGGCAATCGGTCAAGGTTAC" * 7  # varied k-mer content
    fasta.write_text(">c1\n" + seq + "\n")

    from_path = sketch_fasta_sample(fasta)
    from_str = sketch_fasta_sample(str(fasta))

    assert from_path  # sanity: fixture yields sampled hashes
    assert from_str == from_path


# ---------------------------------------------------------------------------
# detect_species / is_unique_detection
# ---------------------------------------------------------------------------


def _fingerprint(organism: str, hashes: list[int]) -> dict[str, Any]:
    return {
        "organism": organism,
        "k": FINGERPRINT_K,
        "sample_rate": FINGERPRINT_SAMPLE_RATE,
        "hashes": hashes,
        "source_scheme": "x_1",
    }


def test_detect_species_perfect_containment_wins() -> None:
    reference = list(range(1, 101))
    other = list(range(1001, 1201))
    fingerprints = [
        _fingerprint("Escherichia coli", other),
        _fingerprint("Bordetella pertussis", reference),
    ]
    ranked = detect_species(set(reference) | {9001, 9002}, fingerprints)
    assert ranked[0] == ("Bordetella pertussis", 1.0)
    assert "Escherichia coli" not in [organism for organism, _ in ranked]


def test_detect_species_drops_scores_at_or_below_threshold() -> None:
    reference = list(range(1, 101))
    fingerprints = [_fingerprint("Vibrio spp.", reference)]
    tiny_query = set(reference[:5])  # containment exactly 0.05
    assert detect_species(tiny_query, fingerprints) == []
    below = set(reference[:4])
    assert detect_species(below, fingerprints) == []


def test_detect_species_sorts_by_score_then_name() -> None:
    hashes = list(range(1, 101))
    fingerprints = [
        _fingerprint("Zoo", hashes),
        _fingerprint("Alfa", hashes),
    ]
    query = set(hashes)
    ranked = detect_species(query, fingerprints)
    assert [organism for organism, _ in ranked] == ["Alfa", "Zoo"]


def test_margin_rule_unique_when_top_dominates() -> None:
    ranked = [("A", 0.6), ("B", 0.25)]
    assert is_unique_detection(ranked) is True


def test_margin_rule_ambiguous_when_runner_up_close() -> None:
    ranked = [("A", 0.6), ("B", 0.5)]
    assert is_unique_detection(ranked) is False


def test_margin_rule_requires_minimum_top_score() -> None:
    assert is_unique_detection([("A", 0.2)]) is False
    assert is_unique_detection([("A", DETECT_MIN_CONTAINMENT)]) is False
    assert is_unique_detection([("A", 0.31)]) is True
    assert is_unique_detection([]) is False


def test_margin_rule_factor_boundary() -> None:
    top = 0.6
    runner = top / DETECT_MARGIN_FACTOR
    assert is_unique_detection([("A", top), ("B", runner)]) is True
    assert is_unique_detection([("A", top), ("B", runner + 0.01)]) is False


# ---------------------------------------------------------------------------
# schemes_for_organism
# ---------------------------------------------------------------------------


def test_schemes_for_organism_filters_type_and_organism_case_insensitively() -> None:
    cache = _FakeCatalogCache(
        {
            "pubmlst": [
                {
                    "scheme_name": "saureus_24",
                    "organism": "Staphylococcus aureus",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "saureus_25",
                    "organism": "Staphylococcus aureus",
                    "scheme_type": "cgmlst",
                    "n_loci": 1861,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "epidermidis_1",
                    "organism": "Staphylococcus epidermidis",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
            ],
            "pasteur": [
                {
                    "scheme_name": "saureus_p1",
                    "organism": "staphylococcus aureus",
                    "scheme_type": "wgmlst",
                    "n_loci": 3000,
                    "provider": "pasteur",
                },
            ],
        }
    )
    rows = schemes_for_organism(cache, "staphylococcus AUREUS", {"mlst", "wgmlst"})
    assert [row["scheme_name"] for row in rows] == ["saureus_24", "saureus_p1"]


def test_schemes_for_organism_sorts_by_loci_then_name() -> None:
    cache = _FakeCatalogCache(
        {
            "pubmlst": [
                {
                    "scheme_name": "b_1",
                    "organism": "Org",
                    "scheme_type": "mlst",
                    "n_loci": 9,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "a_1",
                    "organism": "Org",
                    "scheme_type": "mlst",
                    "n_loci": 9,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "c_1",
                    "organism": "Org",
                    "scheme_type": "mlst",
                    "n_loci": 2,
                    "provider": "pubmlst",
                },
            ]
        }
    )
    rows = schemes_for_organism(cache, "org", {"mlst"})
    assert [row["scheme_name"] for row in rows] == ["c_1", "a_1", "b_1"]


# ---------------------------------------------------------------------------
# fingerprints persistence
# ---------------------------------------------------------------------------


def test_save_and_load_fingerprints_roundtrip(tmp_path: Path) -> None:
    payload = {
        "version": 1,
        "k": FINGERPRINT_K,
        "sample_rate": FINGERPRINT_SAMPLE_RATE,
        "fingerprints": [_fingerprint("Org", [3, 1, 2])],
    }
    path = tmp_path / "species_fingerprints.json.gz"
    save_fingerprints(payload, path)
    assert path.exists()
    assert load_fingerprints(path) == payload


def test_fingerprints_path_lives_in_cache_root(tmp_path: Path) -> None:
    from gmlst.database.cache import DatabaseCache

    cache = DatabaseCache(tmp_path / "cache")
    assert (
        fingerprints_path(cache) == tmp_path / "cache" / "species_fingerprints.json.gz"
    )


# ---------------------------------------------------------------------------
# build_fingerprints
# ---------------------------------------------------------------------------


class _FakeDownloadCache(_FakeCatalogCache):
    """Catalog + scheme-downloading cache stub backed by temp FASTA files."""

    def __init__(
        self,
        catalogs: dict[str, list[dict[str, Any]]],
        scheme_dir: Path,
        allele_sequence: str = "ACCTGACCGTTAACGGCATTGCAACCGGTTAAAC",
    ) -> None:
        super().__init__(catalogs)
        self._scheme_dir = scheme_dir
        self._allele_sequence = allele_sequence
        self.downloaded: list[tuple[str, str]] = []
        self.root = scheme_dir

    def is_downloaded(self, name: str, provider: str) -> bool:
        return (name, provider) in self.downloaded

    def ensure_scheme(self, name: str, provider: str = "pubmlst", **_kwargs: Any):
        self.downloaded.append((name, provider))
        locus = f"{name}_locus1"
        locus_file = self._scheme_dir / name / f"{locus}.tfa"
        locus_file.parent.mkdir(parents=True, exist_ok=True)
        locus_file.write_text(f">{locus}_1\n{self._allele_sequence}\n")
        return Scheme(name=name, loci=[locus], allele_files={locus: locus_file})


def test_build_fingerprints_picks_smallest_mlst_scheme(tmp_path: Path) -> None:
    cache = _FakeDownloadCache(
        {
            "pubmlst": [
                {
                    "scheme_name": "org_1",
                    "organism": "Org one",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "org_2",
                    "organism": "Org one",
                    "scheme_type": "mlst",
                    "n_loci": 10,
                    "provider": "pubmlst",
                },
            ]
        },
        tmp_path,
    )
    payload = build_fingerprints(cache)
    assert payload["version"] == 1
    assert payload["k"] == FINGERPRINT_K
    assert len(payload["fingerprints"]) == 1
    fingerprint = payload["fingerprints"][0]
    assert fingerprint["organism"] == "Org one"
    assert fingerprint["source_scheme"] == "org_1"
    assert fingerprint["hashes"]
    expected = sketch_sequence(cache._allele_sequence)
    assert set(fingerprint["hashes"]) == expected


def test_build_fingerprints_skips_cgmlst_only_species(tmp_path: Path) -> None:
    """cgMLST-only organisms are skipped: species ID uses MLST sources only."""
    cache = _FakeDownloadCache(
        {
            "enterobase": [
                {
                    "scheme_name": "ecoli_cg",
                    "organism": "Escherichia coli",
                    "scheme_type": "cgmlst",
                    "n_loci": 2513,
                    "provider": "enterobase",
                }
            ]
        },
        tmp_path,
    )
    payload = build_fingerprints(cache)
    assert payload["fingerprints"] == []


def test_build_fingerprints_skips_organisms_without_mlst_or_cgmlst(
    tmp_path: Path,
) -> None:
    cache = _FakeDownloadCache(
        {
            "pubmlst": [
                {
                    "scheme_name": "r_1",
                    "organism": "Rmlst only",
                    "scheme_type": "rmlst",
                    "n_loci": 3,
                    "provider": "pubmlst",
                }
            ]
        },
        tmp_path,
    )
    events: list[tuple[str, str]] = []
    payload = build_fingerprints(cache, progress_cb=lambda e, d: events.append((e, d)))
    assert payload["fingerprints"] == []
    assert ("total", "1") in events
    assert any(event == "skip" for event, _ in events)


def test_build_fingerprints_reports_download_events(tmp_path: Path) -> None:
    cache = _FakeDownloadCache(
        {
            "pubmlst": [
                {
                    "scheme_name": "dl_1",
                    "organism": "Downloadus testus",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                }
            ]
        },
        tmp_path,
    )
    events: list[tuple[str, str]] = []
    build_fingerprints(cache, progress_cb=lambda e, d: events.append((e, d)))
    assert ("download", "dl_1 (pubmlst)") in events
    assert ("sketch", "Downloadus testus") in events


def test_build_fingerprints_continues_after_scheme_failure(tmp_path: Path) -> None:
    class _FailingCache(_FakeDownloadCache):
        failing = {"boom_1"}

        def ensure_scheme(self, name: str, provider: str = "pubmlst", **_kwargs):
            if name in self.failing:
                raise RuntimeError("network down")
            return super().ensure_scheme(name, provider, **_kwargs)

    cache = _FailingCache(
        {
            "pubmlst": [
                {
                    "scheme_name": "boom_1",
                    "organism": "Bad organism",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "ok_1",
                    "organism": "Good organism",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
            ]
        },
        tmp_path,
    )
    payload = build_fingerprints(cache)
    assert [fp["organism"] for fp in payload["fingerprints"]] == ["Good organism"]


def test_build_fingerprints_organism_filter_is_case_insensitive(
    tmp_path: Path,
) -> None:
    cache = _FakeDownloadCache(
        {
            "pubmlst": [
                {
                    "scheme_name": "a_1",
                    "organism": "Alpha alpha",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "b_1",
                    "organism": "Beta beta",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
            ]
        },
        tmp_path,
    )
    payload = build_fingerprints(cache, organisms={"alpha ALPHA"})
    assert [fp["organism"] for fp in payload["fingerprints"]] == ["Alpha alpha"]


# ---------------------------------------------------------------------------
# organism aliasing / dedup (scheme_preferences integration)
# ---------------------------------------------------------------------------


def _mlst_row(name: str, organism: str, loci: int = 7) -> dict[str, Any]:
    return {
        "scheme_name": name,
        "organism": organism,
        "scheme_type": "mlst",
        "n_loci": loci,
        "provider": "pubmlst",
    }


def test_build_fingerprints_merges_aliased_organisms(tmp_path: Path) -> None:
    cache = _FakeDownloadCache(
        {
            "pubmlst": [_mlst_row("escherichia_1", "Escherichia spp.")],
            "enterobase": [
                {
                    "scheme_name": "ecoli_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "enterobase",
                }
            ],
        },
        tmp_path,
    )

    payload = build_fingerprints(cache)

    organisms = [f["organism"] for f in payload["fingerprints"]]
    assert organisms == ["Escherichia spp."]
    # Preference order (escherichia_1 first) decides the source scheme.
    assert payload["fingerprints"][0]["source_scheme"] == "escherichia_1"


def test_build_fingerprints_organisms_filter_matches_any_alias(
    tmp_path: Path,
) -> None:
    cache = _FakeDownloadCache(
        {
            "pubmlst": [
                _mlst_row("escherichia_1", "Escherichia spp."),
                _mlst_row("vcholerae_1", "Vibrio cholerae"),
            ]
        },
        tmp_path,
    )

    payload = build_fingerprints(cache, organisms={"Escherichia coli"})

    organisms = [f["organism"] for f in payload["fingerprints"]]
    assert organisms == ["Escherichia spp."]


def test_select_source_scheme_prefers_curated_order() -> None:
    from gmlst.core.species_id import _select_source_scheme

    rows = [
        _mlst_row("big_2", "Org one", loci=7),
        _mlst_row("big_1", "Org one", loci=7),
    ]

    picked = _select_source_scheme(rows, order=["big_2", "big_1"])
    assert picked is not None
    assert picked["scheme_name"] == "big_2"

    fallback = _select_source_scheme(rows, order=["absent_9"])
    assert fallback is not None
    assert fallback["scheme_name"] == "big_1"


def test_select_source_scheme_deprioritizes_tiny_schemes() -> None:
    from gmlst.core.species_id import _select_source_scheme

    rows = [
        _mlst_row("bpertussis_7", "Bordetella pertussis", loci=2),
        _mlst_row("bpertussis_1", "Bordetella pertussis", loci=7),
        _mlst_row("bpertussis_2", "Bordetella pertussis", loci=5),
    ]

    picked = _select_source_scheme(rows)
    assert picked is not None
    assert picked["scheme_name"] == "bpertussis_1"


def test_select_source_scheme_prefers_seven_loci_classic() -> None:
    from gmlst.core.species_id import _select_source_scheme

    rows = [
        _mlst_row("bpertussis_6", "Bordetella pertussis", loci=6),
        _mlst_row("bpertussis_1", "Bordetella pertussis", loci=7),
        _mlst_row("bpertussis_3", "Bordetella pertussis", loci=9),
    ]

    picked = _select_source_scheme(rows)
    assert picked is not None
    assert picked["scheme_name"] == "bpertussis_1"
