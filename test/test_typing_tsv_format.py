from __future__ import annotations

from typing import cast

from gmlst.aligners.base import AlleleMatch
from gmlst.calling.allele import LocusCall, call_best_allele
from gmlst.calling.st_lookup import STResult, lookup_st
from gmlst.commands.typing import _format_st_for_tsv, _format_tsv_row
from gmlst.database.schema import Scheme


def test_format_st_for_tsv_none_becomes_dash() -> None:
    result = STResult(sample_id="s1", scheme="ecoli", st=None, locus_calls={})
    assert _format_st_for_tsv(result) == "-"


def test_format_tsv_row_uses_uncertainty_symbols() -> None:
    result = STResult(
        sample_id="sampleA",
        scheme="ecoli",
        st=66,
        locus_calls={
            "abc": LocusCall(
                locus="abc",
                allele_id="66",
                call_type="closest",
                confidence=0.8,
            ),
            "def": LocusCall(
                locus="def",
                allele_id="15",
                call_type="partial",
                confidence=0.7,
            ),
            "ghi": LocusCall(
                locus="ghi",
                allele_id="77",
                call_type="exact",
                confidence=0.99,
            ),
        },
    )

    row = _format_tsv_row(
        result,
        ["abc", "def", "ghi", "missing"],
        False,
        call_policy="default",
    )
    assert row == "sampleA\tecoli\t-\t~66\t15?\t77\t-"


def test_full_identity_but_not_full_length_is_partial() -> None:
    match = AlleleMatch(
        locus="pyrC",
        allele_id="66",
        identity=100.0,
        coverage=0.9878,
        alignment_length=487,
    )
    call = call_best_allele([match], min_identity=95.0, min_coverage=0.95)
    assert call.call_type == "partial"


def test_stresult_to_dict_uses_best_match_metrics() -> None:
    result = STResult(
        sample_id="sampleB",
        scheme="vparahaemolyticus",
        st=None,
        locus_calls={
            "pyrC": LocusCall(
                locus="pyrC",
                allele_id="66",
                call_type="partial",
                confidence=0.9,
                best_match=AlleleMatch(
                    locus="pyrC",
                    allele_id="66",
                    identity=100.0,
                    coverage=0.9878,
                    alignment_length=487,
                ),
            )
        },
    )

    payload = result.to_dict()
    assert payload["allele_calls"]["pyrC"]["identity"] == 100.0
    assert payload["allele_calls"]["pyrC"]["coverage"] == 0.9878


def test_multicopy_conflict_formats_as_comma_and_sets_st_dash() -> None:
    result = STResult(
        sample_id="sampleC",
        scheme="vpa",
        st=87,
        locus_calls={
            "pyrC": LocusCall(
                locus="pyrC",
                allele_id="1",
                call_type="exact",
                confidence=1.0,
                multiple_hits=True,
                allele_ids=["2", "1"],
            )
        },
    )

    row = _format_tsv_row(result, ["pyrC"], False, call_policy="default")
    assert row == "sampleC\tvpa\t-\t1,2"


def test_same_copy_count_notation_enabled() -> None:
    result = STResult(
        sample_id="sampleD",
        scheme="vpa",
        st=87,
        locus_calls={
            "dnaE": LocusCall(
                locus="dnaE",
                allele_id="1",
                call_type="exact",
                confidence=1.0,
                copy_count=2,
            )
        },
    )

    row = _format_tsv_row(result, ["dnaE"], True, call_policy="default")
    assert row == "sampleD\tvpa\t87\t1,1"


def test_format_tsv_row_uses_chew_style_calls_when_policy_enabled() -> None:
    result = STResult(
        sample_id="sampleE",
        scheme="vpa",
        st=12,
        locus_calls={
            "VP0015": LocusCall(
                locus="VP0015",
                allele_id="1",
                call_type="exact",
                confidence=1.0,
            )
        },
        chew_style_calls={"VP0015": "LNF"},
    )

    row = _format_tsv_row(result, ["VP0015"], False, call_policy="chewbbaca")
    assert row == "sampleE\tvpa\t12\tLNF"


class _DummyScheme:
    name = "dummy"
    loci = ["pyrC"]

    @staticmethod
    def lookup_st(_allele_ids: dict[str, str]) -> int | None:
        return 42


def test_lookup_st_forces_none_on_multicopy_conflict() -> None:
    calls = {
        "pyrC": LocusCall(
            locus="pyrC",
            allele_id="1",
            call_type="exact",
            confidence=1.0,
            multiple_hits=True,
            allele_ids=["1", "2"],
        )
    }
    result = lookup_st("s1", cast(Scheme, _DummyScheme()), calls)
    assert result.st is None
