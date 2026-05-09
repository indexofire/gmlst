from __future__ import annotations

from pathlib import Path

from gmlst.novel.reader import NovelDataReader
from gmlst.novel.writer import NovelAlleleWriter


def test_novel_allele_fasta_roundtrip_preserves_multiple_samples(
    tmp_path: Path,
) -> None:
    writer = NovelAlleleWriter(tmp_path)
    assert writer.add_novel_allele("dnaN", "isoA", "ATGCATGC") == "n1"
    assert writer.add_novel_allele("dnaN", "isoB", "ATGCATGC") == "dnaN_n1"
    writer.write()

    alleles_by_locus, profiles = NovelDataReader(tmp_path).read_all()

    assert profiles == []
    assert list(alleles_by_locus) == ["dnaN"]
    assert len(alleles_by_locus["dnaN"]) == 1
    allele = alleles_by_locus["dnaN"][0]
    assert allele.allele_id == "n1"
    assert allele.samples == ["isoA", "isoB"]
