"""BLASTN alignment backend.

Strategy
--------
FASTA input (assembled genome):
    Query  = allele sequences (all loci concatenated)
    Subject = genome contigs  → makeblastdb on genome
    This matches tseemann/mlst behaviour exactly.

FASTQ input:
    Not supported — BLASTN cannot handle raw reads.
    Use kma backend instead.

Output format
-------------
We use BLAST tabular output format 6 with the following fields::

    qseqid sseqid pident length qlen slen qstart qend sstart send evalue bitscore

The query sequence id encodes locus and allele, e.g. ``arcC_1``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Literal

from gmlst.aligners.base import AlignmentResult, AlleleMatch, split_allele_id
from gmlst.fasta_io import merge_fasta_files
from gmlst.utils import require_tool, run_cmd, temp_dir

logger = logging.getLogger(__name__)

_MIN_BLAST_IDENTITY = 80

# Tabular fields we request from BLAST
_OUTFMT = (
    "6 qseqid sseqid pident length qlen qstart qend sstart send evalue bitscore sseq"
)


class BlastnAligner:
    """MLST aligner using NCBI BLASTN."""

    def __init__(
        self, threads: int = 1, count_same_copy: bool = False, **kwargs
    ) -> None:
        self.threads = threads
        self.count_same_copy = count_same_copy

    @property
    def name(self) -> str:
        return "blastn"

    @property
    def supports_fastq(self) -> bool:
        return False

    def check_dependencies(self) -> None:
        require_tool("blastn")
        require_tool("makeblastdb")

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
        """Concatenate all allele FASTAs and build a BLAST nucleotide database.

        Returns
        -------
        Path
            The BLAST database prefix (e.g. ``index_dir / "alleles"``).
        """
        require_tool("makeblastdb")
        index_dir.mkdir(parents=True, exist_ok=True)

        merged = merge_fasta_files(allele_fastas, index_dir / "alleles.fasta")

        db_prefix = index_dir / "alleles"

        # Build BLAST db only if stale
        nhr = db_prefix.with_suffix(".nhr")
        if not nhr.exists() or nhr.stat().st_mtime < merged.stat().st_mtime:
            logger.info("Building BLAST database at %s …", db_prefix)
            run_cmd(
                [
                    "makeblastdb",
                    "-in",
                    str(merged),
                    "-dbtype",
                    "nucl",
                    "-out",
                    str(db_prefix),
                    "-title",
                    "gmlst_alleles",
                ]
            )
        return db_prefix

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
        """Run BLASTN: allele sequences → assembled genome.

        For FASTA inputs the allele DB is used as **query** and the genome
        as **subject** (``-db`` flag points to the allele index, genome is
        passed with ``-query``).

        Wait — tseemann does it the other way: genome is the db, alleles are
        queries.  We follow the same convention for compatibility:

            blastn -query alleles.fasta -db genome -outfmt 6 …

        This avoids building a db per sample (samples are queries would need
        per-sample dbs).  Instead we build one allele db and query each
        sample against it.

        Actually the most efficient approach for assembled genomes is:
            -query <allele_fasta>  -subject <genome>  (no db needed per run)
        Or build a db from the genome once per sample (tseemann does this).

        We use ``-query <alleles> -subject <genome>`` for simplicity — no
        per-sample database build required.
        """
        if input_type == "fastq":
            raise ValueError(
                "BlastnAligner does not support FASTQ input. Use kma backend."
            )

        sample_id = sample.stem.split(".")[0]
        t0 = time.perf_counter()

        # The index_path is the allele db prefix; we query alleles against genome
        alleles_fasta = index_path.parent / "alleles.fasta"

        with temp_dir("gmlst_blastn_") as tmp:
            out_file = tmp / "hits.tsv"
            run_cmd(
                [
                    "blastn",
                    "-query",
                    str(alleles_fasta),
                    "-subject",
                    str(sample),
                    "-outfmt",
                    _OUTFMT,
                    "-out",
                    str(out_file),
                    "-perc_identity",
                    str(_MIN_BLAST_IDENTITY),
                    "-dust",
                    "no",
                    "-num_threads",
                    str(self.threads),
                ],
            )
            matches = _parse_blast_output(
                out_file,
                loci,
                count_same_copy=self.count_same_copy,
            )

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
# Output parsing
# ---------------------------------------------------------------------------


def _parse_blast_output(
    path: Path,
    loci: list[str],
    *,
    count_same_copy: bool = False,
) -> list[AlleleMatch]:
    """Parse BLAST tabular output and return :class:`AlleleMatch` objects.

    Fields (format 6 custom)::

        qseqid sseqid pident length qlen qstart qend sstart send evalue bitscore

    The query id encodes locus and allele as ``<locus>_<allele_id>``.
    We take the **best hit per (locus, allele_id)** pair — highest identity,
    then longest alignment.
    """
    loci_set = set(loci)
    # best[(locus, allele_id)] = AlleleMatch
    best: dict[tuple[str, str], AlleleMatch] = {}
    copies: dict[tuple[str, str], set[tuple[str, str, str]]] = {}

    if not path.exists():
        return []

    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 11:
                continue

            qseqid = parts[0]
            pident = float(parts[2])
            aln_len = int(parts[3])
            qlen = int(parts[4])

            # Parse locus + allele from query id (e.g. "arcC_1")
            locus, allele_id = split_allele_id(qseqid)
            if locus not in loci_set:
                continue

            coverage = aln_len / qlen if qlen > 0 else 0.0
            key = (locus, allele_id)
            if count_same_copy:
                sseqid = parts[1]
                sstart = parts[7]
                send = parts[8]
                start, end = (sstart, send) if sstart <= send else (send, sstart)
                copies.setdefault(key, set()).add((sseqid, start, end))

            existing = best.get(key)
            if existing is None or (
                pident > existing.identity
                or (pident == existing.identity and coverage > existing.coverage)
            ):
                sseqid = parts[1]
                sstart = int(parts[7])
                send = int(parts[8])
                strand = "-" if sstart > send else "+"
                seq_start = min(sstart, send)
                seq_end = max(sstart, send)
                sequence = parts[11] if len(parts) > 11 else None

                best[key] = AlleleMatch(
                    locus=locus,
                    allele_id=allele_id,
                    identity=pident,
                    coverage=coverage,
                    alignment_length=aln_len,
                    score=float(parts[10]),
                    sequence=sequence,
                    strand=strand,
                    query_contig=sseqid,
                    query_start=seq_start,
                    query_end=seq_end,
                )

    if count_same_copy:
        for key, match in best.items():
            match.copy_count = max(1, len(copies.get(key, set())))

    return list(best.values())
