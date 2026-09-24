"""Tests for MLST result quality scoring (gmlst.calling.scoring)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from click.testing import CliRunner

from gmlst.calling.allele import LocusCall
from gmlst.calling.scoring import (
    locus_score,
    passes_minscore,
    sample_score,
    sample_status,
    score_result,
)
from gmlst.calling.st_lookup import STResult


def _call(
    locus: str = "abc",
    call_type: str = "exact",
    confidence: float = 1.0,
    allele_id: str | None = "1",
    multiple_hits: bool = False,
) -> LocusCall:
    return LocusCall(
        locus=locus,
        allele_id=allele_id,
        call_type=call_type,
        confidence=confidence,
        multiple_hits=multiple_hits,
    )


def _result(
    calls: dict[str, LocusCall],
    st: int | None = 1,
) -> STResult:
    return STResult(
        sample_id="s1",
        scheme="x_1",
        st=st,
        locus_calls=calls,
    )


# ---------------------------------------------------------------------------
# locus_score
# ---------------------------------------------------------------------------


def test_locus_score_exact_is_100() -> None:
    assert locus_score(_call(call_type="exact", confidence=0.42)) == 100.0


def test_locus_score_missing_and_none_are_0() -> None:
    assert locus_score(_call(call_type="missing", allele_id=None)) == 0.0
    assert locus_score(None) == 0.0


def test_locus_score_conflicting_multicopy_is_0() -> None:
    call = _call(call_type="exact", multiple_hits=True)
    assert locus_score(call) == 0.0


def test_locus_score_scales_with_confidence() -> None:
    assert locus_score(_call(call_type="closest", confidence=0.87)) == 87.0
    assert locus_score(_call(call_type="partial", confidence=0.25)) == 25.0


def test_locus_score_clamps_confidence_range() -> None:
    assert locus_score(_call(call_type="closest", confidence=1.5)) == 100.0
    assert locus_score(_call(call_type="closest", confidence=-0.2)) == 0.0


# ---------------------------------------------------------------------------
# sample_score
# ---------------------------------------------------------------------------


def test_sample_score_mean_over_all_loci() -> None:
    calls = {f"l{i}": _call(locus=f"l{i}") for i in range(6)}
    calls["l6"] = _call(locus="l6", call_type="missing", allele_id=None)

    assert sample_score(_result(calls)) == 85.7


def test_sample_score_empty_result_is_0() -> None:
    assert sample_score(_result({})) == 0.0


# ---------------------------------------------------------------------------
# sample_status
# ---------------------------------------------------------------------------


def test_status_perfect_for_exact_profile_with_st() -> None:
    calls = {"a": _call(locus="a"), "b": _call(locus="b")}
    assert sample_status(_result(calls, st=7), 100.0) == "PERFECT"


def test_status_novel_for_exact_profile_without_st() -> None:
    calls = {"a": _call(locus="a"), "b": _call(locus="b")}
    assert sample_status(_result(calls, st=None), 100.0) == "NOVEL"


def test_status_novel_for_complete_novel_calls() -> None:
    calls = {
        "a": _call(locus="a", call_type="novel", confidence=0.95),
        "b": _call(locus="b", call_type="novel", confidence=0.95),
    }
    assert sample_status(_result(calls, st=None), 95.0) == "NOVEL"


def test_status_missing_when_locus_missing_and_score_ok() -> None:
    calls = {
        "a": _call(locus="a"),
        "b": _call(locus="b", call_type="missing", allele_id=None),
    }
    assert sample_status(_result(calls, st=None), 50.0) == "MISSING"


def test_status_bad_when_score_below_threshold() -> None:
    calls = {
        "a": _call(locus="a", call_type="partial", confidence=0.1),
        "b": _call(locus="b", call_type="partial", confidence=0.1),
    }
    assert sample_status(_result(calls, st=None), 10.0) == "BAD"


def test_status_mixed_for_conflicting_multicopy() -> None:
    calls = {
        "a": _call(locus="a", multiple_hits=True),
        "b": _call(locus="b"),
    }
    assert sample_status(_result(calls, st=None), 50.0) == "MIXED"


def test_status_none_for_empty_calls() -> None:
    assert sample_status(_result({}), 0.0) == "NONE"


# ---------------------------------------------------------------------------
# score_result + minscore gate
# ---------------------------------------------------------------------------


def test_score_result_combines_score_and_status() -> None:
    calls = {"a": _call(locus="a"), "b": _call(locus="b")}
    scored = score_result(_result(calls, st=3))
    assert scored.score == 100.0
    assert scored.status == "PERFECT"


def test_passes_minscore_inclusive_boundary() -> None:
    calls = {"a": _call(locus="a", call_type="closest", confidence=0.6)}
    result = _result(calls, st=None)
    assert passes_minscore(result, 60.0)
    assert not passes_minscore(result, 60.1)


# ---------------------------------------------------------------------------
# Wire-in regression: scores reach the JSON payload (old confidence.py never did)
# ---------------------------------------------------------------------------


def test_st_result_to_dict_includes_score_and_status() -> None:
    calls = {"a": _call(locus="a"), "b": _call(locus="b")}
    payload: dict[str, Any] = _result(calls, st=3).to_dict()

    assert payload["score"] == 100.0
    assert payload["status"] == "PERFECT"


def test_cli_typing_minscore_option_is_plumbed(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing", fake_run_mlst_like_typing
    )
    sample = tmp_path / "sample.fna"
    sample.write_text(">c1\nacgt\n")

    from gmlst.cli import main

    result = CliRunner().invoke(
        main, ["typing", "mlst", "-s", "x_1", "--minscore", "60", str(sample)]
    )

    assert result.exit_code == 0, result.output
    assert captured.get("minscore") == 60.0
