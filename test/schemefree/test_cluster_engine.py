from __future__ import annotations

from pathlib import Path

from gmlst.schemefree.cluster_engine import MMseqsClusterEngine
from gmlst.schemefree.gene_predictor import PredictedGene


def test_fallback_clustering_groups_identical_sequences(monkeypatch) -> None:
    import gmlst.schemefree.cluster_engine as module

    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    engine = MMseqsClusterEngine(enable_fallback=True)

    genes = [
        PredictedGene("s1", "g1", "ATCG"),
        PredictedGene("s2", "g1", "ATCG"),
        PredictedGene("s2", "g2", "GGGG"),
    ]
    assignments = engine.cluster_genes(genes)

    assert assignments["s1|g1"] == assignments["s2|g1"]
    assert assignments["s1|g1"] != assignments["s2|g2"]


def test_parse_cluster_tsv_numbering_is_line_order_independent(
    tmp_path: Path,
) -> None:
    engine = MMseqsClusterEngine(enable_fallback=False)

    tsv_original = tmp_path / "original_cluster.tsv"
    tsv_original.write_text("s1|g1\ts1|g1\ns1|g1\ts2|g1\ns2|g2\ts2|g2\n")
    tsv_shuffled = tmp_path / "shuffled_cluster.tsv"
    tsv_shuffled.write_text("s2|g2\ts2|g2\ns1|g1\ts2|g1\ns1|g1\ts1|g1\n")

    assignments_original = engine._parse_cluster_tsv(tsv_original)
    assignments_shuffled = engine._parse_cluster_tsv(tsv_shuffled)

    assert assignments_original == assignments_shuffled
    assert assignments_original["s1|g1"] == "locus_1"
    assert assignments_original["s2|g1"] == "locus_1"
    assert assignments_original["s2|g2"] == "locus_2"


def test_parse_cluster_tsv_numbers_by_smallest_member_key(tmp_path: Path) -> None:
    engine = MMseqsClusterEngine(enable_fallback=False)

    tsv = tmp_path / "clusters.tsv"
    tsv.write_text(
        "s3|g1\ts3|g1\ns3|g1\ts3|g2\ns1|g1\ts1|g1\ns1|g1\ts2|g1\ns2|g9\ts2|g9\n"
    )

    assignments = engine._parse_cluster_tsv(tsv)

    assert assignments["s1|g1"] == "locus_1"
    assert assignments["s2|g1"] == "locus_1"
    assert assignments["s2|g9"] == "locus_2"
    assert assignments["s3|g1"] == "locus_3"
    assert assignments["s3|g2"] == "locus_3"


def test_mmseqs_path_parses_cluster_tsv(monkeypatch, tmp_path: Path) -> None:
    import gmlst.schemefree.cluster_engine as module

    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/mmseqs")

    def fake_run(cmd, check, capture_output, text, timeout):
        prefix = Path(cmd[3])
        cluster_tsv = prefix.with_name(f"{prefix.name}_cluster.tsv")
        cluster_tsv.write_text("s1|g1\ts1|g1\ns1|g1\ts2|g1\ns2|g2\ts2|g2\n")
        return None

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    engine = MMseqsClusterEngine(enable_fallback=False)
    genes = [
        PredictedGene("s1", "g1", "ATCG"),
        PredictedGene("s2", "g1", "ATCG"),
        PredictedGene("s2", "g2", "GGGG"),
    ]
    assignments = engine.cluster_genes(genes)

    assert assignments["s1|g1"] == assignments["s2|g1"]
    assert assignments["s1|g1"] != assignments["s2|g2"]
