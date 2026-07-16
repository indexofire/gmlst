"""Behavior tests for aligner output parsing functions.

Tests _parse_coords (nucmer) and _parse_blast_output (blastn) with
sample output files, covering normal hits, filtering thresholds,
malformed lines, and edge cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gmlst.aligners.blastn import _parse_blast_output
from gmlst.aligners.nucmer import _MIN_COVERAGE, _MIN_IDENTITY, _parse_coords

# ---------------------------------------------------------------------------
# _parse_coords (nucmer)
# ---------------------------------------------------------------------------


class TestParseCoords:
    loci = ["abcZ", "adk"]

    def _write_coords(self, path: Path, rows: list[str]) -> None:
        path.write_text("\n".join(rows) + "\n")

    def _make_row(
        self,
        allele: str = "abcZ_1",
        identity: float = 100.0,
        covq: float = 100.0,
        aln_len: int = 500,
    ) -> str:
        return "\t".join(
            [
                "1",
                "500",
                "1",
                "500",
                str(aln_len),
                "500",
                str(identity),
                "500",
                "500",
                "100.00",
                f"{covq:.2f}",
                "contig1",
                allele,
            ]
        )

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        result = _parse_coords(tmp_path / "nonexistent", self.loci)
        assert result == []

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        coords = tmp_path / "empty.tsv"
        coords.write_text("")
        result = _parse_coords(coords, self.loci)
        assert result == []

    def test_single_valid_hit(self, tmp_path: Path) -> None:
        coords = tmp_path / "hits.tsv"
        self._write_coords(coords, [self._make_row("abcZ_1", 100.0, 100.0)])
        result = _parse_coords(coords, self.loci)
        assert len(result) == 1
        assert result[0].locus == "abcZ"
        assert result[0].allele_id == "1"
        assert result[0].identity == 100.0
        assert result[0].coverage == 1.0

    def test_best_hit_wins_on_identity(self, tmp_path: Path) -> None:
        coords = tmp_path / "hits.tsv"
        self._write_coords(
            coords,
            [
                self._make_row("abcZ_1", 95.0, 100.0),
                self._make_row("abcZ_1", 99.0, 90.0),
            ],
        )
        result = _parse_coords(coords, self.loci)
        assert len(result) == 1
        assert result[0].identity == 99.0

    def test_filters_below_min_identity(self, tmp_path: Path) -> None:
        coords = tmp_path / "hits.tsv"
        self._write_coords(
            coords,
            [self._make_row("abcZ_1", _MIN_IDENTITY - 1, 100.0)],
        )
        result = _parse_coords(coords, self.loci)
        assert result == []

    def test_filters_below_min_coverage(self, tmp_path: Path) -> None:
        coords = tmp_path / "hits.tsv"
        covq_below = (_MIN_COVERAGE * 100.0) - 1.0
        self._write_coords(
            coords,
            [self._make_row("abcZ_1", 100.0, covq_below)],
        )
        result = _parse_coords(coords, self.loci)
        assert result == []

    def test_skips_unknown_locus(self, tmp_path: Path) -> None:
        coords = tmp_path / "hits.tsv"
        self._write_coords(coords, [self._make_row("unknown_1", 100.0, 100.0)])
        result = _parse_coords(coords, self.loci)
        assert result == []

    def test_skips_malformed_line(self, tmp_path: Path) -> None:
        coords = tmp_path / "hits.tsv"
        self._write_coords(
            coords,
            [
                "garbage\tline\twith\tfew\tcolumns",
                self._make_row("abcZ_1", 100.0, 100.0),
            ],
        )
        result = _parse_coords(coords, self.loci)
        assert len(result) == 1

    def test_skips_header_line(self, tmp_path: Path) -> None:
        coords = tmp_path / "hits.tsv"
        self._write_coords(
            coords,
            [
                "/home/user/ref/ref.fasta /home/user/query/q.fasta",
                "NUCMER",
                self._make_row("abcZ_1", 100.0, 100.0),
            ],
        )
        result = _parse_coords(coords, self.loci)
        assert len(result) == 1

    def test_multiple_loci(self, tmp_path: Path) -> None:
        coords = tmp_path / "hits.tsv"
        self._write_coords(
            coords,
            [
                self._make_row("abcZ_1", 100.0, 100.0),
                self._make_row("adk_3", 98.5, 95.0),
            ],
        )
        result = _parse_coords(coords, self.loci)
        assert len(result) == 2
        loci_found = {m.locus for m in result}
        assert loci_found == {"abcZ", "adk"}


# ---------------------------------------------------------------------------
# _parse_blast_output (blastn)
# ---------------------------------------------------------------------------


class TestParseBlastOutput:
    loci = ["arcC", "aroE"]

    def _write_blast(self, path: Path, rows: list[str]) -> None:
        path.write_text("\n".join(rows) + "\n")

    def _make_row(
        self,
        qseqid: str = "arcC_1",
        sseqid: str = "contig1",
        pident: float = 100.0,
        length: int = 480,
        qlen: int = 480,
        qstart: int = 1,
        qend: int = 480,
        sstart: int = 100,
        send: int = 579,
        evalue: str = "0.0",
        bitscore: str = "900",
        sseq: str = "",
    ) -> str:
        fields = [
            qseqid,
            sseqid,
            f"{pident}",
            str(length),
            str(qlen),
            str(qstart),
            str(qend),
            str(sstart),
            str(send),
            evalue,
            bitscore,
        ]
        if sseq:
            fields.append(sseq)
        return "\t".join(fields)

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        result = _parse_blast_output(tmp_path / "nonexistent", self.loci)
        assert result == []

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        blast = tmp_path / "empty.tsv"
        blast.write_text("")
        result = _parse_blast_output(blast, self.loci)
        assert result == []

    def test_single_valid_hit(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(blast, [self._make_row("arcC_1", pident=100.0)])
        result = _parse_blast_output(blast, self.loci)
        assert len(result) == 1
        assert result[0].locus == "arcC"
        assert result[0].allele_id == "1"
        assert result[0].identity == 100.0
        assert result[0].coverage == 1.0

    def test_best_hit_wins_on_identity(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(
            blast,
            [
                self._make_row("arcC_1", pident=95.0, length=480, qlen=480),
                self._make_row("arcC_1", pident=99.0, length=400, qlen=480),
            ],
        )
        result = _parse_blast_output(blast, self.loci)
        assert len(result) == 1
        assert result[0].identity == 99.0

    def test_best_hit_same_identity_higher_coverage_wins(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(
            blast,
            [
                self._make_row("arcC_1", pident=98.0, length=400, qlen=480),
                self._make_row("arcC_1", pident=98.0, length=460, qlen=480),
            ],
        )
        result = _parse_blast_output(blast, self.loci)
        assert len(result) == 1
        assert result[0].coverage == pytest.approx(460 / 480)

    def test_skips_unknown_locus(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(blast, [self._make_row("glpF_1", pident=100.0)])
        result = _parse_blast_output(blast, self.loci)
        assert result == []

    def test_skips_comment_and_empty_lines(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(
            blast,
            [
                "# BLASTN 2.14.0+",
                "",
                self._make_row("arcC_1", pident=100.0),
            ],
        )
        result = _parse_blast_output(blast, self.loci)
        assert len(result) == 1

    def test_skips_short_lines(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(
            blast,
            [
                "arcC_1\tcontig1",
                self._make_row("arcC_1", pident=100.0),
            ],
        )
        result = _parse_blast_output(blast, self.loci)
        assert len(result) == 1

    def test_count_same_copy_sets_copy_count(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(
            blast,
            [
                self._make_row("arcC_1", sseqid="contig1", sstart=100, send=579),
                self._make_row("arcC_1", sseqid="contig2", sstart=200, send=679),
            ],
        )
        result = _parse_blast_output(blast, self.loci, count_same_copy=True)
        assert len(result) == 1
        assert result[0].copy_count == 2

    def test_count_same_copy_default_is_one(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(blast, [self._make_row("arcC_1", pident=100.0)])
        result = _parse_blast_output(blast, self.loci, count_same_copy=True)
        assert result[0].copy_count == 1

    def test_reverse_strand_detected(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(
            blast,
            [self._make_row("arcC_1", pident=100.0, sstart=579, send=100)],
        )
        result = _parse_blast_output(blast, self.loci)
        assert result[0].strand == "-"

    def test_multiple_loci(self, tmp_path: Path) -> None:
        blast = tmp_path / "hits.tsv"
        self._write_blast(
            blast,
            [
                self._make_row("arcC_1", pident=100.0),
                self._make_row("aroE_5", pident=97.0, length=450, qlen=450),
            ],
        )
        result = _parse_blast_output(blast, self.loci)
        assert len(result) == 2
        loci_found = {m.locus for m in result}
        assert loci_found == {"arcC", "aroE"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
