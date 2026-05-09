from __future__ import annotations

from gmlst.core.prefilter import prefilter_is_confident_impl


def test_prefilter_is_confident_returns_false_when_total_loci_non_positive() -> None:
    assert (
        prefilter_is_confident_impl(
            {"abc": [("1", 0.9)]},
            total_loci=0,
            min_loci_fraction=0.5,
        )
        is False
    )


def test_prefilter_is_confident_clamps_fraction_bounds() -> None:
    candidates = {"abc": [("1", 0.9)]}
    assert (
        prefilter_is_confident_impl(
            candidates,
            total_loci=3,
            min_loci_fraction=-1.0,
        )
        is True
    )
    assert (
        prefilter_is_confident_impl(
            candidates,
            total_loci=3,
            min_loci_fraction=2.0,
        )
        is False
    )


def test_prefilter_is_confident_uses_ceil_for_fraction_threshold() -> None:
    candidates = {
        "abc": [("1", 0.9)],
        "def": [],
        "ghi": [],
        "jkl": [],
    }
    assert (
        prefilter_is_confident_impl(
            candidates,
            total_loci=4,
            min_loci_fraction=0.26,
        )
        is False
    )
