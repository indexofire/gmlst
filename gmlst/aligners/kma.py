from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Literal

from gmlst.aligners.base import AlignmentResult, AlleleMatch
from gmlst.fasta_io import merge_fasta_files
from gmlst.readers.sample import SampleInput
from gmlst.utils import temp_dir


class KmaAligner:
    def __init__(self, threads: int = 1, **kwargs) -> None:
        self.threads = threads
        self.fastq_mem_mode = bool(kwargs.get("fastq_mem_mode", False))

    @property
    def name(self) -> str:
        return "kma"

    @property
    def supports_fastq(self) -> bool:
        return True

    def check_dependencies(self) -> None:
        if shutil.which("kma") is None:
            raise RuntimeError(
                "kma backend requires KMA binary. Install by source build: "
                "git clone https://github.com/genomicepidemiology/kma.git "
                "&& cd kma && make"
            )

    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
        index_dir.mkdir(parents=True, exist_ok=True)
        merged = merge_fasta_files(allele_fastas, index_dir / "alleles.fasta")
        db_prefix = index_dir / "kma_db"

        subprocess.run(
            [
                "kma",
                "index",
                "-i",
                str(merged),
                "-o",
                str(db_prefix),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return index_dir

    def align(
        self,
        sample: Path | tuple[Path, Path],
        index_path: Path,
        loci: list[str],
        input_type: Literal["fasta", "fastq"],
    ) -> AlignmentResult:
        sample_path = sample[0] if isinstance(sample, tuple) else sample
        sample_id = SampleInput.from_path(sample_path).sample_id
        t0 = time.perf_counter()

        db_prefix = index_path / "kma_db"
        with temp_dir("gmlst_kma_") as tmp_dir:
            out_prefix = tmp_dir / "kma_out"
            cmd = [
                "kma",
                "-o",
                str(out_prefix),
                "-t_db",
                str(db_prefix),
                "-t",
                str(max(1, self.threads)),
            ]
            if isinstance(sample, tuple):
                cmd.extend(["-ipe", str(sample[0]), str(sample[1])])
            else:
                cmd.extend(["-i", str(sample)])
            if input_type == "fasta":
                cmd.append("-asm")
            else:
                cmd.append("-ill")
                if self.fastq_mem_mode:
                    cmd.append("-mem_mode")
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            res_file = out_prefix.with_suffix(".res")
            matches = _parse_kma_res(res_file, loci, input_type)

        runtime = time.perf_counter() - t0
        called_loci = {m.locus for m in matches}
        failed = [loc for loc in loci if loc not in called_loci]
        return AlignmentResult(
            sample_id=sample_id,
            matches=matches,
            failed_loci=failed,
            backend=self.name,
            runtime_seconds=runtime,
        )


def _parse_kma_res(
    path: Path,
    loci: list[str],
    input_type: Literal["fasta", "fastq"],
) -> list[AlleleMatch]:
    loci_set = set(loci)
    results: list[AlleleMatch] = []
    with path.open() as fh:
        header: dict[str, int] | None = None
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("#"):
                cols = line.lstrip("#").split("\t")
                header = {name: idx for idx, name in enumerate(cols)}
                continue
            if header is None:
                continue

            cols = line.split("\t")
            template = cols[header.get("Template", 0)]
            locus, allele_id = _split_template(template)
            if locus not in loci_set:
                continue

            identity = float(cols[header.get("Template_Identity", 4)])
            coverage = float(cols[header.get("Template_Coverage", 5)]) / 100.0
            score = float(cols[header.get("Score", 1)])
            raw_depth = float(cols[header.get("Depth", 8)])
            depth = raw_depth if input_type == "fastq" else None
            template_len = int(float(cols[header.get("Template_length", 3)]))

            results.append(
                AlleleMatch(
                    locus=locus,
                    allele_id=allele_id,
                    identity=identity,
                    coverage=coverage,
                    score=score,
                    depth=depth,
                    alignment_length=template_len,
                )
            )

    return results


def _split_template(template: str) -> tuple[str, str]:
    if "_" in template:
        return tuple(template.rsplit("_", 1))  # type: ignore[return-value]  # rsplit(sep, 1) always yields exactly 2 elements when sep is present
    if "-" in template:
        return tuple(template.rsplit("-", 1))  # type: ignore[return-value]  # rsplit(sep, 1) always yields exactly 2 elements when sep is present
    return (template, "")
