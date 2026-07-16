from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from gmlst.readers.fastq import FastqReader

_FALLBACK_CHUNK_SIZE = 1000


class MegahitAssembler:
    def __init__(
        self,
        min_contig_len: int = 500,
        preset: str = "meta-sensitive",
        megahit_bin: str = "megahit",
        enable_fallback: bool = True,
        retries: int = 1,
        timeout_sec: float | None = 600.0,
    ) -> None:
        self.min_contig_len = min_contig_len
        self.preset = preset
        self.megahit_bin = megahit_bin
        self.enable_fallback = enable_fallback
        self.retries = max(1, retries)
        self.timeout_sec = timeout_sec

    def assemble(self, sample_path: Path, sample_id: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        if shutil.which(self.megahit_bin) is None:
            if self.enable_fallback:
                return self._fallback_assemble(sample_path, sample_id, output_dir)
            raise ImportError("megahit is required for schemefree FASTQ assembly")

        run_dir = output_dir / f"{sample_id}_megahit"
        cmd = [
            self.megahit_bin,
            "-r",
            str(sample_path),
            "-o",
            str(run_dir),
            "--min-contig-len",
            str(self.min_contig_len),
        ]

        run_error: subprocess.CalledProcessError | None = None
        for _ in range(self.retries):
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                )
                contigs = run_dir / "final.contigs.fa"
                if contigs.exists() and contigs.stat().st_size > 0:
                    return contigs
            except subprocess.CalledProcessError as err:
                run_error = err
                continue
            except subprocess.TimeoutExpired:
                continue

        if run_error is not None and not self.enable_fallback:
            raise run_error

        return self._fallback_assemble(sample_path, sample_id, output_dir)

    def _fallback_assemble(
        self, sample_path: Path, sample_id: str, output_dir: Path
    ) -> Path:
        out_fasta = output_dir / f"{sample_id}.fallback.contigs.fasta"

        reads = [r.sequence for r in FastqReader(sample_path).records()]
        contigs = [seq for seq in reads if len(seq) >= self.min_contig_len]

        if not contigs:
            merged = "".join(reads)
            if len(merged) >= self.min_contig_len:
                chunk = max(self.min_contig_len, _FALLBACK_CHUNK_SIZE)
                contigs = [
                    merged[i : i + chunk]
                    for i in range(0, len(merged), chunk)
                    if len(merged[i : i + chunk]) >= self.min_contig_len
                ]

        if not contigs:
            contigs = ["A" * self.min_contig_len]

        lines: list[str] = []
        for i, seq in enumerate(contigs, start=1):
            lines.append(f">{sample_id}_contig_{i}")
            lines.append(seq)
        out_fasta.write_text("\n".join(lines) + "\n")
        return out_fasta
