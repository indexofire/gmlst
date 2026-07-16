from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from gmlst.core.gene_predictor import PredictedGene
from gmlst.utils import temp_dir


class MMseqsClusterEngine:
    def __init__(
        self,
        min_seq_id: float = 0.95,
        coverage: float = 0.8,
        cov_mode: int = 1,
        cluster_mode: int = 0,
        threads: str = "auto",
        mmseqs_bin: str = "mmseqs",
        enable_fallback: bool = True,
        timeout_sec: float = 300.0,
    ) -> None:
        self.min_seq_id = min_seq_id
        self.coverage = coverage
        self.cov_mode = cov_mode
        self.cluster_mode = cluster_mode
        self.threads = threads
        self.mmseqs_bin = mmseqs_bin
        self.enable_fallback = enable_fallback
        self.timeout_sec = timeout_sec

    def cluster_genes(self, genes: list[PredictedGene]) -> dict[str, str]:
        if not genes:
            return {}

        if shutil.which(self.mmseqs_bin) is None:
            if self.enable_fallback:
                return self._fallback_cluster(genes)
            raise ImportError("mmseqs is required for schemefree clustering")

        with temp_dir("gmlst_schemefree_") as tmp:
            temp_path = Path(tmp)
            input_fasta = temp_path / "genes.fasta"
            result_prefix = temp_path / "clusters"
            tmp_dir = temp_path / "tmp"

            self._write_genes_fasta(genes, input_fasta)

            cmd = [
                self.mmseqs_bin,
                "easy-cluster",
                str(input_fasta),
                str(result_prefix),
                str(tmp_dir),
                "--min-seq-id",
                str(self.min_seq_id),
                "-c",
                str(self.coverage),
                "--cov-mode",
                str(self.cov_mode),
                "--cluster-mode",
                str(self.cluster_mode),
                "--threads",
                self._resolve_threads(),
            ]

            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )

            cluster_tsv = result_prefix.with_name(f"{result_prefix.name}_cluster.tsv")
            if not cluster_tsv.exists():
                return self._fallback_cluster(genes)
            return self._parse_cluster_tsv(cluster_tsv)

    def _resolve_threads(self) -> str:
        if self.threads == "auto":
            return str(max(1, os.cpu_count() or 1))
        return self.threads

    def _write_genes_fasta(self, genes: list[PredictedGene], path: Path) -> None:
        lines: list[str] = []
        for gene in genes:
            lines.append(f">{gene.key}")
            lines.append(gene.sequence)
        path.write_text("\n".join(lines) + "\n")

    def _parse_cluster_tsv(self, cluster_tsv: Path) -> dict[str, str]:
        representative_to_locus: dict[str, str] = {}
        assignments: dict[str, str] = {}
        locus_counter = 1

        for line in cluster_tsv.read_text().splitlines():
            if not line.strip():
                continue
            representative, member = line.split("\t", maxsplit=1)
            locus_id = representative_to_locus.get(representative)
            if locus_id is None:
                locus_id = f"locus_{locus_counter}"
                representative_to_locus[representative] = locus_id
                locus_counter += 1
            assignments[member] = locus_id
        return assignments

    def _fallback_cluster(self, genes: list[PredictedGene]) -> dict[str, str]:
        hash_to_locus: dict[str, str] = {}
        assignments: dict[str, str] = {}
        locus_counter = 1

        for gene in genes:
            seq_hash = hashlib.sha1(gene.sequence.encode()).hexdigest()
            locus_id = hash_to_locus.get(seq_hash)
            if locus_id is None:
                locus_id = f"locus_{locus_counter}"
                hash_to_locus[seq_hash] = locus_id
                locus_counter += 1
            assignments[gene.key] = locus_id
        return assignments
