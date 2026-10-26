from __future__ import annotations

from pathlib import Path

from gmlst.aligners.base import AlleleMatch
from gmlst.calling.allele import LocusCall
from gmlst.calling.chew_policy import classify_chew_style_calls


def _write_locus(path: Path, locus: str) -> Path:
    file_path = path / f"{locus}.tfa"
    file_path.write_text(f">{locus}_1\nATGAAATAG\n")
    return file_path


def test_chew_policy_keeps_exact_numeric(tmp_path: Path) -> None:
    locus = "VPX001"
    allele_file = _write_locus(tmp_path, locus)
    calls = {
        locus: LocusCall(
            locus=locus,
            allele_id="1",
            call_type="exact",
            confidence=1.0,
            best_match=AlleleMatch(
                locus=locus,
                allele_id="1",
                identity=100.0,
                coverage=1.0,
                allele_length=9,
                allele_start=0,
                allele_end=9,
            ),
        )
    }

    classes = classify_chew_style_calls(
        locus_calls=calls,
        allele_files={locus: allele_file},
    )

    assert classes[locus] == "1"


def test_chew_policy_marks_multihit_nonexact_as_niph(tmp_path: Path) -> None:
    locus = "VPX002"
    allele_file = _write_locus(tmp_path, locus)
    calls = {
        locus: LocusCall(
            locus=locus,
            allele_id="2",
            call_type="closest",
            confidence=0.8,
            multiple_hits=True,
            allele_ids=["2", "3"],
            best_match=AlleleMatch(
                locus=locus,
                allele_id="2",
                identity=99.0,
                coverage=0.98,
                allele_length=9,
                allele_start=0,
                allele_end=9,
            ),
        )
    }

    classes = classify_chew_style_calls(
        locus_calls=calls,
        allele_files={locus: allele_file},
    )

    assert classes[locus] == "NIPH"


def test_chew_policy_marks_boundary_extension_as_plot3(tmp_path: Path) -> None:
    locus = "VPX003"
    allele_file = _write_locus(tmp_path, locus)
    calls = {
        locus: LocusCall(
            locus=locus,
            allele_id="4",
            call_type="closest",
            confidence=0.7,
            best_match=AlleleMatch(
                locus=locus,
                allele_id="4",
                identity=98.0,
                coverage=0.95,
                strand="+",
                allele_length=120,
                allele_start=0,
                allele_end=90,
                query_contig_length=130,
                query_start=5,
                query_end=110,
            ),
        )
    }

    classes = classify_chew_style_calls(
        locus_calls=calls,
        allele_files={locus: allele_file},
    )

    assert classes[locus] == "PLOT3"


def test_chew_policy_cds_gate_marks_non_cds_numeric_as_lnf(tmp_path: Path) -> None:
    locus = "VPX004"
    allele_file = _write_locus(tmp_path, locus)
    calls = {
        locus: LocusCall(
            locus=locus,
            allele_id="1",
            call_type="exact",
            confidence=1.0,
            best_match=AlleleMatch(
                locus=locus,
                allele_id="1",
                identity=100.0,
                coverage=1.0,
                allele_length=9,
                allele_start=0,
                allele_end=9,
            ),
        )
    }

    classes = classify_chew_style_calls(
        locus_calls=calls,
        allele_files={locus: allele_file},
        cds_dna_hashes=set(),
    )

    assert classes[locus] == "LNF"


def test_chew_policy_cds_fallback_recovers_inf_on_boundary_match(
    tmp_path: Path,
) -> None:
    locus = "VPX005"
    allele_file = _write_locus(tmp_path, locus)
    calls = {
        locus: LocusCall(
            locus=locus,
            allele_id="1",
            call_type="exact",
            confidence=1.0,
            best_match=AlleleMatch(
                locus=locus,
                allele_id="1",
                identity=100.0,
                coverage=1.0,
                allele_length=9,
                allele_start=0,
                allele_end=9,
            ),
        )
    }

    classes = classify_chew_style_calls(
        locus_calls=calls,
        allele_files={locus: allele_file},
        cds_dna_hashes=set(),
        cds_sequences=["AAAATGAAATAGTTT"],
    )

    assert classes[locus] == "INF-1"


def test_chew_policy_can_disable_cds_gate(tmp_path: Path) -> None:
    locus = "VPX006"
    allele_file = _write_locus(tmp_path, locus)
    calls = {
        locus: LocusCall(
            locus=locus,
            allele_id="1",
            call_type="exact",
            confidence=1.0,
            best_match=AlleleMatch(
                locus=locus,
                allele_id="1",
                identity=100.0,
                coverage=1.0,
                allele_length=9,
                allele_start=0,
                allele_end=9,
            ),
        )
    }

    classes = classify_chew_style_calls(
        locus_calls=calls,
        allele_files={locus: allele_file},
        cds_dna_hashes=set(),
        enforce_cds_gate=False,
    )

    assert classes[locus] == "1"


def test_chew_metadata_cache_reuses_unchanged_allele_files(
    tmp_path: Path, monkeypatch
) -> None:
    from gmlst.calling import chew_policy

    locus = "VPX_CACHE"
    allele_file = _write_locus(tmp_path, locus)
    calls = {
        locus: LocusCall(
            locus=locus,
            allele_id="1",
            call_type="exact",
            confidence=1.0,
            best_match=AlleleMatch(
                locus=locus,
                allele_id="1",
                identity=100.0,
                coverage=1.0,
                allele_length=9,
                allele_start=0,
                allele_end=9,
            ),
        )
    }
    chew_policy._CHEW_METADATA_CACHE.clear()
    classify_chew_style_calls(locus_calls=calls, allele_files={locus: allele_file})

    def boom(*args, **kwargs):
        raise AssertionError("allele FASTA should be cached")

    monkeypatch.setattr(chew_policy, "iter_fasta_records", boom)
    assert classify_chew_style_calls(
        locus_calls=calls, allele_files={locus: allele_file}
    ) == {locus: "1"}


def test_chew_metadata_cache_invalidates_on_file_change(tmp_path: Path) -> None:
    from gmlst.calling import chew_policy

    locus = "VPX_CACHE2"
    allele_file = _write_locus(tmp_path, locus)
    calls = {
        locus: LocusCall(
            locus=locus,
            allele_id="1",
            call_type="closest",
            confidence=0.8,
            best_match=AlleleMatch(
                locus=locus,
                allele_id="1",
                identity=99.0,
                coverage=0.9,
                allele_length=20,
                allele_start=0,
                allele_end=9,
            ),
        )
    }
    chew_policy._CHEW_METADATA_CACHE.clear()
    first = classify_chew_style_calls(
        locus_calls=calls, allele_files={locus: allele_file}
    )
    allele_file.write_text(f">{locus}_1\nATGAAATAGATGAAATAGATGAAATAG\n")
    second = classify_chew_style_calls(
        locus_calls=calls, allele_files={locus: allele_file}
    )
    assert first != second


def _boundary_call(
    *,
    strand: str,
    allele_len: int,
    allele_start: int,
    allele_end: int,
    contig_len: int,
    query_start: int,
    query_end: int,
) -> LocusCall:
    return LocusCall(
        locus="BOUND",
        allele_id="1",
        call_type="closest",
        confidence=0.8,
        best_match=AlleleMatch(
            locus="BOUND",
            allele_id="1",
            identity=99.0,
            coverage=0.95,
            strand=strand,
            allele_length=allele_len,
            allele_start=allele_start,
            allele_end=allele_end,
            query_contig_length=contig_len,
            query_start=query_start,
            query_end=query_end,
        ),
    )


def test_chew_boundary_codes_table(tmp_path: Path) -> None:
    locus = "BOUND"
    allele_file = tmp_path / f"{locus}.tfa"
    allele_file.write_text(f">{locus}_1\n" + "A" * 120 + "\n")
    cases = [
        (
            "PLOT5",
            _boundary_call(
                strand="+",
                allele_len=120,
                allele_start=10,
                allele_end=110,
                contig_len=130,
                query_start=0,
                query_end=120,
            ),
        ),
        (
            "PLOT3",
            _boundary_call(
                strand="+",
                allele_len=120,
                allele_start=10,
                allele_end=110,
                contig_len=130,
                query_start=10,
                query_end=130,
            ),
        ),
        (
            "PLOT5",
            _boundary_call(
                strand="-",
                allele_len=120,
                allele_start=10,
                allele_end=110,
                contig_len=130,
                query_start=10,
                query_end=121,
            ),
        ),
        (
            "PLOT3",
            _boundary_call(
                strand="-",
                allele_len=120,
                allele_start=10,
                allele_end=110,
                contig_len=130,
                query_start=0,
                query_end=120,
            ),
        ),
        (
            "LOTSC",
            _boundary_call(
                strand="+",
                allele_len=120,
                allele_start=10,
                allele_end=110,
                contig_len=100,
                query_start=0,
                query_end=100,
            ),
        ),
    ]
    for expected, call in cases:
        classes = classify_chew_style_calls(
            locus_calls={locus: call},
            allele_files={locus: allele_file},
        )
        assert classes[locus] == expected


def test_chew_size_outliers(tmp_path: Path) -> None:
    locus = "SIZE"
    allele_file = _write_locus(tmp_path, locus)
    small = _boundary_call(
        strand="+",
        allele_len=2,
        allele_start=0,
        allele_end=2,
        contig_len=2,
        query_start=0,
        query_end=2,
    )
    large = _boundary_call(
        strand="+",
        allele_len=40,
        allele_start=0,
        allele_end=40,
        contig_len=40,
        query_start=0,
        query_end=40,
    )
    for expected, call in (("ASM", small), ("ALM", large)):
        classes = classify_chew_style_calls(
            locus_calls={locus: call},
            allele_files={locus: allele_file},
        )
        assert classes[locus] == expected
