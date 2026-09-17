"""Integration tests for joint fragment allele reconstruction.

Drives the real blastn and minimap2 backends against synthetic genomes
where locus L1 is intact, split, overlapping, mutated, reversed, or gapped,
then asserts the resulting LocusCall. A local-scheme CLI fixture does not
exist in the suite yet, so the aligner+caller path is exercised directly.
"""

from __future__ import annotations

import random
import shutil
from pathlib import Path

import pytest

from gmlst.aligners.base import AlleleMatch
from gmlst.aligners.blastn import BlastnAligner
from gmlst.aligners.minimap2 import Minimap2Aligner
from gmlst.calling.allele import LocusCall, call_all_loci, call_best_allele
from gmlst.calling.st_lookup import lookup_st

_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def _revcomp(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def _mutate(seq: str, position: int) -> str:
    replacement = ({"A", "C", "G", "T"} - {seq[position]}).pop()
    return seq[:position] + replacement + seq[position + 1 :]


def _with_snps(seq: str, positions: list[int]) -> str:
    for position in positions:
        seq = _mutate(seq, position)
    return seq


def _random_seq(seed: int, length: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


ALLELE = _random_seq(101, 400)
ALLELE_2 = _with_snps(ALLELE, random.Random(202).sample(range(10, 390), 3))
FLANK_L = _random_seq(303, 200)
FLANK_R = _random_seq(404, 200)
ALLELE_600 = _random_seq(505, 600)
FLANK_600_L = _random_seq(606, 200)
FLANK_600_R = _random_seq(707, 200)


def _write_fasta(path: Path, records: dict[str, str]) -> Path:
    with path.open("w") as handle:
        for name, seq in records.items():
            handle.write(f">{name}\n{seq}\n")
    return path


def _build_scheme(tmp_path: Path, allele: str, allele_2: str) -> Path:
    scheme = tmp_path / "L1.tfa"
    scheme.write_text(f">L1_1\n{allele}\n>L1_2\n{allele_2}\n")
    return scheme


def _type_contigs(
    backend_cls: type, scheme_file: Path, contigs: dict[str, str], tmp_path: Path
) -> LocusCall:
    genome = _write_fasta(tmp_path / "genome.fna", contigs)
    index_dir = tmp_path / "index"
    aligner = backend_cls(threads=1)
    index_path = aligner.index([scheme_file], index_dir)
    result = aligner.align(genome, index_path, ["L1"], "fasta")
    return call_all_loci(result, ["L1"])["L1"]


BACKENDS = [
    pytest.param(
        BlastnAligner,
        id="blastn",
        marks=pytest.mark.skipif(
            shutil.which("blastn") is None or shutil.which("makeblastdb") is None,
            reason="BLAST+ tools not installed",
        ),
    ),
    pytest.param(
        Minimap2Aligner,
        id="minimap2",
        marks=pytest.mark.skipif(
            shutil.which("minimap2") is None, reason="minimap2 not installed"
        ),
    ),
]


@pytest.mark.parametrize("backend_cls", BACKENDS)
class TestJointAlignment:
    def test_intact_contig_calls_exact_without_fragments(
        self, backend_cls: type, tmp_path: Path
    ) -> None:
        scheme = _build_scheme(tmp_path, ALLELE, ALLELE_2)
        call = _type_contigs(
            backend_cls,
            scheme,
            {"c1": FLANK_L + ALLELE + FLANK_R},
            tmp_path,
        )
        assert call.call_type == "exact"
        assert call.allele_id == "1"
        assert call.best_match is not None
        assert call.best_match.identity == 100.0
        assert call.fragments is None

    def test_disjoint_split_stays_partial_with_joint_coverage(
        self, backend_cls: type, tmp_path: Path
    ) -> None:
        scheme = _build_scheme(tmp_path, ALLELE, ALLELE_2)
        call = _type_contigs(
            backend_cls,
            scheme,
            {
                "cA": FLANK_L + ALLELE[:200],
                "cB": ALLELE[200:] + FLANK_R,
            },
            tmp_path,
        )
        assert call.call_type == "partial"
        assert call.allele_id == "1"
        assert call.best_match is not None
        assert call.best_match.coverage == pytest.approx(1.0)
        assert call.fragments is not None
        assert len(call.fragments) == 2

    def test_overlap_split_reconstructed_to_exact(
        self, backend_cls: type, tmp_path: Path
    ) -> None:
        scheme = _build_scheme(tmp_path, ALLELE, ALLELE_2)
        call = _type_contigs(
            backend_cls,
            scheme,
            {
                "cA": FLANK_L + ALLELE[:260],
                "cB": ALLELE[200:] + FLANK_R,
            },
            tmp_path,
        )
        assert call.call_type == "exact"
        assert call.allele_id == "1"
        assert call.best_match is not None
        assert call.best_match.identity == 100.0
        assert call.best_match.sequence == ALLELE
        assert call.fragments is not None
        assert len(call.fragments) == 2

    def test_overlap_with_snp_stays_partial(
        self, backend_cls: type, tmp_path: Path
    ) -> None:
        scheme = _build_scheme(tmp_path, ALLELE, ALLELE_2)
        mutated_b = _mutate(ALLELE[200:], 30)
        call = _type_contigs(
            backend_cls,
            scheme,
            {
                "cA": FLANK_L + ALLELE[:260],
                "cB": mutated_b + FLANK_R,
            },
            tmp_path,
        )
        assert call.call_type == "partial"
        assert call.best_match is not None
        assert call.best_match.coverage < 0.95
        assert call.fragments is None

    def test_opposite_strand_second_fragment_stays_partial(
        self, backend_cls: type, tmp_path: Path
    ) -> None:
        scheme = _build_scheme(tmp_path, ALLELE, ALLELE_2)
        call = _type_contigs(
            backend_cls,
            scheme,
            {
                "cA": FLANK_L + ALLELE[:260],
                "cB": _revcomp(ALLELE[200:]) + FLANK_R,
            },
            tmp_path,
        )
        assert call.call_type == "partial"
        assert call.best_match is not None
        assert call.best_match.coverage == pytest.approx(260 / 400, abs=0.02)
        assert call.fragments is None

    def test_true_gap_never_exact_despite_full_coverage(
        self, backend_cls: type, tmp_path: Path
    ) -> None:
        scheme = _build_scheme(tmp_path, ALLELE, ALLELE_2)
        call = _type_contigs(
            backend_cls,
            scheme,
            {
                "cA": FLANK_L + ALLELE[:200] + "ACGTA",
                "cB": ALLELE[200:] + FLANK_R,
            },
            tmp_path,
        )
        assert call.call_type == "partial"
        assert call.best_match is not None
        assert call.best_match.coverage == pytest.approx(1.0)
        assert call.fragments is not None
        assert len(call.fragments) == 2

    def test_three_fragment_overlap_chain_reconstructs(
        self, backend_cls: type, tmp_path: Path
    ) -> None:
        scheme = _build_scheme(
            tmp_path, ALLELE_600, _with_snps(ALLELE_600, [100, 300, 500])
        )
        call = _type_contigs(
            backend_cls,
            scheme,
            {
                "cA": FLANK_600_L + ALLELE_600[:250],
                "cB": ALLELE_600[200:450],
                "cC": ALLELE_600[400:] + FLANK_600_R,
            },
            tmp_path,
        )
        assert call.call_type == "exact"
        assert call.allele_id == "1"
        assert call.fragments is not None
        assert len(call.fragments) == 3


class TestJointGateBelowSingleFragmentThreshold:
    """Regression: joint evidence must not be discarded below the 0.5 gate.

    A gene split into three disjoint ~33 % fragments leaves every single
    match under ``min_coverage * 0.5``; the joint coverage (~1.0) must
    still yield a partial call with the fragments listed, not "missing".
    """

    ALLELE_LENGTH = 300

    def _fragment(
        self, allele: str, start: int, end: int, *, contig: str
    ) -> AlleleMatch:
        return AlleleMatch(
            locus="L1",
            allele_id="1",
            identity=100.0,
            coverage=(end - start) / self.ALLELE_LENGTH,
            strand="+",
            score=100.0,
            alignment_length=end - start,
            sequence=allele[start:end],
            query_contig=contig,
            allele_length=self.ALLELE_LENGTH,
            allele_start=start,
            allele_end=end,
        )

    def test_three_way_split_reports_joint_partial_not_missing(self) -> None:
        allele = _random_seq(999, self.ALLELE_LENGTH)
        fragments = [
            self._fragment(allele, 0, 100, contig="cA"),
            self._fragment(allele, 100, 200, contig="cB"),
            self._fragment(allele, 200, 300, contig="cC"),
        ]

        call = call_best_allele(
            list(fragments),
            fragments=fragments,
            min_identity=95.0,
            min_coverage=0.95,
        )

        assert call.call_type == "partial"
        assert call.allele_id == "1"
        assert call.best_match is not None
        assert call.best_match.coverage == pytest.approx(1.0)
        assert call.fragments is not None
        assert [frag["contig"] for frag in call.fragments] == ["cA", "cB", "cC"]


class _FakeScheme:
    name = "test_scheme"

    def lookup_st(self, allele_ids: dict[str, str]) -> int | None:
        return None


class TestJsonSerialization:
    def test_partial_call_with_fragments_included_in_dict(self) -> None:
        best = AlleleMatch(
            locus="L1",
            allele_id="1",
            identity=100.0,
            coverage=1.0,
            strand="+",
            query_contig="cA",
        )
        call = LocusCall(
            locus="L1",
            allele_id="1",
            call_type="partial",
            confidence=1.0,
            best_match=best,
            fragments=[
                {"contig": "cA", "allele_start": 0, "allele_end": 200},
                {"contig": "cB", "allele_start": 200, "allele_end": 400},
            ],
        )
        payload = lookup_st("s1", _FakeScheme(), {"L1": call}).to_dict()
        locus_payload = payload["allele_calls"]["L1"]
        assert locus_payload["call_type"] == "partial"
        assert locus_payload["fragments"] == [
            {"contig": "cA", "allele_start": 0, "allele_end": 200},
            {"contig": "cB", "allele_start": 200, "allele_end": 400},
        ]

    def test_call_without_fragments_omits_key(self) -> None:
        best = AlleleMatch(locus="L1", allele_id="1", identity=100.0, coverage=1.0)
        call = LocusCall(
            locus="L1",
            allele_id="1",
            call_type="exact",
            confidence=1.0,
            best_match=best,
        )
        payload = lookup_st("s1", _FakeScheme(), {"L1": call}).to_dict()
        assert "fragments" not in payload["allele_calls"]["L1"]
