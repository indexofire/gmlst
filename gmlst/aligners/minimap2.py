"""minimap2 alignment backend.

Strategy
--------
FASTA input (assembled genome):
    Preset ``asm5`` — for <5% divergence (typical for same-species cgMLST alleles).
    Query  = allele sequences (merged FASTA)
    Target = genome assembly
    Output = PAF

FASTQ input is not supported. Use KMA for raw reads.

PAF format (tab-separated, 12+ columns)
----------------------------------------
0  qname     query name
1  qlen      query length
2  qstart    query start (0-based)
3  qend      query end
4  strand    +/-
5  tname     target name
6  tlen      target length
7  tstart    target start
8  tend      target end
9  nmatch    number of matching bases
10 blen      alignment block length
11 mapq      mapping quality
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Literal

from gmlst.aligners.base import (
    AlignmentResult,
    AlleleMatch,
    build_alignment_result,
    cap_fragments,
    select_best_matches,
    split_allele_id,
)
from gmlst.fasta_io import iter_fasta_records, merge_fasta_files
from gmlst.readers.sample import SampleInput
from gmlst.utils import require_tool, run_cmd, temp_dir

logger = logging.getLogger(__name__)

_COMPLEMENT = str.maketrans("ACGTUNacgtun", "TGCAANtgcaan")


def _revcomp(seq: str) -> str:
    """Reverse-complement a nucleotide string."""
    return seq.translate(_COMPLEMENT)[::-1]


_FASTA_PRESET = os.getenv("GMLST_MINIMAP2_FASTA_PRESET", "asm5")
_FASTA_SPEED_PROFILES: dict[str, list[str]] = {
    "default": [],
    "fast": ["-w", "15", "-e", "1000", "-K", "1G"],
    "ultrafast": [
        "-w",
        "15",
        "-e",
        "1000",
        "-f",
        "0.001",
        "-U",
        "50,1000",
        "-K",
        "1G",
    ],
}


class Minimap2Aligner:
    """MLST aligner using minimap2 (FASTA assemblies only)."""

    def __init__(self, threads: int = 1, **kwargs) -> None:
        """Initialize aligner. Accepts kwargs for compatibility with other aligners."""
        self.threads = threads
        raw_fasta_emit_cigar = kwargs.get(
            "fasta_emit_cigar",
            os.getenv("GMLST_MINIMAP2_FASTA_EMIT_CIGAR", "1"),
        )
        if isinstance(raw_fasta_emit_cigar, bool):
            self.fasta_emit_cigar = raw_fasta_emit_cigar
        else:
            self.fasta_emit_cigar = str(raw_fasta_emit_cigar).strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        requested_speed_profile = (
            str(
                kwargs.get(
                    "fasta_speed_profile",
                    os.getenv("GMLST_MINIMAP2_FASTA_SPEED_PROFILE", "default"),
                )
            )
            .strip()
            .lower()
        )
        if requested_speed_profile not in _FASTA_SPEED_PROFILES:
            logger.warning(
                "Unknown minimap2 FASTA speed profile '%s', falling back to 'default'.",
                requested_speed_profile,
            )
            requested_speed_profile = "default"
        self.fasta_speed_profile = requested_speed_profile

    @property
    def name(self) -> str:
        return "minimap2"

    @property
    def supports_fastq(self) -> bool:
        return False

    def check_dependencies(self) -> None:
        require_tool("minimap2")

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
        """Merge allele FASTAs and build a minimap2 index."""
        require_tool("minimap2")
        index_dir.mkdir(parents=True, exist_ok=True)

        merged = index_dir / "alleles.fasta"
        if not merged.exists():
            merge_fasta_files(allele_fastas, merged)

        mmi = index_dir / "alleles.asm5.mmi"
        if not mmi.exists():
            logger.info("Building minimap2 index (%s) at %s …", _FASTA_PRESET, mmi)
            run_cmd(
                [
                    "minimap2",
                    "-x",
                    _FASTA_PRESET,
                    "-d",
                    str(mmi),
                    str(merged),
                ]
            )

        return index_dir

    # ------------------------------------------------------------------
    # Alignment
    # ------------------------------------------------------------------

    def align(
        self,
        sample: Path | tuple[Path, Path],
        index_path: Path,
        loci: list[str],
        input_type: Literal["fasta", "fastq"],
    ) -> AlignmentResult:
        """Align an assembly against the prebuilt allele index.

        Runs minimap2 (alleles as query, genome as target) in a temporary
        directory and parses the PAF output into :class:`AlleleMatch`
        entries. FASTA assemblies only — FASTQ input is not supported
        (use the KMA backend).
        """
        sample_path = sample[0] if isinstance(sample, tuple) else sample
        sample_id = SampleInput.from_path(sample_path).sample_id
        t0 = time.perf_counter()

        matches, fragments = self._align_fasta(sample_path, index_path, loci)

        runtime = time.perf_counter() - t0
        return build_alignment_result(
            sample_id=sample_id,
            backend=self.name,
            matches=matches,
            fragments=fragments,
            loci=loci,
            runtime_seconds=runtime,
        )

    def _align_fasta(
        self, genome: Path, index_dir: Path, loci: list[str]
    ) -> tuple[list[AlleleMatch], list[AlleleMatch]]:
        """allele sequences → genome assembly (asm5 preset)."""
        alleles_fasta = index_dir / "alleles.fasta"
        with temp_dir("gmlst_mm2_") as tmp:
            paf = tmp / "hits.paf"
            run_cmd(
                [
                    "minimap2",
                    "-x",
                    _FASTA_PRESET,
                    "-t",
                    str(self.threads),
                    *_FASTA_SPEED_PROFILES[self.fasta_speed_profile],
                    *(["-c"] if self.fasta_emit_cigar else []),
                    "--secondary=no",
                    "-o",
                    str(paf),
                    str(genome),  # target (genome assembly)
                    str(alleles_fasta),  # query (alleles)
                ]
            )
            contigs = {name: seq for name, seq in iter_fasta_records(genome)}
            return _parse_paf(
                paf,
                loci,
                contigs,
            )


# ---------------------------------------------------------------------------
# PAF parsing helper
# ---------------------------------------------------------------------------


def _parse_paf(
    path: Path,
    loci: list[str],
    contigs: dict[str, str],
) -> tuple[list[AlleleMatch], list[AlleleMatch]]:
    """Parse PAF for FASTA mode where the query is the allele sequence.

    *matches* keeps the best hit per (locus, allele) — semantics unchanged.
    *fragments* records every PAF row with ``sequence`` set to the
    allele-oriented contig slice (reverse-complemented for ``-`` strand),
    so downstream join logic never needs to re-orient anything.

    Contig slicing/reverse-complementing is deferred to after the
    per-locus fragment cap: only surviving fragments pay for it.
    """
    loci_set = set(loci)
    fragments: list[AlleleMatch] = []
    allele_id_cache: dict[str, tuple[str, str]] = {}

    if not path.exists():
        return [], []

    with path.open() as fh:
        for line in fh:
            cols = line.rstrip().split("\t")
            if len(cols) < 12:
                continue

            allele_name = cols[0]  # query = allele
            qlen = int(cols[1])
            qstart = int(cols[2])
            qend = int(cols[3])
            strand = cols[4]
            contig_name = cols[5]
            contig_len = int(cols[6])
            contig_start = int(cols[7])
            contig_end = int(cols[8])
            nmatch = int(cols[9])
            blen = int(cols[10])

            cached_ids = allele_id_cache.get(allele_name)
            if cached_ids is None:
                cached_ids = split_allele_id(allele_name)
                allele_id_cache[allele_name] = cached_ids
            locus, allele_id = cached_ids
            if locus not in loci_set:
                continue

            coverage = (qend - qstart) / qlen if qlen > 0 else 0.0
            nm = 0
            for tag in cols[12:]:
                if tag.startswith("NM:i:"):
                    nm = int(tag[5:])
                    break
            total_aligned = nmatch + nm
            identity = (nmatch / total_aligned * 100.0) if total_aligned > 0 else 0.0

            fragments.append(
                AlleleMatch(
                    locus=locus,
                    allele_id=allele_id,
                    identity=identity,
                    coverage=coverage,
                    strand=strand,
                    alignment_length=blen,
                    score=identity * coverage,
                    query_contig=contig_name,
                    query_contig_length=contig_len,
                    query_start=contig_start,
                    query_end=contig_end,
                    allele_length=qlen,
                    allele_start=qstart,
                    allele_end=qend,
                )
            )

    best: list[AlleleMatch] = []
    for frag in select_best_matches(fragments):
        assert frag.query_start is not None and frag.query_end is not None
        assert frag.allele_start is not None and frag.allele_end is not None
        best.append(
            AlleleMatch(
                locus=frag.locus,
                allele_id=frag.allele_id,
                identity=frag.identity,
                coverage=frag.coverage,
                strand=frag.strand,
                alignment_length=frag.alignment_length,
                score=frag.score,
                query_contig=frag.query_contig,
                query_contig_length=frag.query_contig_length,
                query_start=min(frag.query_start, frag.query_end),
                query_end=max(frag.query_start, frag.query_end),
                allele_length=frag.allele_length,
                allele_start=min(frag.allele_start, frag.allele_end),
                allele_end=max(frag.allele_start, frag.allele_end),
            )
        )

    capped = cap_fragments(fragments)
    for frag in capped:
        assert frag.query_contig is not None
        contig_seq = contigs.get(frag.query_contig)
        block = contig_seq[frag.query_start : frag.query_end] if contig_seq else None
        if block is not None and frag.strand == "-":
            block = _revcomp(block)
        frag.sequence = block

    return best, capped
