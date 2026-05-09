from gmlst.aligners.base import AlignmentResult, AlleleMatch


def test_alignment_result_matches_for_uses_grouped_cache() -> None:
    result = AlignmentResult(
        sample_id="s1",
        matches=[
            AlleleMatch(locus="a", allele_id="1", identity=99.0, coverage=0.9),
            AlleleMatch(locus="b", allele_id="2", identity=97.0, coverage=0.8),
            AlleleMatch(locus="a", allele_id="3", identity=100.0, coverage=1.0),
        ],
    )

    hits_first = result.matches_for("a")
    hits_second = result.matches_for("a")

    assert [hit.allele_id for hit in hits_first] == ["3", "1"]
    assert [hit.allele_id for hit in hits_second] == ["3", "1"]
    assert result.matches_for("missing") == []
