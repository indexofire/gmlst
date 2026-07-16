from __future__ import annotations

from pathlib import Path

from gmlst.core.gene_predictor import PredictedGene, ProdigalPredictor


def test_fallback_prediction_when_prodigal_missing(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">contig1\nATCG" * 80 + "\n")

    import gmlst.core.gene_predictor as module

    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    predictor = ProdigalPredictor(min_gene_len=100, max_gene_len=5000)

    genes = predictor.predict(sample, "sample")
    assert genes
    assert all(g.sample_id == "sample" for g in genes)


def test_runs_prodigal_and_parses_output(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">contig1\nATCGATCGATCG\n")

    import gmlst.core.gene_predictor as module

    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/prodigal")

    def fake_run(cmd, check, capture_output, text, timeout):
        genes_out = Path(cmd[cmd.index("-d") + 1])
        genes_out.write_text(">gene1\nATCGATCGATCGATCG\n")
        return None

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    predictor = ProdigalPredictor(
        tool="prodigal",
        min_gene_len=10,
        max_gene_len=5000,
    )
    genes = predictor.predict(sample, "s1")

    assert genes == [
        PredictedGene(
            sample_id="s1",
            gene_id="gene_1",
            sequence="ATCGATCGATCGATCG",
            contig_id="gene1",
        )
    ]
