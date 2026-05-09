from __future__ import annotations

from gmlst.kmer_prefilter import prefilter_assembly_candidates


def test_prefilter_prioritizes_exact_allele() -> None:
    allele_sequences = {
        ("locusA", "1"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA",
        ("locusA", "2"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCAA",
        ("locusB", "1"): "CCCCGGGGAAAATTTTCCCCGGGGAAAATTTTCCCC",
    }
    assembly_sequences = [
        "TTTTATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTATTTT",
        "GGGGCCCCGGGGAAAATTTTCCCCGGGGAAAATTTTCCCCAAAA",
    ]

    candidates = prefilter_assembly_candidates(
        allele_sequences=allele_sequences,
        assembly_sequences=assembly_sequences,
        k=21,
        top_n=2,
    )

    assert candidates["locusA"][0][0] == "1"
    assert candidates["locusB"][0][0] == "1"


def test_prefilter_honors_top_n_limit() -> None:
    allele_sequences = {
        ("locusA", "1"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA",
        ("locusA", "2"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCAA",
        ("locusA", "3"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCCC",
    }
    assembly_sequences = ["ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA"]

    candidates = prefilter_assembly_candidates(
        allele_sequences=allele_sequences,
        assembly_sequences=assembly_sequences,
        k=21,
        top_n=1,
    )

    assert len(candidates["locusA"]) == 1


def test_prefilter_excludes_unmatched_zero_score_alleles() -> None:
    allele_sequences = {
        ("locusA", "1"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA",
        ("locusA", "2"): "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    }
    assembly_sequences = ["ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA"]

    candidates = prefilter_assembly_candidates(
        allele_sequences=allele_sequences,
        assembly_sequences=assembly_sequences,
        k=21,
        top_n=2,
    )

    assert "locusA" in candidates
    ranked = candidates["locusA"]
    assert ranked
    assert all(score > 0.0 for _, score in ranked)
    assert [allele_id for allele_id, _ in ranked] == ["1"]


def test_prefilter_does_not_emit_candidates_without_matches() -> None:
    allele_sequences = {
        ("locusA", "1"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA",
        ("locusB", "1"): "CCCCGGGGAAAATTTTCCCCGGGGAAAATTTTCCCC",
    }
    assembly_sequences = ["ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA"]

    candidates = prefilter_assembly_candidates(
        allele_sequences=allele_sequences,
        assembly_sequences=assembly_sequences,
        k=21,
        top_n=2,
    )

    assert "locusA" in candidates
    assert "locusB" not in candidates


def test_prefilter_supports_stride_sampling() -> None:
    allele_sequences = {
        ("locusA", "1"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA",
        ("locusA", "2"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCAA",
    }
    assembly_sequences = ["ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA"]

    candidates = prefilter_assembly_candidates(
        allele_sequences=allele_sequences,
        assembly_sequences=assembly_sequences,
        k=21,
        top_n=2,
        stride=4,
    )

    assert "locusA" in candidates
    assert candidates["locusA"][0][0] == "1"


def test_prefilter_rejects_non_positive_stride() -> None:
    allele_sequences = {("locusA", "1"): "ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA"}
    assembly_sequences = ["ATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA"]

    try:
        prefilter_assembly_candidates(
            allele_sequences=allele_sequences,
            assembly_sequences=assembly_sequences,
            k=21,
            top_n=1,
            stride=0,
        )
    except ValueError as exc:
        assert "stride" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-positive stride")
