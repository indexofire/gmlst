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
