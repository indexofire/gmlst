from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from gmlst.readers.fasta import FastaReader

try:
    import pyrodigal
except ImportError:
    pyrodigal = None

_FALLBACK_WINDOW_SIZE = 900


@dataclass(frozen=True)
class PredictedGene:
    sample_id: str
    gene_id: str
    sequence: str
    contig_id: str | None = None
    start: int | None = None
    end: int | None = None
    strand: str | None = None
    partial_begin: bool | None = None
    partial_end: bool | None = None

    @property
    def key(self) -> str:
        return f"{self.sample_id}|{self.gene_id}"


def create_pyrodigal_training_file(sample_path: Path, output_path: Path) -> Path:
    if pyrodigal is None:
        raise ImportError("pyrodigal is required to create training files")
    records = list(FastaReader(sample_path).records())
    contigs = [record.sequence.encode("ascii") for record in records]
    if not contigs:
        raise ValueError(f"No sequences found in {sample_path}")

    finder = pyrodigal.GeneFinder(meta=False)
    training_info = finder.train(contigs[0], *contigs[1:])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        training_info.dump(handle)
    return output_path


class ProdigalPredictor:
    def __init__(
        self,
        tool: str = "pyrodigal",
        mode: str = "meta",
        min_gene_len: int = 100,
        max_gene_len: int = 5000,
        training_file: Path | str | None = None,
        closed_ends: bool = False,
        prodigal_bin: str = "prodigal",
        enable_fallback: bool = True,
        timeout_sec: float = 300.0,
    ) -> None:
        self.tool = tool
        self.mode = mode
        self.min_gene_len = min_gene_len
        self.max_gene_len = max_gene_len
        self.training_file = Path(training_file) if training_file is not None else None
        self.closed_ends = closed_ends
        self.prodigal_bin = prodigal_bin
        self.enable_fallback = enable_fallback
        self.timeout_sec = timeout_sec

    def predict(self, sample_path: Path, sample_id: str) -> list[PredictedGene]:
        if self.tool == "pyrodigal":
            try:
                return self._predict_with_pyrodigal(sample_path, sample_id)
            except (RuntimeError, ValueError) as exc:
                if self.enable_fallback and self.mode.strip().lower() == "single":
                    message = str(exc).lower()
                    if (
                        "at least 20000" in message
                        or "without having trained" in message
                    ):
                        return self._predict_with_pyrodigal(
                            sample_path, sample_id, "meta"
                        )
                if self.enable_fallback:
                    return self._predict_with_prodigal_cli(sample_path, sample_id)
                raise
            except ImportError:
                if self.enable_fallback:
                    return self._predict_with_prodigal_cli(sample_path, sample_id)
                raise
        return self._predict_with_prodigal_cli(sample_path, sample_id)

    def _predict_with_prodigal_cli(
        self,
        sample_path: Path,
        sample_id: str,
    ) -> list[PredictedGene]:
        if shutil.which(self.prodigal_bin) is None:
            if self.enable_fallback:
                return self._fallback_predict(sample_path, sample_id)
            raise ImportError("prodigal is required for schemefree gene prediction")

        with tempfile.TemporaryDirectory(prefix="gmlst_prodigal_") as temp_dir:
            genes_fna = Path(temp_dir) / "genes.fna"
            subprocess.run(
                [
                    self.prodigal_bin,
                    "-i",
                    str(sample_path),
                    "-d",
                    str(genes_fna),
                    "-f",
                    "gff",
                    "-p",
                    self.mode,
                    "-q",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
            return self._parse_predicted_genes(genes_fna, sample_id)

    def _predict_with_pyrodigal(
        self,
        sample_path: Path,
        sample_id: str,
        mode_override: str | None = None,
    ) -> list[PredictedGene]:
        if pyrodigal is None:
            raise ImportError("pyrodigal is required for pyrodigal gene prediction")

        mode = self.mode.strip().lower() if mode_override is None else mode_override
        meta_mode = mode == "meta"
        training_info = None
        if self.training_file is not None:
            with self.training_file.open("rb") as handle:
                training_info = pyrodigal.TrainingInfo.load(handle)

        finder = pyrodigal.GeneFinder(
            training_info=training_info,
            meta=meta_mode,
            closed=self.closed_ends,
            min_gene=self.min_gene_len,
        )

        records = list(FastaReader(sample_path).records())
        if not meta_mode and training_info is None and records:
            contigs = [record.sequence.encode("ascii") for record in records]
            finder.train(contigs[0], *contigs[1:])

        genes: list[PredictedGene] = []
        gene_index = 1
        for record in records:
            predicted_genes = finder.find_genes(record.sequence.encode("ascii"))
            for gene in predicted_genes:
                sequence = gene.sequence().upper()
                if (
                    len(sequence) < self.min_gene_len
                    or len(sequence) > self.max_gene_len
                ):
                    continue
                genes.append(
                    PredictedGene(
                        sample_id=sample_id,
                        gene_id=f"gene_{gene_index}",
                        sequence=sequence,
                        contig_id=record.seq_id,
                        start=int(gene.begin),
                        end=int(gene.end),
                        strand="+" if int(gene.strand) >= 0 else "-",
                        partial_begin=bool(gene.partial_begin),
                        partial_end=bool(gene.partial_end),
                    )
                )
                gene_index += 1
        return genes

    def _parse_predicted_genes(
        self, genes_fna: Path, sample_id: str
    ) -> list[PredictedGene]:
        genes: list[PredictedGene] = []
        for index, record in enumerate(FastaReader(genes_fna).records(), start=1):
            seq = record.sequence
            if len(seq) < self.min_gene_len or len(seq) > self.max_gene_len:
                continue
            header_parts = [part.strip() for part in record.header.split("#")]
            contig_id = header_parts[0] if header_parts else None
            start: int | None = None
            end: int | None = None
            strand: str | None = None
            partial_begin: bool | None = None
            partial_end: bool | None = None
            if len(header_parts) >= 4:
                with_start = header_parts[1]
                with_end = header_parts[2]
                with_strand = header_parts[3]
                if with_start.isdigit():
                    start = int(with_start)
                if with_end.isdigit():
                    end = int(with_end)
                if with_strand in {"1", "+"}:
                    strand = "+"
                elif with_strand in {"-1", "-"}:
                    strand = "-"
            if len(header_parts) >= 5:
                attrs = header_parts[4]
                marker = "partial="
                idx = attrs.find(marker)
                if idx >= 0 and idx + len(marker) + 1 < len(attrs):
                    pair = attrs[idx + len(marker) : idx + len(marker) + 2]
                    if (
                        len(pair) == 2
                        and pair[0] in {"0", "1"}
                        and pair[1] in {"0", "1"}
                    ):
                        partial_begin = pair[0] == "1"
                        partial_end = pair[1] == "1"
            genes.append(
                PredictedGene(
                    sample_id=sample_id,
                    gene_id=f"gene_{index}",
                    sequence=seq,
                    contig_id=contig_id,
                    start=start,
                    end=end,
                    strand=strand,
                    partial_begin=partial_begin,
                    partial_end=partial_end,
                )
            )
        return genes

    def _fallback_predict(
        self, sample_path: Path, sample_id: str
    ) -> list[PredictedGene]:
        genes: list[PredictedGene] = []
        index = 1
        for record in FastaReader(sample_path).records():
            sequence = record.sequence
            window = max(
                self.min_gene_len, min(_FALLBACK_WINDOW_SIZE, self.max_gene_len)
            )
            if (
                len(sequence) <= self.max_gene_len
                and len(sequence) >= self.min_gene_len
            ):
                genes.append(
                    PredictedGene(
                        sample_id=sample_id,
                        gene_id=f"gene_{index}",
                        sequence=sequence,
                        contig_id=record.seq_id,
                        start=1,
                        end=len(sequence),
                        strand="+",
                        partial_begin=False,
                        partial_end=False,
                    )
                )
                index += 1
                continue

            for start in range(0, len(sequence), window):
                fragment = sequence[start : start + window]
                if len(fragment) < self.min_gene_len:
                    continue
                genes.append(
                    PredictedGene(
                        sample_id=sample_id,
                        gene_id=f"gene_{index}",
                        sequence=fragment,
                        contig_id=record.seq_id,
                        start=start + 1,
                        end=start + len(fragment),
                        strand="+",
                        partial_begin=start > 0,
                        partial_end=(start + len(fragment)) < len(sequence),
                    )
                )
                index += 1
        return genes
