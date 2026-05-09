from __future__ import annotations

from pathlib import Path

import gmlst.aligners.minimap2 as minimap2_mod
from gmlst.aligners.base import AlleleMatch
from gmlst.aligners.minimap2 import (
    Minimap2Aligner,
    _build_targeted_validation_shortlist,
    _iter_canonical_kmer_codes,
    _iter_canonical_kmers,
    _parse_paf_fastq,
)
from gmlst.readers.sample import SampleInput


def test_parse_paf_fastq_uses_per_read_per_locus_winner(tmp_path: Path) -> None:
    paf = tmp_path / "hits.paf"
    paf.write_text(
        "\n".join(
            [
                "r1\t100\t0\t100\t+\tabc_1\t200\t0\t100\t90\t100\t20",
                "r1\t100\t0\t100\t+\tabc_2\t200\t0\t100\t85\t100\t20",
                "r2\t100\t0\t100\t+\tabc_1\t200\t100\t200\t95\t100\t30",
                "r2\t100\t0\t100\t+\tabc_2\t200\t100\t200\t80\t100\t30",
                "r3\t100\t0\t100\t+\tdef_4\t100\t0\t100\t100\t100\t40",
            ]
        )
        + "\n"
    )

    matches = _parse_paf_fastq(paf, ["abc", "def"])
    by_key = {(m.locus, m.allele_id): m for m in matches}

    assert ("abc", "1") in by_key
    assert ("abc", "2") not in by_key
    assert ("def", "4") in by_key

    abc = by_key[("abc", "1")]
    assert abc.coverage == 1.0
    assert abc.depth == 1.0
    assert abc.identity == 92.5


def test_parse_paf_fastq_uses_breadth_from_interval_union(tmp_path: Path) -> None:
    paf = tmp_path / "overlap.paf"
    paf.write_text(
        "\n".join(
            [
                "r1\t100\t0\t100\t+\tabc_3\t300\t0\t100\t98\t100\t25",
                "r2\t100\t0\t100\t+\tabc_3\t300\t50\t150\t97\t100\t25",
            ]
        )
        + "\n"
    )

    matches = _parse_paf_fastq(paf, ["abc"])
    assert len(matches) == 1
    hit = matches[0]

    assert hit.locus == "abc"
    assert hit.allele_id == "3"
    assert hit.coverage == 0.5
    assert hit.depth is not None
    assert round(hit.depth, 4) == round(200 / 150, 4)
    assert hit.identity == 97.5


def test_parse_paf_fastq_assigns_each_read_once_per_locus(tmp_path: Path) -> None:
    paf = tmp_path / "multi_locus.paf"
    paf.write_text(
        "\n".join(
            [
                "r1/1\t100\t0\t100\t+\tabc_1\t200\t0\t100\t95\t100\t10",
                "r1/1\t100\t0\t100\t+\tdef_2\t200\t0\t100\t90\t100\t10",
            ]
        )
        + "\n"
    )

    matches = _parse_paf_fastq(paf, ["abc", "def"])
    by_key = {(m.locus, m.allele_id): m for m in matches}

    assert ("abc", "1") in by_key
    assert ("def", "2") in by_key


def test_parse_paf_fastq_downweights_ambiguous_read_locus_hits(tmp_path: Path) -> None:
    paf = tmp_path / "ambiguous.paf"
    paf.write_text(
        "\n".join(
            [
                "r1/1\t100\t0\t100\t+\tabc_1\t200\t0\t100\t100\t100\t0",
                "r1/1\t100\t0\t100\t+\tabc_2\t200\t0\t100\t100\t100\t0",
            ]
        )
        + "\n"
    )

    matches = _parse_paf_fastq(paf, ["abc"])
    assert len(matches) == 1
    assert matches[0].locus == "abc"
    assert matches[0].score == 0.5


def test_canonical_kmer_codes_match_string_canonical_order() -> None:
    seq = "ACGTNACGTTTACGTAACCGGNACGTACGT"
    k = 5
    string_kmers = list(_iter_canonical_kmers(seq, k))
    code_kmers = list(_iter_canonical_kmer_codes(seq, k))

    assert len(string_kmers) == len(code_kmers)

    base_bits = {"A": 0, "C": 1, "G": 2, "T": 3}

    def encode(kmer: str) -> int:
        code = 0
        for base in kmer:
            code = (code << 2) | base_bits[base]
        return code

    assert [encode(kmer) for kmer in string_kmers] == code_kmers


def test_build_targeted_validation_shortlist_expands_for_mlst() -> None:
    shortlist = {
        "abc": [
            AlleleMatch(
                locus="abc", allele_id="2", identity=99.0, coverage=0.7, score=5.0
            )
        ]
    }
    top = {
        "abc": AlleleMatch(
            locus="abc",
            allele_id="2",
            identity=99.0,
            coverage=0.7,
            score=5.0,
            depth=2.0,
        )
    }
    seqs = {
        ("abc", "1"): "ACGT",
        ("abc", "2"): "ACGT",
        ("abc", "3"): "ACGT",
    }
    support = {("abc", "1"): 3.0}

    expanded = _build_targeted_validation_shortlist(
        shortlist,
        top,
        seqs,
        support,
        total_loci=7,
    )

    assert [c.allele_id for c in expanded["abc"]] == ["2", "1", "3"]
    assert expanded["abc"][1].score == 3.0


def test_build_targeted_validation_shortlist_uses_top_only_for_large_scheme() -> None:
    shortlist = {
        "abc": [
            AlleleMatch(
                locus="abc", allele_id="2", identity=99.0, coverage=0.7, score=5.0
            )
        ]
    }
    top = {
        "abc": AlleleMatch(
            locus="abc", allele_id="2", identity=99.0, coverage=0.7, score=5.0
        )
    }
    seqs = {
        ("abc", "1"): "ACGT",
        ("abc", "2"): "ACGT",
    }

    expanded = _build_targeted_validation_shortlist(
        shortlist,
        top,
        seqs,
        {},
        total_loci=100,
    )

    assert list(expanded) == ["abc"]
    assert [c.allele_id for c in expanded["abc"]] == ["2"]


def test_align_fasta_respects_emit_cigar_flag(monkeypatch, tmp_path: Path) -> None:
    genome = tmp_path / "genome.fna"
    genome.write_text(">contig\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "alleles.fasta").write_text(">abc_1\nATGCGTACGTTAGCTAGCTA\n")

    commands: list[list[str]] = []

    def fake_run_cmd(cmd: list[str]) -> None:
        commands.append(cmd)

    monkeypatch.setattr(minimap2_mod, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(minimap2_mod, "_parse_paf", lambda *_a, **_k: [])

    Minimap2Aligner(threads=1, fasta_emit_cigar=True)._align_fasta(
        genome,
        index_dir,
        ["abc"],
    )
    Minimap2Aligner(threads=1, fasta_emit_cigar=False)._align_fasta(
        genome,
        index_dir,
        ["abc"],
    )

    assert "-c" in commands[0]
    assert "-c" not in commands[1]


def test_align_fastq_pair_preserves_normalized_sample_id(
    monkeypatch, tmp_path: Path
) -> None:
    r1 = tmp_path / "sample_R1.fastq.gz"
    r2 = tmp_path / "sample_R2.fastq.gz"
    r1.write_text("@r1\nATGC\n+\n####\n")
    r2.write_text("@r2\nATGC\n+\n####\n")
    index_dir = tmp_path / "idx"
    index_dir.mkdir()

    monkeypatch.setattr(
        Minimap2Aligner, "_align_fastq", lambda self, *_args, **_kwargs: []
    )

    sample = SampleInput.from_fastq_pair(r1, r2, "sample")
    aligner = Minimap2Aligner(threads=1)
    result = aligner.align((sample.path, sample.mate_path), index_dir, ["abc"], "fastq")

    assert result.sample_id == "sample"


def test_align_fasta_applies_fast_speed_profile(monkeypatch, tmp_path: Path) -> None:
    genome = tmp_path / "genome.fna"
    genome.write_text(">contig\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "alleles.fasta").write_text(">abc_1\nATGCGTACGTTAGCTAGCTA\n")

    commands: list[list[str]] = []

    def fake_run_cmd(cmd: list[str]) -> None:
        commands.append(cmd)

    monkeypatch.setattr(minimap2_mod, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(minimap2_mod, "_parse_paf", lambda *_a, **_k: [])

    Minimap2Aligner(
        threads=1,
        fasta_emit_cigar=False,
        fasta_speed_profile="fast",
    )._align_fasta(
        genome,
        index_dir,
        ["abc"],
    )

    cmd = commands[0]
    assert "-w" in cmd
    assert cmd[cmd.index("-w") + 1] == "15"
    assert "-e" in cmd
    assert cmd[cmd.index("-e") + 1] == "1000"
    assert "-K" in cmd
    assert cmd[cmd.index("-K") + 1] == "1G"
    assert "-f" not in cmd
    assert "-U" not in cmd


def test_align_fasta_applies_ultrafast_speed_profile(
    monkeypatch, tmp_path: Path
) -> None:
    genome = tmp_path / "genome.fna"
    genome.write_text(">contig\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "alleles.fasta").write_text(">abc_1\nATGCGTACGTTAGCTAGCTA\n")

    commands: list[list[str]] = []

    def fake_run_cmd(cmd: list[str]) -> None:
        commands.append(cmd)

    monkeypatch.setattr(minimap2_mod, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(minimap2_mod, "_parse_paf", lambda *_a, **_k: [])

    Minimap2Aligner(
        threads=1,
        fasta_emit_cigar=False,
        fasta_speed_profile="ultrafast",
    )._align_fasta(
        genome,
        index_dir,
        ["abc"],
    )

    cmd = commands[0]
    assert "-w" in cmd
    assert cmd[cmd.index("-w") + 1] == "15"
    assert "-e" in cmd
    assert cmd[cmd.index("-e") + 1] == "1000"
    assert "-f" in cmd
    assert cmd[cmd.index("-f") + 1] == "0.001"
    assert "-U" in cmd
    assert cmd[cmd.index("-U") + 1] == "50,1000"
    assert "-K" in cmd
    assert cmd[cmd.index("-K") + 1] == "1G"
