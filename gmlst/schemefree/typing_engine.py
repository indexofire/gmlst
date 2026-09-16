"""Scheme-free typing engine.

This module provides the main typing engine for scheme-free MLST analysis,
tying together gene prediction, clustering, and hashing to generate profiles.
"""

from __future__ import annotations

import concurrent.futures
import sys
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
    """Pipeline failure for one sample, tagged with its failing stage."""

    def __init__(self, sample_id: str, stage: str, message: str) -> None:
        super().__init__(message)
        self.sample_id = sample_id
        self.stage = stage


SampleGenesOutcome = tuple[str, list[PredictedGene], bool, float, float]

# Sentinel sample_id for scheme anchor pseudo-genes; anchors are excluded
# from profiles and stats, so this ID never reaches output.
SCHEME_ANCHOR_SAMPLE_ID = "__scheme_anchor__"


def _trailing_int(identifier: str) -> int:
    """Trailing integer of a ``..._N`` ID; 0 when non-numeric."""
    try:
        return int(identifier.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return 0


def _locus_sort_key(locus_id: str) -> tuple[int, str]:
    """Deterministic locus order: number first, ID as tiebreak."""
    return (_trailing_int(locus_id), locus_id)


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
        # Representative sequence per locus (first allele seen)
        self.locus_representatives: dict[str, str] = {}
        # md5 -> allele_id for exact scheme allele reuse (load mode)
        self._scheme_hash_to_allele: dict[str, str] = {}
        # Highest scheme locus number; novel loci continue after it
        self._scheme_max_locus_number: int = 0
        # Map of sample_id -> profile
        self.profiles: dict[str, dict[str, Any]] = {}
        self.last_run_stats: dict[str, Any] = {}
        self.last_run_errors: list[dict[str, str]] = []

    def type_sample_files(self, sample_paths: list[Path]) -> list[SampleProfile]:
        """Run the full tgMLST pipeline over FASTA/FASTQ sample files.

        Stages: input parsing, optional FASTQ assembly (megahit), gene
        prediction (Prodigal), locus clustering (mmseqs2, longest gene per
        sample wins a locus), and allele hashing into profiles. Per-sample
        failures are captured in ``last_run_errors`` (with stage tags)
        instead of aborting the run; ``last_run_stats`` carries stage
        timings and counts.
        """
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
                    future_to_index = {
                        executor.submit(
                            self._prepare_sample_genes, sample, temp_path
                        ): index
                        for index, sample in enumerate(sample_inputs)
                    }
                    # Store outcomes keyed by sample position (not completion
                    # order): determinism requires replaying them in input
                    # order below.
                    outcomes: dict[int, SampleGenesOutcome | SampleProcessingError] = {}
                    for future in concurrent.futures.as_completed(future_to_index):
                        index = future_to_index[future]
                        try:
                            outcomes[index] = future.result()
                        except SampleProcessingError as exc:
                            outcomes[index] = exc

                # Input-order replay keeps gene order, sample order, and
                # allele numbering identical to the serial path.
                for index, _sample in enumerate(sample_inputs):
                    outcome = outcomes[index]
                    if isinstance(outcome, SampleProcessingError):
                        self.last_run_errors.append(
                            {
                                "sample_id": outcome.sample_id,
                                "stage": outcome.stage,
                                "severity": "error",
                                "error": str(outcome),
                            }
                        )
                        continue

                    sample_id, predicted, used_fastq, assembly_dur, prediction_dur = (
                        outcome
                    )
                    successful_sample_ids.append(sample_id)
                    if used_fastq:
                        assembly_count += 1
                    assembly_seconds += assembly_dur
                    prediction_seconds += prediction_dur
                    all_genes.extend(predicted)

        cluster_start = time.perf_counter()
        anchor_genes = self._build_anchor_genes()
        assignments = self.cluster_engine.cluster_genes(all_genes + anchor_genes)
        if anchor_genes:
            assignments = self._remap_anchor_clusters(
                assignments,
                {gene.key: gene.gene_id for gene in anchor_genes},
            )
        self._override_locus_for_exact_alleles(all_genes, assignments)
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

        final_loci = {locus_id for locus_id in assignments.values()}
        scheme_locus_ids = {gene.gene_id for gene in anchor_genes}
        self.last_run_stats = {
            "samples_total": len(sample_paths),
            "samples_succeeded": len(successful_sample_ids),
            "samples_failed": len(self.last_run_errors),
            "samples_fastq": assembly_count,
            "samples_fasta": len(successful_sample_ids) - assembly_count,
            "genes_predicted": len(all_genes),
            "loci_discovered": len(final_loci),
            "scheme_loci_anchored": len(final_loci & scheme_locus_ids),
            "novel_loci": len(final_loci - scheme_locus_ids),
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

    def _build_anchor_genes(self) -> list[PredictedGene]:
        """Create pseudo-genes carrying each scheme locus representative.

        Anchors ride along into clustering so sample genes can be pinned
        to scheme loci; they never enter profiles or per-sample stats.
        """
        if not self.locus_representatives:
            return []
        return [
            PredictedGene(
                sample_id=SCHEME_ANCHOR_SAMPLE_ID,
                gene_id=locus_id,
                sequence=sequence,
            )
            for locus_id, sequence in sorted(
                self.locus_representatives.items(),
                key=lambda item: _locus_sort_key(item[0]),
            )
        ]

    def _remap_anchor_clusters(
        self,
        assignments: dict[str, str],
        anchor_loci: dict[str, str],
    ) -> dict[str, str]:
        """Resolve raw cluster IDs to final locus IDs against scheme anchors.

        A cluster adopts the locus of its lowest-numbered anchor; an
        anchorless cluster gets a novel ID continuing after the scheme's
        highest locus number. Novel IDs are assigned in canonical order
        (sorted by smallest real-gene key) so numbering never depends on
        cluster iteration order.
        """
        clusters: dict[str, list[str]] = {}
        for gene_key, cluster_id in assignments.items():
            clusters.setdefault(cluster_id, []).append(gene_key)

        def canonical_key(cluster_id: str) -> str:
            members = clusters[cluster_id]
            # Anchor-only clusters still need a total sort key.
            real_keys = [key for key in members if key not in anchor_loci]
            return min(real_keys) if real_keys else min(members)

        final: dict[str, str] = {}
        novel_counter = self._scheme_max_locus_number
        for cluster_id in sorted(clusters, key=canonical_key):
            members = clusters[cluster_id]
            real_keys = [key for key in members if key not in anchor_loci]
            if not real_keys:
                continue
            anchored = sorted(
                (anchor_loci[key] for key in members if key in anchor_loci),
                key=_locus_sort_key,
            )
            if anchored:
                locus_id = anchored[0]
            else:
                novel_counter += 1
                locus_id = f"locus_{novel_counter}"
            for gene_key in real_keys:
                final[gene_key] = locus_id
        return final

    def _override_locus_for_exact_alleles(
        self,
        genes: list[PredictedGene],
        assignments: dict[str, str],
    ) -> None:
        """Pin exact scheme-allele matches to their allele's own locus.

        Anchored clustering decides locus membership for diverged genes;
        a byte-identical match to a scheme allele derives both locus and
        allele from the hit itself, immune to borderline cluster
        assignments between paralogous loci.
        """
        if not self._scheme_hash_to_allele:
            return
        for gene in genes:
            allele_id = self._scheme_hash_to_allele.get(
                self._compute_hash(gene.sequence)
            )
            if allele_id is None:
                continue
            locus_id = allele_id.rsplit("_", 1)[0]
            if locus_id in self.locus_alleles:
                assignments[gene.key] = locus_id

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

        In load mode, a sequence whose md5 matches a scheme allele of the
        same locus reuses that exact allele ID, bypassing the strategy.

        Args:
            sequence: DNA sequence
            locus_id: Locus identifier
            sample_id: Sample identifier

        Returns:
            Allele ID (e.g., "locus_1_42")
        """
        if locus_id not in self.locus_alleles:
            self.locus_alleles[locus_id] = {}
        if locus_id not in self.locus_representatives:
            self.locus_representatives[locus_id] = sequence

        seq_hash = self._compute_hash(sequence)
        allele_id: str | None = None
        if self._scheme_hash_to_allele:
            candidate = self._scheme_hash_to_allele.get(seq_hash)
            # Reuse only alleles of this locus: a hash shared across loci
            # must not leak a foreign locus ID into the profile.
            if candidate is not None and candidate.startswith(f"{locus_id}_"):
                allele_id = candidate
        if allele_id is None:
            allele_id = self.hash_strategy.get_allele_id(sequence, locus_id)

        # Store the allele assignment
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

        Includes per-locus allele-to-hash maps and one representative
        sequence per locus so a later ``--load-scheme`` run can reuse
        allele IDs and anchor genes to these loci.

        Args:
            output_path: Path to save the scheme
        """
        path = Path(output_path)
        write_scheme_json(
            path,
            self._config_to_dict(),
            self.locus_alleles,
            self.profiles,
            self.locus_representatives,
        )

    def load_scheme(self, input_path: Path | str) -> None:
        """Load a previously discovered scheme.

        Restores allele hashes and per-locus representatives so typing
        reuses scheme allele IDs on exact matches, anchors genes to
        scheme loci, and continues novel numbering after the scheme's
        highest locus and allele numbers.

        Args:
            input_path: Path to the scheme JSON file
        """
        path = Path(input_path)
        scheme = read_scheme_json(path)

        # Restore loci and alleles
        self.locus_alleles = {
            locus_id: dict(alleles) for locus_id, alleles in scheme["loci"].items()
        }

        representatives = scheme.get("representatives", {})
        if not representatives:
            print(
                "Warning: legacy scheme lacks representative sequences; "
                "locus anchoring is disabled. Re-export it with "
                "--save-scheme to enable anchoring.",
                file=sys.stderr,
            )
        self.locus_representatives = dict(representatives)

        # md5 -> allele_id; on a hash shared by two loci the lowest locus
        # number wins so the map is deterministic.
        self._scheme_hash_to_allele = {}
        for locus_id in sorted(self.locus_alleles, key=_locus_sort_key):
            for allele_id, seq_hash in self.locus_alleles[locus_id].items():
                if seq_hash and seq_hash not in self._scheme_hash_to_allele:
                    self._scheme_hash_to_allele[seq_hash] = allele_id

        self._scheme_max_locus_number = max(
            (_trailing_int(locus_id) for locus_id in self.locus_alleles),
            default=0,
        )

        for locus_id, alleles in self.locus_alleles.items():
            highest = max(
                (_trailing_int(allele_id) for allele_id in alleles), default=0
            )
            if highest:
                self.hash_strategy.reserve_allele_numbers(locus_id, highest)

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
