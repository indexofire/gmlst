"""Tests for schemefree typing engine."""

import json
import tempfile
from pathlib import Path

from gmlst.schemefree.config import SchemaFreeConfig
from gmlst.schemefree.gene_predictor import PredictedGene
from gmlst.schemefree.typing_engine import SampleProfile, SchemeFreeTyper


class TestSchemeFreeTyper:
    """Test the main typing engine."""

    def test_basic_initialization(self):
        """Test basic initialization with default config."""
        typer = SchemeFreeTyper()
        assert typer.config is not None
        assert typer.hash_strategy is not None
        assert typer.locus_alleles == {}
        assert typer.profiles == {}

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = SchemaFreeConfig()
        config.hash.strategy = "strict"
        typer = SchemeFreeTyper(config)
        assert typer.config.hash.strategy == "strict"

    def test_type_single_sequence(self):
        """Test typing a single sequence."""
        typer = SchemeFreeTyper()
        allele_id = typer.type_sequence("ATCGATCGATCG", "locus_1", "sample_1")
        assert allele_id == "locus_1_1"

        # Same sequence should get same ID
        allele_id2 = typer.type_sequence("ATCGATCGATCG", "locus_1", "sample_1")
        assert allele_id2 == "locus_1_1"

    def test_type_sample(self):
        """Test typing a sample with multiple genes."""
        typer = SchemeFreeTyper()
        genes = {
            "locus_1": "ATCGATCGATCG",
            "locus_2": "GGCCGGCCGGCC",
        }

        result = typer.type_sample(genes, "sample_1")
        assert result.sample_id == "sample_1"
        assert result.loci_count == 2
        assert "locus_1" in result.profile
        assert "locus_2" in result.profile
        assert result.profile["locus_1"] == "locus_1_1"
        assert result.profile["locus_2"] == "locus_2_1"

    def test_type_multiple_samples(self):
        """Test typing multiple samples."""
        typer = SchemeFreeTyper()
        samples = {
            "sample_1": {
                "locus_1": "ATCGATCGATCG",
                "locus_2": "GGCCGGCCGGCC",
            },
            "sample_2": {
                "locus_1": "ATCGATCGATCG",  # Same as sample_1
                "locus_2": "AAAATTTTCCCC",  # Different
            },
        }

        results = typer.type_multiple_samples(samples)
        assert len(results) == 2

        # Sample 1 and 2 should share locus_1 allele
        assert results[0].profile["locus_1"] == results[1].profile["locus_1"]
        # But have different locus_2 alleles
        assert results[0].profile["locus_2"] != results[1].profile["locus_2"]

    def test_get_stats(self):
        """Test statistics collection."""
        typer = SchemeFreeTyper()
        genes = {
            "locus_1": "ATCGATCGATCG",
            "locus_2": "GGCCGGCCGGCC",
        }
        typer.type_sample(genes, "sample_1")

        stats = typer.get_stats()
        assert stats["samples_typed"] == 1
        assert stats["loci_discovered"] == 2
        assert stats["total_alleles"] == 2
        assert "total_sequences" in stats
        assert "unique_alleles" in stats

    def test_export_and_load_scheme(self):
        """Test scheme export and loading."""
        typer = SchemeFreeTyper()
        genes = {
            "locus_1": "ATCGATCGATCG",
            "locus_2": "GGCCGGCCGGCC",
        }
        typer.type_sample(genes, "sample_1")

        with tempfile.TemporaryDirectory() as tmpdir:
            scheme_path = Path(tmpdir) / "scheme.json"

            # Export
            typer.export_scheme(scheme_path)
            assert scheme_path.exists()

            # Verify JSON structure
            with open(scheme_path) as f:
                scheme = json.load(f)
            assert "config" in scheme
            assert "loci" in scheme
            assert "profiles" in scheme
            assert "locus_1" in scheme["loci"]
            assert "locus_2" in scheme["loci"]

            # Load into new typer
            new_typer = SchemeFreeTyper()
            new_typer.load_scheme(scheme_path)
            assert len(new_typer.locus_alleles) == 2
            assert len(new_typer.profiles) == 1


class TestSampleProfile:
    """Test SampleProfile class."""

    def test_creation(self):
        """Test basic creation."""
        profile = SampleProfile(
            sample_id="sample_1",
            profile={"locus_1": "locus_1_1", "locus_2": "locus_2_1"},
            loci_count=2,
        )
        assert profile.sample_id == "sample_1"
        assert profile.loci_count == 2
        assert profile.profile["locus_1"] == "locus_1_1"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        profile = SampleProfile(
            sample_id="sample_1",
            profile={"locus_1": "locus_1_1"},
            loci_count=1,
        )
        d = profile.to_dict()
        assert d["sample_id"] == "sample_1"
        assert d["loci_count"] == 1
        assert d["profile"]["locus_1"] == "locus_1_1"

    def test_repr(self):
        """Test string representation."""
        profile = SampleProfile(
            sample_id="sample_1",
            profile={"locus_1": "locus_1_1"},
            loci_count=1,
        )
        assert "sample_1" in repr(profile)
        assert "1 loci" in repr(profile)


class TestDifferentHashStrategies:
    """Test typing engine with different hash strategies."""

    def test_with_safe_strategy(self):
        """Test with safe (MD5) strategy."""
        config = SchemaFreeConfig()
        config.hash.strategy = "safe"
        typer = SchemeFreeTyper(config)

        genes = {"locus_1": "ATCGATCGATCG"}
        result = typer.type_sample(genes, "sample_1")
        assert result.profile["locus_1"] == "locus_1_1"


class TestSchemeFreeFilePipeline:
    def test_type_sample_files(self, monkeypatch, tmp_path: Path):
        typer = SchemeFreeTyper()

        sample1 = tmp_path / "s1.fna"
        sample2 = tmp_path / "s2.fna"
        sample1.write_text(">c1\nATCG\n")
        sample2.write_text(">c1\nATCG\n")

        predicted = {
            "s1": [
                PredictedGene("s1", "g1", "ATCGATCG"),
                PredictedGene("s1", "g2", "GGGGCCCC"),
            ],
            "s2": [
                PredictedGene("s2", "g1", "ATCGATCG"),
                PredictedGene("s2", "g2", "TTTTAAAA"),
            ],
        }

        def fake_predict(path: Path, sample_id: str):
            return predicted[sample_id]

        def fake_cluster(genes):
            return {
                "s1|g1": "locus_1",
                "s2|g1": "locus_1",
                "s1|g2": "locus_2",
                "s2|g2": "locus_3",
            }

        monkeypatch.setattr(typer.gene_predictor, "predict", fake_predict)
        monkeypatch.setattr(typer.cluster_engine, "cluster_genes", fake_cluster)

        results = typer.type_sample_files([sample1, sample2])
        assert len(results) == 2

        by_sample = {result.sample_id: result for result in results}
        assert by_sample["s1"].profile["locus_1"] == by_sample["s2"].profile["locus_1"]
        assert by_sample["s1"].profile["locus_2"].startswith("locus_2_")
        assert by_sample["s2"].profile["locus_3"].startswith("locus_3_")

    def test_type_fastq_sample_files_uses_assembly(self, monkeypatch, tmp_path: Path):
        typer = SchemeFreeTyper()

        fastq = tmp_path / "s1.fastq"
        fastq.write_text("@r1\nATCGATCG\n+\nFFFFFFFF\n")

        assembled = tmp_path / "assembled.fasta"
        assembled.write_text(">contig1\nATCGATCG\n")

        calls: dict[str, Path] = {}

        def fake_assemble(sample_path: Path, sample_id: str, output_dir: Path):
            calls["input"] = sample_path
            calls["output_dir"] = output_dir
            return assembled

        def fake_predict(path: Path, sample_id: str):
            assert path == assembled
            assert sample_id == "s1"
            return [PredictedGene("s1", "g1", "ATCGATCG")]

        def fake_cluster(genes):
            return {"s1|g1": "locus_1"}

        monkeypatch.setattr(typer.assembly_engine, "assemble", fake_assemble)
        monkeypatch.setattr(typer.gene_predictor, "predict", fake_predict)
        monkeypatch.setattr(typer.cluster_engine, "cluster_genes", fake_cluster)

        results = typer.type_sample_files([fastq])
        assert len(results) == 1
        assert results[0].sample_id == "s1"
        assert results[0].profile["locus_1"].startswith("locus_1_")
        assert calls["input"] == fastq
        assert typer.last_run_stats["samples_fastq"] == 1
        assert typer.last_run_stats["samples_fasta"] == 0

    def test_with_strict_strategy(self):
        """Test with strict (SHA256) strategy."""
        config = SchemaFreeConfig()
        config.hash.strategy = "strict"
        typer = SchemeFreeTyper(config)

        genes = {"locus_1": "ATCGATCGATCG"}
        result = typer.type_sample(genes, "sample_1")
        assert result.profile["locus_1"] == "locus_1_1"

    def test_type_sample_files_collects_run_stats(self, monkeypatch, tmp_path: Path):
        typer = SchemeFreeTyper()
        sample = tmp_path / "s1.fna"
        sample.write_text(">c1\nATCG\n")

        monkeypatch.setattr(
            typer.gene_predictor,
            "predict",
            lambda _path, _sid: [PredictedGene("s1", "g1", "ATCGATCG")],
        )
        monkeypatch.setattr(
            typer.cluster_engine, "cluster_genes", lambda _genes: {"s1|g1": "locus_1"}
        )

        results = typer.type_sample_files([sample])

        assert len(results) == 1
        stats = typer.last_run_stats
        assert stats["samples_total"] == 1
        assert stats["samples_fasta"] == 1
        assert stats["samples_fastq"] == 0
        assert stats["genes_predicted"] == 1
        assert stats["loci_discovered"] == 1
        assert stats["max_workers_used"] == 1
        assert "seconds_total" in stats

    def test_type_sample_files_reports_parallel_worker_count(
        self, monkeypatch, tmp_path: Path
    ):
        config = SchemaFreeConfig()
        config.assembly.max_parallel_samples = 4
        typer = SchemeFreeTyper(config)

        s1 = tmp_path / "s1.fna"
        s2 = tmp_path / "s2.fna"
        s1.write_text(">c1\nATCG\n")
        s2.write_text(">c1\nATCG\n")

        monkeypatch.setattr(
            typer.gene_predictor,
            "predict",
            lambda path, sid: [PredictedGene(sid, "g1", "ATCGATCG")],
        )
        monkeypatch.setattr(
            typer.cluster_engine,
            "cluster_genes",
            lambda genes: {gene.key: "locus_1" for gene in genes},
        )

        results = typer.type_sample_files([s1, s2])
        assert len(results) == 2
        assert typer.last_run_stats["max_workers_used"] == 2

    def test_type_sample_files_isolates_failed_samples(
        self, monkeypatch, tmp_path: Path
    ):
        typer = SchemeFreeTyper()

        s1 = tmp_path / "s1.fna"
        s2 = tmp_path / "s2.fna"
        s1.write_text(">c1\nATCG\n")
        s2.write_text(">c1\nATCG\n")

        def fake_predict(_path: Path, sample_id: str):
            if sample_id == "s2":
                raise RuntimeError("prediction failed")
            return [PredictedGene("s1", "g1", "ATCGATCG")]

        monkeypatch.setattr(typer.gene_predictor, "predict", fake_predict)
        monkeypatch.setattr(
            typer.cluster_engine,
            "cluster_genes",
            lambda genes: {gene.key: "locus_1" for gene in genes},
        )

        results = typer.type_sample_files([s1, s2])

        assert len(results) == 1
        assert results[0].sample_id == "s1"
        assert typer.last_run_stats["samples_total"] == 2
        assert typer.last_run_stats["samples_succeeded"] == 1
        assert typer.last_run_stats["samples_failed"] == 1
        assert typer.last_run_stats["run_status"] == "partial_failed"
        assert typer.last_run_errors[0]["sample_id"] == "s2"
        assert typer.last_run_errors[0]["stage"] == "prediction"
        assert typer.last_run_errors[0]["severity"] == "error"
