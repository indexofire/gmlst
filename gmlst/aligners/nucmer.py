"""MUMmer4 / nucmer alignment backend.

Strategy
--------
FASTA input only — nucmer aligns genome-to-genome (or short sequences to
a genome).

    nucmer [opts] <reference=genome> <query=alleles>

We then run ``show-coords -rcl`` to extract percent identity and coverage.

FASTQ input:
    Not supported — nucmer requires assembled sequences.

nucmer flags for short allele sequences (~300–800 bp):
    -c 20   minimum cluster size (default 65 is too large for short seqs)
    -l 20   minimum MUM length
    --maxmatch   find all matches, not just unique

    [S1] [E1] [S2] [E2] [LEN1] [LEN2] [%IDY] [LENR] [LENQ] [COVR] [COVQ]
    [FRM] [TAGR] [TAGQ]
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Literal

from gmlst.aligners.base import AlignmentResult, AlleleMatch, split_allele_id
from gmlst.fasta_io import merge_fasta_files
from gmlst.utils import require_tool, run_cmd, temp_dir

logger = logging.getLogger("gmlst.aligners.nucmer")

# Minimum values for a hit to be considered
_MIN_IDENTITY = 70.0
_MIN_COVERAGE = 0.5


class NucmerAligner:
    """MLST aligner using MUMmer4 nucmer."""

    def __init__(self, **kwargs) -> None:
        """Initialize aligner. Accepts kwargs for compatibility with other aligners."""
        pass

    @property
    def name(self) -> str:
        return "nucmer"

    @property
    def supports_fastq(self) -> bool:
        return False

    def check_dependencies(self) -> None:
        require_tool("nucmer")
        require_tool("show-coords")

    # ------------------------------------------------------------------
    # Indexing — nucmer has no separate index step; just merge FASTAs
    # ------------------------------------------------------------------

    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
        """Merge allele FASTAs into one file.  Returns the merged FASTA path."""
        index_dir.mkdir(parents=True, exist_ok=True)
        merged = index_dir / "alleles.fasta"
        if not merged.exists():
            merge_fasta_files(allele_fastas, merged)
        return merged

    # ------------------------------------------------------------------
    # Alignment
    # ------------------------------------------------------------------

    def align(
        self,
        sample: Path,
        index_path: Path,
        loci: list[str],
        input_type: Literal["fasta", "fastq"],
    ) -> AlignmentResult:
        if input_type == "fastq":
            raise ValueError(
                "NucmerAligner does not support FASTQ input. Use kma backend."
            )

        sample_id = sample.stem.split(".")[0]
        t0 = time.perf_counter()

        # index_path is the merged allele FASTA
        alleles_fasta = index_path

        with temp_dir("gmlst_nucmer_") as tmp:
            prefix = tmp / "out"
            # Run nucmer: reference=genome, query=alleles
            run_cmd(
                [
                    "nucmer",
                    "--maxmatch",
                    "-c",
                    "20",
                    "-l",
                    "20",
                    "-p",
                    str(prefix),
                    str(sample),  # reference = genome assembly
                    str(alleles_fasta),  # query     = alleles
                ]
            )
            delta = prefix.with_suffix(".delta")
            coords = tmp / "coords.txt"
            # show-coords writes to stdout; capture it output
            result = run_cmd(
                ["show-coords", "-rcl", "-T", str(delta)],
                capture=True,
                check=False,
            )
            coords.write_text(result.stdout)
            matches = _parse_coords(coords, loci)

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


# ---------------------------------------------------------------------------
# show-coords output parsing
# ---------------------------------------------------------------------------

# Tab-delimited show-coords -rcl -T header pattern to skip
_HEADER_RE = re.compile(r"^[^\d]")


def _parse_coords(path: Path, loci: list[str]) -> list[AlleleMatch]:
    """Parse ``show-coords -rcl -T`` output.

    Expected tab-separated columns (13 columns)::

        S1  E1  S2  E2  LEN1  LEN2  [%IDY]  LENR  LENQ  COVR  COVQ  TAGR  TAGQ

    TAGQ = allele name.
    COVQ = coverage of the query (allele) as a percentage.
    """
    loci_set = set(loci)
    best: dict[tuple[str, str], AlleleMatch] = {}

    if not path.exists() or path.stat().st_size == 0:
        return []

    with path.open() as fh:
        line_num = 0
        for line in fh:
            line_num += 1
            line = line.rstrip()
            if not line or _HEADER_RE.match(line):
                continue
            cols = line.split("\t")
            if len(cols) < 13:
                continue
            try:
                identity = float(cols[6])
                covq = float(cols[10])  # coverage of query (allele) %
                allele_name = cols[12]  # TAGQ = allele name
                aln_len = int(cols[4])  # LEN1 = alignment length on ref
            except (ValueError, IndexError):
                logger.debug("Skipping malformed nucmer coords line: %s", line.rstrip())
                continue

            locus, allele_id = split_allele_id(allele_name)
            if locus not in loci_set:
                continue
            if identity < _MIN_IDENTITY:
                continue

            coverage = covq / 100.0
            if coverage < _MIN_COVERAGE:
                continue

            strand = "+"  # simplified
            key = (locus, allele_id)
            existing = best.get(key)
            if (
                existing is None
                or identity > existing.identity
                or (identity == existing.identity and coverage > existing.coverage)
            ):
                best[key] = AlleleMatch(
                    locus=locus,
                    allele_id=allele_id,
                    identity=identity,
                    coverage=coverage,
                    strand=strand,
                    alignment_length=aln_len,
                    score=identity * coverage / 100.0,
                )

    return list(best.values())
