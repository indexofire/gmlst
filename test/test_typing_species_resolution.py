"""CLI tests for typing scheme resolution: -n organism and species auto-detect."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from gmlst.cli import main
from gmlst.core.species_id import (
    FINGERPRINT_K,
    FINGERPRINT_SAMPLE_RATE,
    save_fingerprints,
    sketch_sequence,
)
from gmlst.database.cache import DatabaseCache
from gmlst.database.schema import Scheme

_SPECIES_SEQ = "ACCTGATCGGTACAGCTAAGGCTTGCAATCGGTACAGGCTTAACCGGATCCAATG" * 6
_RELATIVE_SEQ = "TTAAGGCCTTAGGCAATCGGTCAAGGTTACAACCGGTTAAGCCTTGGATCAATC" * 6
_UNRELATED_SEQ = "TTTTAAAACCCCGGGGTTTTAAAACCCCGGGGTTTTAAAACCCCGGGGAAATTT" * 6
# Mostly-overlapping cousin of _SPECIES_SEQ: defeats the 2x margin rule.
_RUNNER_UP_SEQ = _SPECIES_SEQ[:330] + _RELATIVE_SEQ[330:]


def _fake_catalog(catalog: list[dict[str, Any]] | None = None):
    rows = catalog if catalog is not None else _default_catalog()

    def _load_catalog(self, provider: str) -> list[dict[str, Any]]:
        if provider == "pubmlst":
            return rows
        return []

    return _load_catalog


def _default_catalog() -> list[dict[str, Any]]:
    return [
        {
            "scheme_name": "bpertussis_1",
            "organism": "Bordetella pertussis",
            "scheme_type": "mlst",
            "n_loci": 7,
            "provider": "pubmlst",
        },
        {
            "scheme_name": "vcholerae_1",
            "organism": "Vibrio cholerae",
            "scheme_type": "mlst",
            "n_loci": 7,
            "provider": "pubmlst",
        },
        {
            "scheme_name": "vpara_1",
            "organism": "Vibrio parahaemolyticus",
            "scheme_type": "mlst",
            "n_loci": 7,
            "provider": "pubmlst",
        },
    ]


def _run_typing_recorder(monkeypatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing", fake_run_mlst_like_typing
    )
    return captured


def _write_fasta(path: Path, *sequences: str) -> Path:
    parts = [f">seq_{index}\n{seq}" for index, seq in enumerate(sequences)]
    path.write_text("\n".join(parts) + "\n")
    return path


def _fingerprint_payload(organism: str, sequence: str) -> dict[str, Any]:
    return {
        "version": 1,
        "k": FINGERPRINT_K,
        "sample_rate": FINGERPRINT_SAMPLE_RATE,
        "fingerprints": [
            {
                "organism": organism,
                "k": FINGERPRINT_K,
                "sample_rate": FINGERPRINT_SAMPLE_RATE,
                "hashes": sorted(sketch_sequence(sequence)),
                "source_scheme": "src_1",
            }
        ],
    }


# ---------------------------------------------------------------------------
# -n organism resolution
# ---------------------------------------------------------------------------


def _mock_no_bundled(monkeypatch):
    """Disable the bundled fingerprint database for missing-file tests."""
    monkeypatch.setattr("gmlst.core.species_id.bundled_fingerprints_path", lambda: None)


def test_typing_mlst_scheme_and_organism_are_mutually_exclusive(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)

    result = CliRunner().invoke(
        main,
        ["typing", "mlst", "-s", "bpertussis_1", "-n", "bordetella", str(sample)],
    )

    assert result.exit_code == 2
    assert "not both" in result.output
    assert captured == {}


def test_typing_mlst_organism_unique_match_auto_selects(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())

    result = CliRunner().invoke(
        main, ["typing", "mlst", "-n", "bordetella", str(sample)]
    )

    assert result.exit_code == 0
    assert "[auto-selected] bpertussis_1 via -n 'bordetella'" in result.output
    assert captured["scheme"] == "bpertussis_1"
    assert captured["mode"] == "mlst"


def test_typing_mlst_organism_matches_scheme_name_too(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())

    result = CliRunner().invoke(main, ["typing", "mlst", "-n", "vpara_1", str(sample)])

    assert result.exit_code == 0
    assert captured["scheme"] == "vpara_1"


def test_typing_mlst_organism_multiple_matches_table_and_exit_2(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())

    result = CliRunner().invoke(main, ["typing", "mlst", "-n", "vibrio", str(sample)])

    assert result.exit_code == 2
    assert "Multiple MLST schemes match -n 'vibrio'" in result.output
    assert "vcholerae_1" in result.output
    assert "vpara_1" in result.output
    assert captured == {}


def test_typing_mlst_organism_zero_matches_hints_scheme_list(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())

    result = CliRunner().invoke(main, ["typing", "mlst", "-n", "shigella", str(sample)])

    assert result.exit_code == 2
    assert "No MLST schemes match organism 'shigella'" in result.output
    assert "gmlst scheme list -n" in result.output


def test_typing_cgmlst_organism_filtered_to_cgmlst_types(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(
        DatabaseCache,
        "load_catalog",
        _fake_catalog(
            [
                {
                    "scheme_name": "ecoa_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "ecoa_2",
                    "organism": "Escherichia coli",
                    "scheme_type": "cgmlst",
                    "n_loci": 2513,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "ecoa_3",
                    "organism": "Escherichia wgmlstica",
                    "scheme_type": "wgmlst",
                    "n_loci": 9000,
                    "provider": "pubmlst",
                },
            ]
        ),
    )

    unique = CliRunner().invoke(main, ["typing", "cgmlst", "-n", "coli", str(sample)])
    assert unique.exit_code == 0
    assert "[auto-selected] ecoa_2 via -n 'coli'" in unique.output
    assert captured["scheme"] == "ecoa_2"

    both = CliRunner().invoke(
        main, ["typing", "cgmlst", "-n", "escherichia", str(sample)]
    )
    assert both.exit_code == 2
    assert "Multiple cgMLST/wgMLST schemes match" in both.output


def test_typing_mlst_scheme_still_works_without_resolution(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)

    result = CliRunner().invoke(main, ["typing", "mlst", "-s", "custom_x", str(sample)])

    assert result.exit_code == 0
    assert captured["scheme"] == "custom_x"


# ---------------------------------------------------------------------------
# auto-detection flow
# ---------------------------------------------------------------------------


def test_typing_mlst_fastq_without_scheme_or_organism_exits_2(
    tmp_path: Path,
) -> None:
    fastq = tmp_path / "sample_R1.fastq"
    fastq.write_text("@r1\nACGT\n+\n####\n")

    result = CliRunner().invoke(main, ["typing", "mlst", str(fastq)])

    assert result.exit_code == 2
    assert "FASTQ" in result.output
    assert "specify -s" in result.output


def test_auto_flow_missing_fingerprints_noninteractive_exits_2(
    monkeypatch, tmp_path: Path
) -> None:
    _mock_no_bundled(monkeypatch)
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())

    result = CliRunner().invoke(
        main, ["typing", "mlst", str(sample), "--cache-dir", str(tmp_path / "cache")]
    )

    assert result.exit_code == 2
    assert "fingerprint database not found" in result.output.lower()
    assert "gmlst scheme update-fingerprints" in result.output


def test_auto_flow_missing_fingerprints_declined_exits_2(
    monkeypatch, tmp_path: Path
) -> None:
    _mock_no_bundled(monkeypatch)
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())
    monkeypatch.setattr(
        "gmlst.commands.typing_species._stdin_is_interactive", lambda: True
    )

    result = CliRunner().invoke(
        main,
        ["typing", "mlst", str(sample), "--cache-dir", str(tmp_path / "cache")],
        input="n\n",
    )

    assert result.exit_code == 2
    assert "Download and build it now?" in result.output
    assert "gmlst scheme update-fingerprints" in result.output


def test_auto_flow_missing_fingerprints_confirmed_builds_and_selects(
    monkeypatch, tmp_path: Path
) -> None:
    _mock_no_bundled(monkeypatch)
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())
    monkeypatch.setattr(
        "gmlst.commands.typing_species._stdin_is_interactive", lambda: True
    )
    monkeypatch.setattr(
        "gmlst.commands.typing_species.build_fingerprints_with_progress",
        lambda cache, **_kwargs: (
            _fingerprint_payload("Bordetella pertussis", _SPECIES_SEQ),
            {"sketch": 1, "download": 1, "skip": 0},
        ),
    )
    cache_dir = tmp_path / "cache"

    result = CliRunner().invoke(
        main,
        ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)],
        input="y\n",
    )

    assert result.exit_code == 0
    assert "[auto-selected] bpertussis_1" in result.output
    assert "confidence 1.00" in result.output
    assert captured["scheme"] == "bpertussis_1"
    import zlib as _zlib

    saved = json.loads(
        _zlib.decompress((cache_dir / "species_fingerprints.json.gz").read_bytes())
    )
    assert saved["fingerprints"][0]["organism"] == "Bordetella pertussis"


def test_auto_flow_with_fingerprints_unique_detection_auto_selects(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _UNRELATED_SEQ, _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())

    cache_dir = tmp_path / "cache"
    save_fingerprints(
        _fingerprint_payload("Bordetella pertussis", _SPECIES_SEQ),
        cache_dir / "species_fingerprints.json.gz",
    )

    result = CliRunner().invoke(
        main, ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)]
    )

    assert result.exit_code == 0
    assert (
        "[auto-selected] bpertussis_1 "
        "(species Bordetella pertussis, confidence 1.00)" in result.output
    )
    assert captured["scheme"] == "bpertussis_1"


def test_auto_flow_species_detected_but_no_scheme_of_type_exits_2(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())

    cache_dir = tmp_path / "cache"
    save_fingerprints(
        _fingerprint_payload("Bordetella pertussis", _SPECIES_SEQ),
        cache_dir / "species_fingerprints.json.gz",
    )

    result = CliRunner().invoke(
        main, ["typing", "cgmlst", str(sample), "--cache-dir", str(cache_dir)]
    )

    assert result.exit_code == 2
    assert "Detected species 'Bordetella pertussis'" in result.output
    assert "no cgMLST/wgMLST scheme is available" in result.output


def test_auto_flow_unidentified_species_exits_2(monkeypatch, tmp_path: Path) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _UNRELATED_SEQ)
    monkeypatch.setattr(DatabaseCache, "load_catalog", _fake_catalog())

    cache_dir = tmp_path / "cache"
    save_fingerprints(
        _fingerprint_payload("Bordetella pertussis", _SPECIES_SEQ),
        cache_dir / "species_fingerprints.json.gz",
    )

    result = CliRunner().invoke(
        main, ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)]
    )

    assert result.exit_code == 2
    assert "Could not identify the species" in result.output


def test_auto_flow_multiple_schemes_noninteractive_lists_and_exits_2(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(
        DatabaseCache,
        "load_catalog",
        _fake_catalog(
            [
                {
                    "scheme_name": "ecoa_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "ecob_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 9,
                    "provider": "pubmlst",
                },
            ]
        ),
    )
    cache_dir = tmp_path / "cache"
    save_fingerprints(
        _fingerprint_payload("Escherichia coli", _SPECIES_SEQ),
        cache_dir / "species_fingerprints.json.gz",
    )

    result = CliRunner().invoke(
        main, ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)]
    )

    assert result.exit_code == 2
    assert "1. ecoa_1" in result.output
    assert "2. ecob_1" in result.output
    assert "Multiple candidate MLST schemes" in result.output
    assert captured == {}


def test_auto_flow_multiple_schemes_interactive_selection(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(
        DatabaseCache,
        "load_catalog",
        _fake_catalog(
            [
                {
                    "scheme_name": "ecoa_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
                {
                    "scheme_name": "ecob_1",
                    "organism": "Escherichia coli",
                    "scheme_type": "mlst",
                    "n_loci": 9,
                    "provider": "pubmlst",
                },
            ]
        ),
    )
    monkeypatch.setattr(
        "gmlst.commands.typing_species._stdin_is_interactive", lambda: True
    )
    cache_dir = tmp_path / "cache"
    save_fingerprints(
        _fingerprint_payload("Escherichia coli", _SPECIES_SEQ),
        cache_dir / "species_fingerprints.json.gz",
    )

    result = CliRunner().invoke(
        main,
        ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)],
        input="2\n",
    )

    assert result.exit_code == 0
    assert "Select scheme" in result.output
    assert "[auto-selected] ecob_1 (species detection, user selection)" in result.output
    assert captured["scheme"] == "ecob_1"


def test_auto_flow_ambiguous_species_lists_scored_candidates(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(
        DatabaseCache,
        "load_catalog",
        _fake_catalog(
            _default_catalog()
            + [
                {
                    "scheme_name": "bbron_1",
                    "organism": "Bordetella bronchiseptica",
                    "scheme_type": "mlst",
                    "n_loci": 7,
                    "provider": "pubmlst",
                },
            ]
        ),
    )
    monkeypatch.setattr(
        "gmlst.commands.typing_species._stdin_is_interactive", lambda: True
    )
    cache_dir = tmp_path / "cache"
    payload = {
        "version": 1,
        "k": FINGERPRINT_K,
        "sample_rate": FINGERPRINT_SAMPLE_RATE,
        "fingerprints": [
            {
                "organism": "Bordetella pertussis",
                "k": FINGERPRINT_K,
                "sample_rate": FINGERPRINT_SAMPLE_RATE,
                "hashes": sorted(sketch_sequence(_SPECIES_SEQ)),
                "source_scheme": "src_1",
            },
            {
                "organism": "Bordetella bronchiseptica",
                "k": FINGERPRINT_K,
                "sample_rate": FINGERPRINT_SAMPLE_RATE,
                "hashes": sorted(sketch_sequence(_RUNNER_UP_SEQ)),
                "source_scheme": "src_2",
            },
        ],
    }
    save_fingerprints(payload, cache_dir / "species_fingerprints.json.gz")

    result = CliRunner().invoke(
        main,
        ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)],
        input="2\n",
    )

    assert result.exit_code == 0
    assert "species confidence" in result.output
    assert "[auto-selected] bpertussis_1" in result.output
    assert captured["scheme"] == "bpertussis_1"


# ---------------------------------------------------------------------------
# scheme update-fingerprints
# ---------------------------------------------------------------------------


def test_scheme_update_fingerprints_builds_database(
    monkeypatch, tmp_path: Path
) -> None:
    allele_file = tmp_path / "alleles" / "src.tfa"
    allele_file.parent.mkdir(parents=True)
    allele_file.write_text(f">tst_1\n{_SPECIES_SEQ}\n")

    def _load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [
                {
                    "scheme_name": "tst_1",
                    "organism": "Testus testus",
                    "scheme_type": "mlst",
                    "n_loci": 1,
                    "provider": "pubmlst",
                }
            ]
        return []

    monkeypatch.setattr(DatabaseCache, "load_catalog", _load_catalog)
    monkeypatch.setattr(
        DatabaseCache, "is_downloaded", lambda self, name, provider: False
    )
    monkeypatch.setattr(
        DatabaseCache,
        "ensure_scheme",
        lambda self, name, **_kwargs: Scheme(
            name=name, loci=["tst"], allele_files={"tst": allele_file}
        ),
    )

    result = CliRunner().invoke(
        main, ["scheme", "update-fingerprints", "-y", "--cache-dir", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "Organisms sketched: 1" in result.output
    assert "schemes downloaded: 1" in result.output
    import zlib as _z

    payload = json.loads(
        _z.decompress((tmp_path / "species_fingerprints.json.gz").read_bytes())
    )
    assert payload["fingerprints"][0]["organism"] == "Testus testus"
    assert payload["fingerprints"][0]["source_scheme"] == "tst_1"


def test_scheme_update_fingerprints_confirm_declined(
    monkeypatch, tmp_path: Path
) -> None:
    import zlib as _z

    fingerprints = tmp_path / "species_fingerprints.json.gz"
    fingerprints.write_bytes(_z.compress(b'{"version": 1, "fingerprints": []}'))

    result = CliRunner().invoke(
        main,
        ["scheme", "update-fingerprints", "--cache-dir", str(tmp_path)],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Aborted." in result.output
    import zlib as _z2

    assert (
        _z2.decompress(fingerprints.read_bytes())
        == b'{"version": 1, "fingerprints": []}'
    )


def test_scheme_update_fingerprints_help_lists_options() -> None:
    result = CliRunner().invoke(main, ["scheme", "update-fingerprints", "--help"])

    assert result.exit_code == 0
    assert "--yes" in result.output
    assert "--organisms" in result.output
    assert "--connections" in result.output


# ---------------------------------------------------------------------------
# unique detection + multi-scheme: cached-candidate auto-selection
# ---------------------------------------------------------------------------


def _two_scheme_catalog() -> list[dict[str, Any]]:
    return [
        {
            "scheme_name": "bpertussis_1",
            "organism": "Bordetella pertussis",
            "scheme_type": "mlst",
            "n_loci": 7,
            "provider": "pubmlst",
        },
        {
            "scheme_name": "bpertussis_2",
            "organism": "Bordetella pertussis",
            "scheme_type": "mlst",
            "n_loci": 7,
            "provider": "pubmlst",
        },
    ]


def _mark_downloaded(cache_dir: Path, name: str, provider: str = "pubmlst") -> None:
    scheme_dir = cache_dir / provider / name
    scheme_dir.mkdir(parents=True, exist_ok=True)
    (scheme_dir / ".meta.json").write_text("{}")


def test_unique_detection_two_schemes_one_cached_auto_selects(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(
        DatabaseCache, "load_catalog", _fake_catalog(_two_scheme_catalog())
    )

    cache_dir = tmp_path / "cache"
    save_fingerprints(
        _fingerprint_payload("Bordetella pertussis", _SPECIES_SEQ),
        cache_dir / "species_fingerprints.json.gz",
    )
    _mark_downloaded(cache_dir, "bpertussis_1")

    result = CliRunner().invoke(
        main, ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)]
    )

    assert result.exit_code == 0, result.output
    assert "[auto-selected] bpertussis_1" in result.output
    assert "only cached candidate" in result.output
    assert "Select scheme" not in result.output
    assert captured["scheme"] == "bpertussis_1"


def test_unique_detection_two_schemes_both_cached_prompts(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(
        DatabaseCache, "load_catalog", _fake_catalog(_two_scheme_catalog())
    )
    monkeypatch.setattr(
        "gmlst.commands.typing_species._stdin_is_interactive", lambda: True
    )

    cache_dir = tmp_path / "cache"
    save_fingerprints(
        _fingerprint_payload("Bordetella pertussis", _SPECIES_SEQ),
        cache_dir / "species_fingerprints.json.gz",
    )
    _mark_downloaded(cache_dir, "bpertussis_1")
    _mark_downloaded(cache_dir, "bpertussis_2")

    result = CliRunner().invoke(
        main,
        ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)],
        input="2\n",
    )

    assert result.exit_code == 0, result.output
    assert "Select scheme" in result.output
    assert "(cached)" in result.output
    assert captured["scheme"] == "bpertussis_2"


def test_unique_detection_two_schemes_none_cached_prompts(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    captured = _run_typing_recorder(monkeypatch)
    monkeypatch.setattr(
        DatabaseCache, "load_catalog", _fake_catalog(_two_scheme_catalog())
    )
    monkeypatch.setattr(
        "gmlst.commands.typing_species._stdin_is_interactive", lambda: True
    )

    cache_dir = tmp_path / "cache"
    save_fingerprints(
        _fingerprint_payload("Bordetella pertussis", _SPECIES_SEQ),
        cache_dir / "species_fingerprints.json.gz",
    )

    result = CliRunner().invoke(
        main,
        ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)],
        input="1\n",
    )

    assert result.exit_code == 0, result.output
    assert "Select scheme" in result.output
    assert captured["scheme"] == "bpertussis_1"


def test_ambiguous_detection_one_cached_still_prompts(
    monkeypatch, tmp_path: Path
) -> None:
    sample = _write_fasta(tmp_path / "sample.fna", _SPECIES_SEQ)
    _run_typing_recorder(monkeypatch)

    def _two_organisms(catalog: list[dict[str, Any]] | None = None):
        def _load(self, provider: str) -> list[dict[str, Any]]:
            if provider == "pubmlst":
                return catalog if catalog is not None else _default_catalog()
            return []

        return _load

    catalog = _two_scheme_catalog() + [
        {
            "scheme_name": "vpara_1",
            "organism": "Vibrio parahaemolyticus",
            "scheme_type": "mlst",
            "n_loci": 7,
            "provider": "pubmlst",
        }
    ]
    monkeypatch.setattr(DatabaseCache, "load_catalog", _two_organisms(catalog))
    monkeypatch.setattr(
        "gmlst.commands.typing_species._stdin_is_interactive", lambda: True
    )

    cache_dir = tmp_path / "cache"
    payload = _fingerprint_payload("Bordetella pertussis", _SPECIES_SEQ)
    payload["fingerprints"].append(
        {
            "organism": "Vibrio parahaemolyticus",
            "k": FINGERPRINT_K,
            "sample_rate": FINGERPRINT_SAMPLE_RATE,
            "hashes": sorted(sketch_sequence(_RUNNER_UP_SEQ)),
            "source_scheme": "vpara_1",
        }
    )
    save_fingerprints(payload, cache_dir / "species_fingerprints.json.gz")
    _mark_downloaded(cache_dir, "bpertussis_1")

    result = CliRunner().invoke(
        main,
        ["typing", "mlst", str(sample), "--cache-dir", str(cache_dir)],
        input="1\n",
    )

    assert result.exit_code == 0, result.output
    # Ambiguous species window keeps the human decision even with a cached scheme.
    assert "Select scheme" in result.output
