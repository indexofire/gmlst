"""Tests for GenBank/EMBL flat-file input support (gmlst.genbank_io)."""

from __future__ import annotations

import gzip
from pathlib import Path

from click.testing import CliRunner

from gmlst.fasta_io import iter_fasta_records
from gmlst.genbank_io import (
    ensure_fasta_samples,
    is_genbank_path,
    iter_records,
)

_GBK_TWO_CONTIGS = """\
LOCUS       contig0001       60 bp    DNA     linear   BCT
DEFINITION  Test sequence one.
FEATURES             Location/Qualifiers
ORIGIN
        1 acgtacgtac gtacgtacgt gtacgtacgt gtacgtacgt gtacgtacgt
       61 gtacgtacgt
//
LOCUS       contig0002       24 bp    DNA     linear   BCT
ORIGIN
        1 tttaggccta ggccaattga gc
//
"""

_EML_ONE = """\
ID   X12345; SV 1; linear; DNA; STD; 60 BP.
XX
AC   X12345;
XX
SQ   Sequence 60 BP; 15 A; 15 C; 15 G; 15 T;
     acgtacgtac gtacgtacgt gtacgtacgt gtacgtacgt gtacgtacgt
     gtacgtacgt
//
"""


_GBK_SEQ1 = ("acgtacgtac" + "gtacgtacgt" * 5).upper()
_GBK_SEQ2 = "TTTAGGCCTAGGCCAATTGAGC"


def _write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def _write_gzip(path: Path, text: str) -> Path:
    with gzip.open(path, "wt") as handle:
        handle.write(text)
    return path


# ---------------------------------------------------------------------------
# is_genbank_path
# ---------------------------------------------------------------------------


def test_is_genbank_path_recognizes_supported_extensions(tmp_path: Path) -> None:
    for name in ("a.gbk", "b.gb", "c.gbff", "d.embl", "e.gbk.gz", "f.embl.gz"):
        assert is_genbank_path(tmp_path / name), name
    for name in ("g.fna", "h.fasta", "i.fastq", "j.fq.gz", "k.txt"):
        assert not is_genbank_path(tmp_path / name), name


# ---------------------------------------------------------------------------
# GenBank parsing
# ---------------------------------------------------------------------------


def test_iter_records_genbank_multi_contig(tmp_path: Path) -> None:
    gbk = _write(tmp_path / "genome.gbff", _GBK_TWO_CONTIGS)

    records = list(iter_records(gbk))

    assert records == [
        ("contig0001", _GBK_SEQ1),
        ("contig0002", _GBK_SEQ2),
    ]


def test_iter_records_genbank_gzipped(tmp_path: Path) -> None:
    gbk = _write_gzip(tmp_path / "genome.gbk.gz", _GBK_TWO_CONTIGS)

    records = list(iter_records(gbk))

    assert [locus for locus, _ in records] == ["contig0001", "contig0002"]


def test_iter_records_genbank_missing_origin_raises(tmp_path: Path) -> None:
    gbk = _write(tmp_path / "bad.gbk", "LOCUS       x1       10 bp    DNA\n//\n")

    import pytest

    with pytest.raises(ValueError, match="bad.gbk"):
        list(iter_records(gbk))


def test_iter_records_genbank_unterminated_record_raises(tmp_path: Path) -> None:
    gbk = _write(tmp_path / "trunc.gbk", "LOCUS       x1\nORIGIN\nacgt\n")

    import pytest

    with pytest.raises(ValueError, match="trunc.gbk"):
        list(iter_records(gbk))


# ---------------------------------------------------------------------------
# EMBL parsing
# ---------------------------------------------------------------------------


def test_iter_records_embl(tmp_path: Path) -> None:
    embl = _write(tmp_path / "genome.embl", _EML_ONE)

    records = list(iter_records(embl))

    assert records == [("X12345", _GBK_SEQ1)]


# ---------------------------------------------------------------------------
# ensure_fasta_samples
# ---------------------------------------------------------------------------


def test_ensure_fasta_samples_passthrough(tmp_path: Path) -> None:
    fasta = _write(tmp_path / "sample.fna", ">c1\nacgt\n")

    with ensure_fasta_samples((fasta,)) as out:
        assert list(out) == [fasta]


def test_ensure_fasta_samples_converts_genbank(tmp_path: Path) -> None:
    fasta = _write(tmp_path / "keep.fna", ">c1\nacgt\n")
    gbk = _write(tmp_path / "sample.gbk", _GBK_TWO_CONTIGS)

    with ensure_fasta_samples((fasta, gbk)) as out:
        out_list = list(out)
        assert out_list[0] == fasta  # FASTA passes through untouched
        converted = out_list[1]
        assert converted != gbk
        assert converted.suffix == ".fna"
        assert list(iter_fasta_records(converted)) == [
            ("contig0001", _GBK_SEQ1),
            ("contig0002", _GBK_SEQ2),
        ]

    assert not converted.exists()  # temp FASTA cleaned up on context exit


# ---------------------------------------------------------------------------
# CLI integration: typing command converts GenBank before running
# ---------------------------------------------------------------------------


def test_typing_mlst_converts_genbank_before_typing(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, object] = {}

    def fake_run_mlst_like_typing(**kwargs):
        captured.update(kwargs)
        # Read inside the context: the converted temp FASTA only exists
        # for the duration of the typing command.
        captured["records"] = list(iter_fasta_records(list(kwargs["samples"])[0]))

    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing", fake_run_mlst_like_typing
    )

    gbk = _write(tmp_path / "sample.gbk", _GBK_TWO_CONTIGS)

    from gmlst.cli import main

    result = CliRunner().invoke(main, ["typing", "mlst", "-s", "x_1", str(gbk)])

    assert result.exit_code == 0, result.output
    samples = captured.get("samples")
    assert samples is not None
    assert list(samples)[0].suffix == ".fna"
    assert captured["records"] == [
        ("contig0001", _GBK_SEQ1),
        ("contig0002", _GBK_SEQ2),
    ]
