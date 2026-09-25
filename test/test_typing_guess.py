"""Tests for --guess mode: per-sample scheme resolution and multi-scheme routing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from click.testing import CliRunner

from gmlst.calling.allele import LocusCall
from gmlst.calling.st_lookup import STResult
from gmlst.commands.typing_guess import resolve_guess_routes
from gmlst.core.species_id import (
    FINGERPRINT_K,
    FINGERPRINT_SAMPLE_RATE,
    sketch_sequence,
)
from gmlst.database.scheme_prefs import SchemePreference

_ORG_A_SEQ = "ACCTGATCGGTACAGCTAAGGCTTGCAATCGGTACAGGCTTAACCGGATCCAATG" * 6
_ORG_B_SEQ = "TTAAGGCCTTAGGCAATCGGTCAAGGTTACAACCGGTTAAGCCTTGGATCAATC" * 6

_MLST_TYPES = frozenset({"mlst"})


class _GuessCache:
    """Catalog + download stub with the surface resolve_guess_routes uses."""

    def __init__(
        self,
        catalogs: dict[str, list[dict[str, Any]]],
        downloaded: set[tuple[str, str]] | None = None,
        schemes: dict[str, list[str]] | None = None,
    ) -> None:
        self._catalogs = catalogs
        self._downloaded = downloaded or set()
        self._schemes = schemes or {}
        self.ensure_calls: list[str] = []

    def load_catalog(self, provider: str) -> list[dict[str, Any]] | None:
        return self._catalogs.get(provider)

    def is_downloaded(self, name: str, provider: str) -> bool:
        return (name, provider) in self._downloaded

    def ensure_scheme(self, name: str, provider: str = "pubmlst", **_kwargs: Any):
        self.ensure_calls.append(name)
        return self._schemes.get(name)


def _fingerprints(*pairs: tuple[str, str]) -> dict[str, Any]:
    return {
        "version": 1,
        "k": FINGERPRINT_K,
        "sample_rate": FINGERPRINT_SAMPLE_RATE,
        "fingerprints": [
            {
                "organism": organism,
                "k": FINGERPRINT_K,
                "sample_rate": FINGERPRINT_SAMPLE_RATE,
                "hashes": sorted(sketch_sequence(seq)),
                "source_scheme": "src",
            }
            for organism, seq in pairs
        ],
    }


def _org_catalog(organism: str, schemes: list[str], provider: str = "pubmlst"):
    return {
        provider: [
            {
                "scheme_name": name,
                "organism": organism,
                "scheme_type": "mlst",
                "n_loci": 7,
                "provider": provider,
            }
            for name in schemes
        ]
    }


def _write_fasta(path: Path, seq: str) -> Path:
    path.write_text(f">c1\n{seq}\n")
    return path


# ---------------------------------------------------------------------------
# scheme picking rules
# ---------------------------------------------------------------------------


def test_preference_order_wins(tmp_path: Path) -> None:
    sample = _write_fasta(tmp_path / "a.fna", _ORG_A_SEQ)
    cache = _GuessCache(_org_catalog("Org one", ["one_1", "one_2"]))
    prefs = [
        SchemePreference(
            organism="Org one",
            type="mlst",
            order=["one_2", "one_1"],
            aliases=frozenset(),
        )
    ]

    plan = resolve_guess_routes(
        [sample],
        type_set=_MLST_TYPES,
        cache=cache,
        fingerprints=_fingerprints(("Org one", _ORG_A_SEQ)),
        preferences=prefs,
    )

    assert [r.scheme for r in plan.routes] == ["one_2"]
    assert plan.skipped == []


def test_single_cached_candidate_picks_cached(tmp_path: Path) -> None:
    sample = _write_fasta(tmp_path / "a.fna", _ORG_A_SEQ)
    cache = _GuessCache(
        _org_catalog("Org one", ["one_1", "one_2"]),
        downloaded={("one_2", "pubmlst")},
    )

    plan = resolve_guess_routes(
        [sample],
        type_set=_MLST_TYPES,
        cache=cache,
        fingerprints=_fingerprints(("Org one", _ORG_A_SEQ)),
        preferences=[],
    )

    assert [r.scheme for r in plan.routes] == ["one_2"]
    assert "one_2" not in cache.ensure_calls


def test_no_preference_no_cache_picks_natural_first_and_ensures(
    tmp_path: Path,
) -> None:
    sample = _write_fasta(tmp_path / "a.fna", _ORG_A_SEQ)
    cache = _GuessCache(_org_catalog("Org one", ["one_2", "one_1"]))

    plan = resolve_guess_routes(
        [sample],
        type_set=_MLST_TYPES,
        cache=cache,
        fingerprints=_fingerprints(("Org one", _ORG_A_SEQ)),
        preferences=[],
    )

    assert [r.scheme for r in plan.routes] == ["one_1"]
    assert cache.ensure_calls == ["one_1"]


# ---------------------------------------------------------------------------
# grouping and skip semantics
# ---------------------------------------------------------------------------


def test_two_species_group_into_two_routes(tmp_path: Path) -> None:
    a1 = _write_fasta(tmp_path / "a1.fna", _ORG_A_SEQ)
    a2 = _write_fasta(tmp_path / "a2.fna", _ORG_A_SEQ)
    b1 = _write_fasta(tmp_path / "b1.fna", _ORG_B_SEQ)
    cache = _GuessCache(
        {
            "pubmlst": _org_catalog("Org one", ["one_1"])["pubmlst"]
            + _org_catalog("Org two", ["two_1"])["pubmlst"]
        }
    )

    plan = resolve_guess_routes(
        [a1, b1, a2],
        type_set=_MLST_TYPES,
        cache=cache,
        fingerprints=_fingerprints(("Org one", _ORG_A_SEQ), ("Org two", _ORG_B_SEQ)),
        preferences=[],
    )

    assert [(r.scheme, sorted(s.name for s in r.samples)) for r in plan.routes] == [
        ("one_1", ["a1.fna", "a2.fna"]),
        ("two_1", ["b1.fna"]),
    ]


def test_no_detection_skips_sample(tmp_path: Path) -> None:
    sample = _write_fasta(tmp_path / "x.fna", "ACGTACGTAC")
    cache = _GuessCache(_org_catalog("Org one", ["one_1"]))

    plan = resolve_guess_routes(
        [sample],
        type_set=_MLST_TYPES,
        cache=cache,
        fingerprints=_fingerprints(("Org one", _ORG_A_SEQ)),
        preferences=[],
    )

    assert plan.routes == []
    assert len(plan.skipped) == 1
    assert plan.skipped[0][0] == sample
    assert "identify" in plan.skipped[0][1].lower()


def test_no_scheme_of_type_skips_sample(tmp_path: Path) -> None:
    sample = _write_fasta(tmp_path / "a.fna", _ORG_A_SEQ)
    cache = _GuessCache(_org_catalog("Org one", []))

    plan = resolve_guess_routes(
        [sample],
        type_set=_MLST_TYPES,
        cache=cache,
        fingerprints=_fingerprints(("Org one", _ORG_A_SEQ)),
        preferences=[],
    )

    assert plan.routes == []
    assert "no scheme" in plan.skipped[0][1].lower()


def test_fastq_input_skips_with_reason(tmp_path: Path) -> None:
    fq = tmp_path / "reads.fastq"
    fq.write_text("@r1\nACGT\n+\nIIII\n")

    plan = resolve_guess_routes(
        [fq],
        type_set=_MLST_TYPES,
        cache=_GuessCache({"pubmlst": []}),
        fingerprints=_fingerprints(("Org one", _ORG_A_SEQ)),
        preferences=[],
    )

    assert plan.routes == []
    assert "assembly" in plan.skipped[0][1].lower()


def test_ambiguous_detection_still_routes_to_top(tmp_path: Path) -> None:
    sample = _write_fasta(tmp_path / "a.fna", _ORG_A_SEQ)
    cousin = _ORG_A_SEQ[:330] + _ORG_B_SEQ[330:]
    cache = _GuessCache(
        {
            "pubmlst": _org_catalog("Org one", ["one_1"])["pubmlst"]
            + _org_catalog("Org two", ["two_1"])["pubmlst"]
        }
    )

    plan = resolve_guess_routes(
        [sample],
        type_set=_MLST_TYPES,
        cache=cache,
        fingerprints=_fingerprints(("Org one", _ORG_A_SEQ), ("Org two", cousin)),
        preferences=[],
    )

    assert [r.scheme for r in plan.routes] == ["one_1"]


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def test_cli_guess_flag_plumbs_through(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def fake_guess_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("gmlst.commands.typing._run_guess_typing", fake_guess_run)
    sample = _write_fasta(tmp_path / "s.fna", _ORG_A_SEQ)

    from gmlst.cli import main

    result = CliRunner().invoke(main, ["typing", "mlst", "--guess", str(sample)])

    assert result.exit_code == 0, result.output
    assert captured.get("mode") == "mlst"
    assert [p.name for p in captured["samples"]] == ["s.fna"]


def test_cli_guess_conflicts_with_scheme_and_organism(tmp_path: Path) -> None:
    sample = _write_fasta(tmp_path / "s.fna", _ORG_A_SEQ)

    from gmlst.cli import main

    for extra in (["-s", "one_1"], ["-n", "org"], ["--novel-allele"]):
        result = CliRunner().invoke(
            main, ["typing", "mlst", "--guess", *extra, str(sample)]
        )
        assert result.exit_code == 2, (extra, result.output)


# ---------------------------------------------------------------------------
# end-to-end routing with a stubbed engine
# ---------------------------------------------------------------------------


def _fake_result(sample_path: Path, scheme: str, loci: list[str]) -> STResult:
    return STResult(
        sample_id=sample_path.name,
        scheme=scheme,
        st=None,
        locus_calls={
            locus: LocusCall(
                locus=locus, allele_id="1", call_type="exact", confidence=1.0
            )
            for locus in loci
        },
    )


def test_guess_routes_two_schemes_through_engine(monkeypatch, tmp_path: Path) -> None:
    a = _write_fasta(tmp_path / "a.fna", _ORG_A_SEQ)
    b = _write_fasta(tmp_path / "b.fna", _ORG_B_SEQ)

    catalogs = {
        "pubmlst": _org_catalog("Org one", ["one_1"])["pubmlst"]
        + _org_catalog("Org two", ["two_1"])["pubmlst"]
    }
    from gmlst.database.schema import Scheme

    def fake_ensure(self, name, provider="pubmlst", **_kwargs):
        return Scheme(name=name, loci=["abc"], allele_files={})

    run_calls: list[dict[str, Any]] = []

    def fake_run_typing(**kwargs):
        run_calls.append(kwargs)
        scheme = kwargs["scheme_name"]
        return [_fake_result(Path(p), scheme, ["abc"]) for p in kwargs["sample_paths"]]

    import gmlst.commands.typing as typing_cmd

    monkeypatch.setattr(
        typing_cmd.DatabaseCache, "load_catalog", lambda self, prov: catalogs.get(prov)
    )
    monkeypatch.setattr(typing_cmd.DatabaseCache, "ensure_scheme", fake_ensure)
    monkeypatch.setattr(typing_cmd, "run_typing", fake_run_typing)

    from gmlst.core import species_id

    monkeypatch.setattr(species_id, "bundled_fingerprints_path", lambda: None)
    cache_dir = tmp_path / "cache"
    from gmlst.core.species_id import save_fingerprints

    save_fingerprints(
        _fingerprints(("Org one", _ORG_A_SEQ), ("Org two", _ORG_B_SEQ)),
        cache_dir / "species_fingerprints.json.gz",
    )

    from gmlst.cli import main

    result = CliRunner().invoke(
        main,
        ["typing", "mlst", "--guess", "--cache-dir", str(cache_dir), str(a), str(b)],
    )

    assert result.exit_code == 0, result.output
    assert sorted(c["scheme_name"] for c in run_calls) == ["one_1", "two_1"]
    # Both per-scheme sections appear in the streamed TSV output.
    assert result.output.count("SCHEME") == 2
    assert "one_1" in result.output and "two_1" in result.output
