from __future__ import annotations

from pathlib import Path

from gmlst.readers.fasta import FastaReader
from gmlst.schemefree.assembly_engine import MegahitAssembler


def test_fallback_assembly_when_megahit_missing(monkeypatch, tmp_path: Path) -> None:
    fastq = tmp_path / "sample.fastq"
    fastq.write_text("@r1\nATCGATCG\n+\nFFFFFFFF\n@r2\nGGGGCCCC\n+\nFFFFFFFF\n")

    import gmlst.schemefree.assembly_engine as module

    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    assembler = MegahitAssembler(min_contig_len=4, enable_fallback=True)

    out = assembler.assemble(fastq, "s1", tmp_path / "out")
    assert out.exists()
    seqs = [record.sequence for record in FastaReader(out).records()]
    assert seqs


def test_megahit_path_uses_final_contigs(monkeypatch, tmp_path: Path) -> None:
    fastq = tmp_path / "sample.fastq"
    fastq.write_text("@r1\nATCGATCG\n+\nFFFFFFFF\n")

    import gmlst.schemefree.assembly_engine as module

    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/megahit")

    def fake_run(cmd, check, capture_output, text, timeout):
        out_dir = Path(cmd[cmd.index("-o") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "final.contigs.fa").write_text(">contig1\nATCGATCGATCG\n")
        return None

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assembler = MegahitAssembler(min_contig_len=4, enable_fallback=False)
    out = assembler.assemble(fastq, "s1", tmp_path / "out")
    assert out.name == "final.contigs.fa"
    assert out.exists()


def test_megahit_retries_then_succeeds(monkeypatch, tmp_path: Path) -> None:
    fastq = tmp_path / "sample.fastq"
    fastq.write_text("@r1\nATCGATCG\n+\nFFFFFFFF\n")

    import gmlst.schemefree.assembly_engine as module

    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/megahit")
    attempts = {"n": 0}

    def fake_run(cmd, check, capture_output, text, timeout):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise module.subprocess.CalledProcessError(1, cmd, "", "boom")
        out_dir = Path(cmd[cmd.index("-o") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "final.contigs.fa").write_text(">contig1\nATCGATCGATCG\n")
        return None

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assembler = MegahitAssembler(min_contig_len=4, retries=2, enable_fallback=False)
    out = assembler.assemble(fastq, "s1", tmp_path / "out")

    assert out.exists()
    assert attempts["n"] == 2


def test_megahit_timeout_falls_back(monkeypatch, tmp_path: Path) -> None:
    fastq = tmp_path / "sample.fastq"
    fastq.write_text("@r1\nATCGATCG\n+\nFFFFFFFF\n")

    import gmlst.schemefree.assembly_engine as module

    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/megahit")

    def fake_run(cmd, check, capture_output, text, timeout):
        raise module.subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assembler = MegahitAssembler(min_contig_len=4, retries=2, enable_fallback=True)
    out = assembler.assemble(fastq, "s1", tmp_path / "out")

    assert out.exists()
    assert out.name.endswith(".fallback.contigs.fasta")
