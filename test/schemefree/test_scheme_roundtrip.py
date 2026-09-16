"""Scheme save/load round-trip and locus anchoring tests."""

from __future__ import annotations

import json
from pathlib import Path

from gmlst.schemefree.gene_predictor import PredictedGene
from gmlst.schemefree.typing_engine import (
    SCHEME_ANCHOR_SAMPLE_ID,
    SchemeFreeTyper,
)

SHARED_SEQ = "ATCGATCG" * 6
S1_UNIQUE = "GGGGTTTTACGCAT"
S2_UNIQUE = "CCCCTTTTAGGCAT"
NOVEL_SEQ = "TTTTACGTGGGGCCTA"
SNP_SEQ = SHARED_SEQ[:23] + "C" + SHARED_SEQ[24:]

SCHEME_GENES = {
    "s1": [
        PredictedGene("s1", "g_shared", SHARED_SEQ),
        PredictedGene("s1", "g_unique", S1_UNIQUE),
    ],
    "s2": [
        PredictedGene("s2", "g_shared", SHARED_SEQ),
        PredictedGene("s2", "g_unique", S2_UNIQUE),
    ],
}


def _exact_sequence_cluster(genes):
    seq_to_locus: dict[str, str] = {}
    assignments: dict[str, str] = {}
    counter = 0
    for gene in genes:
        locus_id = seq_to_locus.get(gene.sequence)
        if locus_id is None:
            counter += 1
            locus_id = f"locus_{counter}"
            seq_to_locus[gene.sequence] = locus_id
        assignments[gene.key] = locus_id
    return assignments


def _prefix_cluster(genes):
    """Similarity fake: real genes join an anchor cluster on an 8-base prefix."""
    anchors = [g for g in genes if g.sample_id == SCHEME_ANCHOR_SAMPLE_ID]
    assignments = {a.key: f"raw_{a.gene_id}" for a in anchors}
    for gene in genes:
        if gene.sample_id == SCHEME_ANCHOR_SAMPLE_ID:
            continue
        for anchor in anchors:
            if gene.sequence[:8] == anchor.sequence[:8]:
                assignments[gene.key] = f"raw_{anchor.gene_id}"
                break
        else:
            assignments[gene.key] = f"raw_novel_{gene.key}"
    return assignments


def _make_typer(monkeypatch, cluster_fn, sample_genes) -> SchemeFreeTyper:
    typer = SchemeFreeTyper()

    def fake_predict(_path: Path, sample_id: str):
        return sample_genes[sample_id]

    monkeypatch.setattr(typer.gene_predictor, "predict", fake_predict)
    monkeypatch.setattr(typer.cluster_engine, "cluster_genes", cluster_fn)
    return typer


def _sample_paths(tmp_path: Path, sample_ids: list[str]) -> list[Path]:
    paths = []
    for sample_id in sample_ids:
        path = tmp_path / f"{sample_id}.fna"
        path.write_text(">c1\nATCG\n")
        paths.append(path)
    return paths


def _build_scheme(monkeypatch, tmp_path: Path) -> tuple[Path, list[dict]]:
    typer = _make_typer(monkeypatch, _exact_sequence_cluster, SCHEME_GENES)
    original = typer.type_sample_files(_sample_paths(tmp_path, ["s1", "s2"]))
    scheme_path = tmp_path / "scheme.json"
    typer.export_scheme(scheme_path)
    return scheme_path, [result.to_dict() for result in original]


def test_saved_scheme_round_trip_reproduces_profile(monkeypatch, tmp_path: Path):
    scheme_path, original_dicts = _build_scheme(monkeypatch, tmp_path)

    payload = json.loads(scheme_path.read_text())
    assert set(payload["representatives"]) == {"locus_1", "locus_2", "locus_3"}
    scheme_hashes = [
        seq_hash
        for alleles in payload["loci"].values()
        for seq_hash in alleles.values()
    ]
    assert scheme_hashes and all(seq_hash != "" for seq_hash in scheme_hashes)

    retyper = _make_typer(monkeypatch, _exact_sequence_cluster, SCHEME_GENES)
    retyper.load_scheme(scheme_path)
    retyped = retyper.type_sample_files(_sample_paths(tmp_path, ["s1"]))

    assert len(retyped) == 1
    assert retyped[0].to_dict() == original_dicts[0]


def test_novel_gene_gets_locus_after_scheme_max(monkeypatch, tmp_path: Path):
    scheme_path, _ = _build_scheme(monkeypatch, tmp_path)

    novel_genes = {
        "s3": [
            PredictedGene("s3", "g_shared", SHARED_SEQ),
            PredictedGene("s3", "g_novel", NOVEL_SEQ),
        ]
    }
    typer = _make_typer(monkeypatch, _exact_sequence_cluster, novel_genes)
    typer.load_scheme(scheme_path)
    results = typer.type_sample_files(_sample_paths(tmp_path, ["s3"]))

    profile = results[0].profile
    assert set(profile) == {"locus_1", "locus_4"}
    assert profile["locus_1"] == "locus_1_1"
    assert profile["locus_4"] == "locus_4_1"
    assert typer.last_run_stats["scheme_loci_anchored"] == 1
    assert typer.last_run_stats["novel_loci"] == 1


def test_novel_allele_at_anchored_locus_continues_numbering(
    monkeypatch, tmp_path: Path
):
    scheme_path, _ = _build_scheme(monkeypatch, tmp_path)

    snp_genes = {"s3": [PredictedGene("s3", "g_snp", SNP_SEQ)]}
    typer = _make_typer(monkeypatch, _prefix_cluster, snp_genes)
    typer.load_scheme(scheme_path)
    results = typer.type_sample_files(_sample_paths(tmp_path, ["s3"]))

    profile = results[0].profile
    assert set(profile) == {"locus_1"}
    assert profile["locus_1"] == "locus_1_2"
    assert typer.last_run_stats["scheme_loci_anchored"] == 1
    assert typer.last_run_stats["novel_loci"] == 0


def test_legacy_scheme_loads_with_warning_and_continues_numbering(
    monkeypatch, tmp_path: Path, capsys
):
    scheme_path = tmp_path / "legacy_scheme.json"
    scheme_path.write_text(
        json.dumps(
            {
                "config": {},
                "loci": {"locus_1": ["locus_1_1", "locus_1_2"]},
                "profiles": {},
            }
        )
    )

    typer = SchemeFreeTyper()
    typer.load_scheme(scheme_path)

    captured = capsys.readouterr()
    assert "representative" in captured.err
    assert typer.locus_representatives == {}

    assert typer.type_sequence("ATCGGGTTACGCAT", "locus_1", "s1") == "locus_1_3"


def test_load_mode_runs_are_deterministic(monkeypatch, tmp_path: Path):
    scheme_path, _ = _build_scheme(monkeypatch, tmp_path)

    outputs = []
    for _ in range(2):
        typer = _make_typer(
            monkeypatch,
            _prefix_cluster,
            {
                "s3": [
                    PredictedGene("s3", "g_snp", SNP_SEQ),
                    PredictedGene("s3", "g_novel", NOVEL_SEQ),
                ]
            },
        )
        typer.load_scheme(scheme_path)
        results = typer.type_sample_files(_sample_paths(tmp_path, ["s3"]))
        outputs.append(json.dumps([result.to_dict() for result in results]))

    assert outputs[0] == outputs[1]


def test_exact_allele_locus_wins_over_misclustering(monkeypatch, tmp_path: Path):
    """A byte-identical scheme hit keeps its own locus even when the
    clusterer assigns the gene to a paralogous anchor's cluster."""
    scheme_path, original_dicts = _build_scheme(monkeypatch, tmp_path)

    def misclustering_fake(genes):
        # Deliberately wrong: every real gene joins the locus_3 anchor's
        # cluster (locus_3 = s2's unique gene, biologically unrelated).
        assignments = {}
        for gene in genes:
            if gene.sample_id == SCHEME_ANCHOR_SAMPLE_ID:
                assignments[gene.key] = "raw_anchor"
            else:
                assignments[gene.key] = "raw_anchor"
        return assignments

    retyper = _make_typer(monkeypatch, misclustering_fake, SCHEME_GENES)
    retyper.load_scheme(scheme_path)
    retyped = retyper.type_sample_files(_sample_paths(tmp_path, ["s1"]))

    assert len(retyped) == 1
    assert retyped[0].to_dict() == original_dicts[0]
