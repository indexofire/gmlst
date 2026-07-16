"""Scheme-free typing engine.

This module provides the main typing engine for scheme-free MLST analysis,
tying together gene prediction, clustering, and hashing to generate profiles.
"""

from __future__ import annotations

import concurrent.futures
import time
from pathlib import Path
from typing import Any

from gmlst.core.gene_predictor import PredictedGene, ProdigalPredictor
from gmlst.readers.sample import SampleInput
from gmlst.schemefree.assembly_engine import MegahitAssembler
from gmlst.schemefree.cluster_engine import MMseqsClusterEngine
from gmlst.schemefree.config import SchemaFreeConfig
from gmlst.schemefree.hasher import HashStrategy, HashStrategyManager
from gmlst.schemefree.io_handler import read_scheme_json, write_scheme_json
from gmlst.utils import temp_dir


class SampleProcessingError(RuntimeError):
    def __init__(self, sample_id: str, stage: str, message: str) -> None:
        super().__init__(message)
        self.sample_id = sample_id
        self.stage = stage


def _run_status(samples_succeeded: int, samples_failed: int) -> str:
    if samples_failed == 0:
        return "success"
    if samples_succeeded == 0:
        return "failed"
    return "partial_failed"


class SchemeFreeTyper:
    """Main typing engine for scheme-free MLST analysis.

    This class coordinates the typing process:
    1. Gene prediction (Prodigal)
    2. Gene clustering (MMseqs2)
    3. Allele assignment (Hash strategies)
    4. Profile generation

    Example:
        >>> typer = SchemeFreeTyper()
        >>> result = typer.type_sample("ATCG...", "sample_1")
        >>> print(result.profile)
    """

    def __init__(self, config: SchemaFreeConfig | None = None):
        """Initialize the typing engine.

        Args:
            config: Configuration object. Uses default if None.
        """
        self.config = config or SchemaFreeConfig()
        self.hash_strategy: HashStrategy = HashStrategyManager.get_strategy(
            self.config.hash.strategy,
            self.config.get_hash_config(),
        )
        self.gene_predictor = ProdigalPredictor(
            tool=self.config.gene_prediction.tool,
            mode=self.config.gene_prediction.mode,
            training_file=self.config.gene_prediction.training_file,
            closed_ends=self.config.gene_prediction.closed_ends,
            min_gene_len=self.config.gene_prediction.min_gene_len,
            max_gene_len=self.config.gene_prediction.max_gene_len,
            timeout_sec=self.config.gene_prediction.timeout_sec,
        )
        self.assembly_engine = MegahitAssembler(
            min_contig_len=self.config.assembly.min_contig_len,
            preset=self.config.assembly.preset,
            retries=self.config.assembly.retries,
            timeout_sec=self.config.assembly.assemble_timeout_sec,
        )
        self.cluster_engine = MMseqsClusterEngine(
            min_seq_id=self.config.clustering.min_seq_id,
            coverage=self.config.clustering.coverage,
            cov_mode=self.config.clustering.cov_mode,
            cluster_mode=self.config.clustering.cluster_mode,
            threads=self.config.clustering.threads,
            timeout_sec=self.config.clustering.timeout_sec,
        )
        # Map of locus_id -> {allele_id -> sequence_hash}
        self.locus_alleles: dict[str, dict[str, str]] = {}
        # Map of sample_id -> profile
        self.profiles: dict[str, dict[str, Any]] = {}
        self.last_run_stats: dict[str, Any] = {}
        self.last_run_errors: list[dict[str, str]] = []

    def type_sample_files(self, sample_paths: list[Path]) -> list[SampleProfile]:
        run_start = time.perf_counter()
        all_genes: list[PredictedGene] = []
        sample_inputs: list[SampleInput] = []
        self.last_run_errors = []
        for path in sample_paths:
            try:
                sample_inputs.append(SampleInput.from_path(path))
            except Exception as exc:
                self.last_run_errors.append(
                    {
                        "sample_id": path.name,
                        "stage": "input",
                        "severity": "error",
                        "error": str(exc),
                    }
                )

        sample_ids = [sample.sample_id for sample in sample_inputs]
        successful_sample_ids: list[str] = []
        assembly_count = 0
        prediction_seconds = 0.0
        assembly_seconds = 0.0
        max_workers = min(
            max(1, self.config.assembly.max_parallel_samples),
            max(1, len(sample_inputs)),
        )
        with temp_dir("gmlst_schemefree_") as tmp:
            temp_path = Path(tmp)
            if max_workers == 1:
                for sample in sample_inputs:
                    try:
                        _, predicted, used_fastq, assembly_dur, prediction_dur = (
                            self._prepare_sample_genes(sample, temp_path)
                        )
                    except SampleProcessingError as exc:
                        self.last_run_errors.append(
                            {
                                "sample_id": exc.sample_id,
                                "stage": exc.stage,
                                "severity": "error",
                                "error": str(exc),
                            }
                        )
                        continue

                    successful_sample_ids.append(sample.sample_id)
                    if used_fastq:
                        assembly_count += 1
                    assembly_seconds += assembly_dur
                    prediction_seconds += prediction_dur
                    all_genes.extend(predicted)
            else:
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers
                ) as executor:
                    futures = [
                        executor.submit(self._prepare_sample_genes, sample, temp_path)
                        for sample in sample_inputs
                    ]
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            (
                                sample_id,
                                predicted,
                                used_fastq,
                                assembly_dur,
                                prediction_dur,
                            ) = future.result()
                        except SampleProcessingError as exc:
                            self.last_run_errors.append(
                                {
                                    "sample_id": exc.sample_id,
                                    "stage": exc.stage,
                                    "severity": "error",
                                    "error": str(exc),
                                }
                            )
                            continue

                        successful_sample_ids.append(sample_id)
                        if used_fastq:
                            assembly_count += 1
                        assembly_seconds += assembly_dur
                        prediction_seconds += prediction_dur
                        all_genes.extend(predicted)

        cluster_start = time.perf_counter()
        assignments = self.cluster_engine.cluster_genes(all_genes)
        cluster_seconds = time.perf_counter() - cluster_start

        sample_loci: dict[str, dict[str, str]] = {
            sample_id: {} for sample_id in sample_ids
        }
        for gene in all_genes:
            locus_id = assignments.get(gene.key)
            if locus_id is None:
                continue
            existing = sample_loci[gene.sample_id].get(locus_id)
            if existing is None or len(gene.sequence) > len(existing):
                sample_loci[gene.sample_id][locus_id] = gene.sequence

        results: list[SampleProfile] = []
        for sample_id in successful_sample_ids:
            profile = self.type_sample(sample_loci[sample_id], sample_id)
            results.append(profile)

        self.last_run_stats = {
            "samples_total": len(sample_paths),
            "samples_succeeded": len(successful_sample_ids),
            "samples_failed": len(self.last_run_errors),
            "samples_fastq": assembly_count,
            "samples_fasta": len(successful_sample_ids) - assembly_count,
            "genes_predicted": len(all_genes),
            "loci_discovered": len({v for v in assignments.values()}),
            "seconds_assembly": round(assembly_seconds, 6),
            "seconds_prediction": round(prediction_seconds, 6),
            "seconds_clustering": round(cluster_seconds, 6),
            "seconds_total": round(time.perf_counter() - run_start, 6),
            "max_workers_used": max_workers,
            "run_status": _run_status(
                len(successful_sample_ids),
                len(self.last_run_errors),
            ),
        }
        return results

    def _prepare_sample_genes(
        self,
        sample: SampleInput,
        temp_path: Path,
    ) -> tuple[str, list[PredictedGene], bool, float, float]:
        input_path = sample.path
        used_fastq = sample.input_type == "fastq"
        assembly_dur = 0.0

        if used_fastq:
            try:
                assembly_start = time.perf_counter()
                input_path = self.assembly_engine.assemble(
                    sample.path,
                    sample.sample_id,
                    temp_path,
                )
                assembly_dur = time.perf_counter() - assembly_start
            except Exception as exc:
                raise SampleProcessingError(
                    sample.sample_id,
                    "assembly",
                    str(exc),
                ) from exc

        try:
            prediction_start = time.perf_counter()
            predicted = self.gene_predictor.predict(input_path, sample.sample_id)
            prediction_dur = time.perf_counter() - prediction_start
        except Exception as exc:
            raise SampleProcessingError(
                sample.sample_id,
                "prediction",
                str(exc),
            ) from exc
        return sample.sample_id, predicted, used_fastq, assembly_dur, prediction_dur

    def type_sequence(self, sequence: str, locus_id: str, sample_id: str) -> str:
        """Type a single sequence and return allele ID.

        Args:
            sequence: DNA sequence
            locus_id: Locus identifier
            sample_id: Sample identifier

        Returns:
            Allele ID (e.g., "locus_1_42")
        """
        allele_id = self.hash_strategy.get_allele_id(sequence, locus_id)

        # Track locus -> allele mapping
        if locus_id not in self.locus_alleles:
            self.locus_alleles[locus_id] = {}

        # Store the allele assignment
        seq_hash = self._compute_hash(sequence)
        self.locus_alleles[locus_id][allele_id] = seq_hash

        return allele_id

    def type_sample(
        self,
        genes: dict[str, str],
        sample_id: str,
    ) -> SampleProfile:
        """Type a sample with multiple genes.

        Args:
            genes: Dictionary mapping locus_id -> sequence
            sample_id: Sample identifier

        Returns:
            SampleProfile object with typing results
        """
        profile: dict[str, str] = {}

        for locus_id, sequence in genes.items():
            allele_id = self.type_sequence(sequence, locus_id, sample_id)
            profile[locus_id] = allele_id

        # Store profile
        self.profiles[sample_id] = {
            "sample_id": sample_id,
            "profile": profile,
            "loci_count": len(profile),
        }

        return SampleProfile(
            sample_id=sample_id,
            profile=profile,
            loci_count=len(profile),
        )

    def type_multiple_samples(
        self,
        samples: dict[str, dict[str, str]],
    ) -> list[SampleProfile]:
        """Type multiple samples.

        Args:
            samples: Dictionary mapping sample_id -> {locus_id -> sequence}

        Returns:
            List of SampleProfile objects
        """
        results = []
        for sample_id, genes in samples.items():
            result = self.type_sample(genes, sample_id)
            results.append(result)
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get typing statistics.

        Returns:
            Dictionary with statistics
        """
        hash_stats = self.hash_strategy.get_stats()
        return {
            "samples_typed": len(self.profiles),
            "loci_discovered": len(self.locus_alleles),
            "total_alleles": sum(
                len(alleles) for alleles in self.locus_alleles.values()
            ),
            **hash_stats,
        }

    def export_scheme(self, output_path: Path | str) -> None:
        """Export the discovered scheme to a JSON file.

        Args:
            output_path: Path to save the scheme
        """
        path = Path(output_path)
        loci = {
            locus_id: list(alleles.keys())
            for locus_id, alleles in self.locus_alleles.items()
        }
        write_scheme_json(path, self._config_to_dict(), loci, self.profiles)

    def load_scheme(self, input_path: Path | str) -> None:
        """Load a previously discovered scheme.

        Args:
            input_path: Path to the scheme JSON file
        """
        path = Path(input_path)
        scheme = read_scheme_json(path)

        # Restore loci and alleles
        self.locus_alleles = {
            locus_id: {allele_id: "" for allele_id in allele_ids}
            for locus_id, allele_ids in scheme.get("loci", {}).items()
        }

        # Restore profiles
        self.profiles = scheme.get("profiles", {})

    def _compute_hash(self, sequence: str) -> str:
        """Compute hash for a sequence (for tracking)."""
        import hashlib

        clean_seq = sequence.upper().replace("-", "").replace(" ", "")
        return hashlib.md5(clean_seq.encode()).hexdigest()

    def _config_to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "hash_strategy": self.config.hash.strategy,
            "clustering": {
                "min_seq_id": self.config.clustering.min_seq_id,
                "coverage": self.config.clustering.coverage,
                "timeout_sec": self.config.clustering.timeout_sec,
            },
            "gene_prediction": {
                "mode": self.config.gene_prediction.mode,
                "min_gene_len": self.config.gene_prediction.min_gene_len,
                "max_gene_len": self.config.gene_prediction.max_gene_len,
                "timeout_sec": self.config.gene_prediction.timeout_sec,
            },
        }


class SampleProfile:
    """Represents a typed sample profile.

    Attributes:
        sample_id: Sample identifier
        profile: Dictionary mapping locus_id -> allele_id
        loci_count: Number of loci typed
    """

    def __init__(self, sample_id: str, profile: dict[str, str], loci_count: int):
        self.sample_id = sample_id
        self.profile = profile
        self.loci_count = loci_count

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sample_id": self.sample_id,
            "profile": self.profile,
            "loci_count": self.loci_count,
        }

    def __repr__(self) -> str:
        return f"SampleProfile({self.sample_id}: {self.loci_count} loci)"
