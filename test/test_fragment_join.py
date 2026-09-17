"""Unit tests for gmlst.calling.fragment_join (pure logic, no aligners)."""

from __future__ import annotations

import random

from gmlst.aligners.base import AlleleMatch
from gmlst.calling.fragment_join import join_locus_fragments

ALLELE_LENGTH = 400


def _random_seq(length: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


def _fragment(
    seq: str,
    start: int,
    *,
    allele_id: str = "1",
    strand: str = "+",
    contig: str = "contig1",
    identity: float = 100.0,
    score: float = 100.0,
    allele_length: int = ALLELE_LENGTH,
) -> AlleleMatch:
    end = start + len(seq)
    return AlleleMatch(
        locus="L1",
        allele_id=allele_id,
        identity=identity,
        coverage=len(seq) / allele_length,
        strand=strand,
        score=score,
        alignment_length=len(seq),
        sequence=seq,
        query_contig=contig,
        allele_length=allele_length,
        allele_start=start,
        allele_end=end,
    )


def _join(fragments: list[AlleleMatch]):
    return join_locus_fragments(fragments, min_identity=95.0, min_coverage=0.95)


class TestOverlapAgree:
    def test_reconstructs_tiled_sequence_exactly(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=1)
        joined = _join(
            [
                _fragment(allele[:260], 0, contig="cA"),
                _fragment(allele[200:], 200, contig="cB"),
            ]
        )
        assert joined is not None
        assert joined.kind == "reconstructed"
        assert joined.synthetic is not None
        assert joined.synthetic.sequence == allele
        assert joined.synthetic.identity == 100.0
        assert joined.synthetic.coverage == 1.0
        assert joined.synthetic.strand == "+"
        assert joined.synthetic.allele_id == "1"
        assert joined.joint_coverage == 1.0
        assert joined.fragment_coords == [
            {"contig": "cA", "allele_start": 0, "allele_end": 260},
            {"contig": "cB", "allele_start": 200, "allele_end": 400},
        ]

    def test_partial_span_reconstruction_coverage_is_span_fraction(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=2)
        joined = _join(
            [
                _fragment(allele[50:250], 50, contig="cA"),
                _fragment(allele[200:350], 200, contig="cB"),
            ]
        )
        assert joined is not None
        assert joined.kind == "reconstructed"
        assert joined.synthetic is not None
        assert joined.synthetic.sequence == allele[50:350]
        assert joined.synthetic.coverage == 300 / ALLELE_LENGTH

    def test_three_fragment_chain_reconstructs(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=3)
        joined = _join(
            [
                _fragment(allele[200:], 200, contig="cC"),
                _fragment(allele[:180], 0, contig="cA"),
                _fragment(allele[150:330], 150, contig="cB"),
            ]
        )
        assert joined is not None
        assert joined.kind == "reconstructed"
        assert joined.synthetic is not None
        assert joined.synthetic.sequence == allele
        assert len(joined.fragment_coords) == 3

    def test_identity_is_length_weighted(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=4)
        mutated = allele[200:]
        pos = mutated.find("A", 60)  # mutate outside the shared [200, 260) interval
        assert pos >= 60
        mutated = mutated[:pos] + "T" + mutated[pos + 1 :]
        joined = _join(
            [
                _fragment(allele[:260], 0, contig="cA"),
                _fragment(mutated, 200, contig="cB", identity=99.0),
            ]
        )
        assert joined is not None
        assert joined.synthetic is not None
        # 260 tiled bases at 100% + 140 fresh bases at 99% → < 100, never exact
        assert joined.synthetic.identity < 100.0
        assert joined.synthetic.identity == (260 * 100.0 + 140 * 99.0) / 400

    def test_fully_contained_second_fragment_reconstructs(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=5)
        joined = _join(
            [
                _fragment(allele, 0, contig="cA"),
                _fragment(allele[100:200], 100, contig="cB"),
            ]
        )
        assert joined is not None
        assert joined.synthetic is not None
        assert joined.synthetic.sequence == allele


class TestOverlapDisagree:
    def test_snp_in_overlap_rejects_join(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=6)
        mutated = allele[200:]
        pos = mutated.find("A", 0, 60)  # mutate inside the shared [200, 260) interval
        assert 0 <= pos < 60
        mutated = mutated[:pos] + "T" + mutated[pos + 1 :]
        joined = _join(
            [
                _fragment(allele[:260], 0, contig="cA"),
                _fragment(mutated, 200, contig="cB"),
            ]
        )
        assert joined is None


class TestDisjoint:
    def test_disjoint_returns_joint_coverage(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=7)
        joined = _join(
            [
                _fragment(allele[:200], 0, contig="cA"),
                _fragment(allele[200:], 200, contig="cB"),
            ]
        )
        assert joined is not None
        assert joined.kind == "joint"
        assert joined.synthetic is None
        assert joined.joint_coverage == 1.0
        assert len(joined.fragment_coords) == 2

    def test_disjoint_with_gap_excludes_gap_from_coverage(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=8)
        joined = _join(
            [
                _fragment(allele[:190], 0, contig="cA"),
                _fragment(allele[200:], 200, contig="cB"),
            ]
        )
        assert joined is not None
        assert joined.kind == "joint"
        assert joined.joint_coverage == 390 / ALLELE_LENGTH

    def test_half_covered_fragments_joint_coverage(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=9)
        joined = _join(
            [
                _fragment(allele[:100], 0, contig="cA"),
                _fragment(allele[300:], 300, contig="cB"),
            ]
        )
        assert joined is not None
        assert joined.joint_coverage == 0.5


class TestGrouping:
    def test_strand_mismatch_groups_separately_no_join(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=10)
        joined = _join(
            [
                _fragment(allele[:260], 0, contig="cA", strand="+"),
                _fragment(allele[200:], 200, contig="cB", strand="-"),
            ]
        )
        assert joined is None

    def test_allele_mismatch_groups_separately_single_joinable_wins(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=11)
        other = _random_seq(ALLELE_LENGTH, seed=12)
        joined = _join(
            [
                _fragment(allele[:260], 0, contig="cA"),
                _fragment(allele[200:], 200, contig="cB"),
                _fragment(other[:260], 0, allele_id="2", contig="cA"),
            ]
        )
        assert joined is not None
        assert joined.allele_id == "1"
        assert joined.kind == "reconstructed"

    def test_chimeric_equal_strength_groups_rejected(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=13)
        other = _random_seq(ALLELE_LENGTH, seed=14)
        joined = _join(
            [
                _fragment(allele[:260], 0, contig="cA"),
                _fragment(allele[200:], 200, contig="cB"),
                _fragment(other[:260], 0, allele_id="2", contig="cA"),
                _fragment(other[200:], 200, allele_id="2", contig="cB"),
            ]
        )
        assert joined is None

    def test_four_fragments_rejected(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=15)
        joined = _join(
            [
                _fragment(allele[:120], 0, contig="cA"),
                _fragment(allele[100:220], 100, contig="cB"),
                _fragment(allele[200:320], 200, contig="cC"),
                _fragment(allele[300:], 300, contig="cD"),
            ]
        )
        assert joined is None

    def test_single_fragment_no_join(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=16)
        assert _join([_fragment(allele, 0)]) is None

    def test_below_identity_fragments_ignored(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=17)
        assert (
            _join(
                [
                    _fragment(allele[:260], 0, identity=90.0),
                    _fragment(allele[200:], 200, identity=90.0),
                ]
            )
            is None
        )

    def test_fragment_without_sequence_ignored(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=18)
        frag = _fragment(allele[:260], 0)
        frag.sequence = None
        assert _join([frag, _fragment(allele[200:], 200)]) is None


class TestMinusStrand:
    def test_minus_strand_fragments_join_without_revcomp(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=19)
        joined = _join(
            [
                _fragment(allele[:260], 0, contig="cA", strand="-"),
                _fragment(allele[200:], 200, contig="cB", strand="-"),
            ]
        )
        assert joined is not None
        assert joined.kind == "reconstructed"
        assert joined.synthetic is not None
        # Sequences are already allele-oriented: no reverse-complementing.
        assert joined.synthetic.sequence == allele
        assert joined.synthetic.strand == "-"

    def test_minus_strand_disjoint_joint(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=20)
        joined = _join(
            [
                _fragment(allele[:200], 0, contig="cA", strand="-"),
                _fragment(allele[200:], 200, contig="cB", strand="-"),
            ]
        )
        assert joined is not None
        assert joined.kind == "joint"
        assert joined.joint_coverage == 1.0


class TestMinJoinOverlapParameter:
    def test_small_overlap_below_threshold_degrades_to_joint(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=7)
        joined = join_locus_fragments(
            [
                _fragment(allele[:210], 0, contig="cA"),
                _fragment(allele[200:], 200, contig="cB"),
            ],
            min_identity=95.0,
            min_coverage=0.95,
            min_join_overlap=20,
        )
        assert joined is not None
        assert joined.kind == "joint"
        assert joined.joint_coverage == 1.0

    def test_same_overlap_at_lower_threshold_reconstructs(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=7)
        joined = join_locus_fragments(
            [
                _fragment(allele[:210], 0, contig="cA"),
                _fragment(allele[200:], 200, contig="cB"),
            ],
            min_identity=95.0,
            min_coverage=0.95,
            min_join_overlap=10,
        )
        assert joined is not None
        assert joined.kind == "reconstructed"
        assert joined.synthetic is not None
        assert joined.synthetic.sequence == allele

    def test_zero_threshold_still_requires_an_overlap(self) -> None:
        allele = _random_seq(ALLELE_LENGTH, seed=9)
        joined = join_locus_fragments(
            [
                _fragment(allele[:200], 0, contig="cA"),
                _fragment(allele[200:], 200, contig="cB"),
            ],
            min_identity=95.0,
            min_coverage=0.95,
            min_join_overlap=0,
        )
        assert joined is not None
        assert joined.kind == "joint"
