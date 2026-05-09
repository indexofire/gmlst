"""minimap2 alignment backend.

Strategy
--------
FASTA input (assembled genome):
    Preset ``asm20`` — for ~5–10 % divergence between alleles and assembly.
    Query  = allele sequences (merged FASTA)
    Target = genome assembly
    Output = PAF

FASTQ input (raw reads):
    Preset ``sr`` — optimised for short Illumina reads.
    Query  = reads
    Target = allele sequences (all loci merged)
    Output = PAF

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

import gzip
import logging
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from gmlst.aligners.base import AlignmentResult, AlleleMatch
from gmlst.aligners.blastn import _split_allele_id
from gmlst.fasta_io import iter_fasta_records
from gmlst.readers.sample import SampleInput
from gmlst.utils import require_tool, run_cmd, temp_dir

logger = logging.getLogger("gmlst.aligners.minimap2")

_FASTA_PRESET = "asm20"
_FASTQ_PRESET = "sr"
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
_CIGAR_RE = re.compile(r"(\d+)([MIDNSHP=X])")
_REVCOMP_TABLE = str.maketrans("ACGT", "TGCA")
_BASE_BITS = {ord("A"): 0, ord("C"): 1, ord("G"): 2, ord("T"): 3}
_EXHAUSTIVE_TARGETED_MAX_LOCI = 20
_MLST_TARGETED_SHORTLIST_SIZE = 10
_MLST_TARGETED_NEIGHBOR_COUNT = 40
_MLST_UNCERTAIN_COVERAGE_THRESHOLD = 0.8


class Minimap2Aligner:
    """MLST aligner using minimap2."""

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
        requested_engine = (
            str(
                kwargs.get(
                    "kmer_engine",
                    os.getenv("GMLST_MINIMAP2_KMER_ENGINE", "python"),
                )
            )
            .strip()
            .lower()
        )
        if requested_engine not in {"python", "kmc", "auto"}:
            logger.warning(
                "Unknown minimap2 k-mer engine '%s', falling back to 'python'.",
                requested_engine,
            )
            requested_engine = "python"
        self.kmer_engine = requested_engine
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
        return True

    def check_dependencies(self) -> None:
        require_tool("minimap2")
        if self.kmer_engine == "kmc":
            require_tool("kmc")
            require_tool("kmc_tools")

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
        """Merge allele FASTAs and (optionally) pre-build a ``.mmi`` index.

        We build two indexes: one for FASTA mode (asm20) and one for FASTQ
        mode (sr).  Returns the directory containing both.
        """
        require_tool("minimap2")
        index_dir.mkdir(parents=True, exist_ok=True)

        merged = index_dir / "alleles.fasta"
        if not merged.exists():
            with merged.open("wb") as out:
                for fasta in sorted(allele_fastas):
                    with fasta.open("rb") as f:
                        import shutil

                        shutil.copyfileobj(f, out)
        if not merged.exists():
            with merged.open("w") as out:
                for fasta in sorted(allele_fastas):
                    out.write(fasta.read_text())

        for preset, suffix in [(_FASTA_PRESET, "asm20"), (_FASTQ_PRESET, "sr")]:
            mmi = index_dir / f"alleles.{suffix}.mmi"
            if not mmi.exists():
                logger.info("Building minimap2 index (%s) at %s …", preset, mmi)
                run_cmd(
                    [
                        "minimap2",
                        "-x",
                        preset,
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
        sample_path = sample[0] if isinstance(sample, tuple) else sample
        sample_id = SampleInput.from_path(sample_path).sample_id
        t0 = time.perf_counter()

        if input_type == "fasta":
            matches = self._align_fasta(sample_path, index_path, loci)
        else:
            matches = self._align_fastq(sample, index_path, loci)

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

    def _align_fasta(
        self, genome: Path, index_dir: Path, loci: list[str]
    ) -> list[AlleleMatch]:
        """allele sequences → genome assembly (asm20 preset)."""
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
            return _parse_paf(
                paf,
                loci,
                query_is_allele=True,
            )

    def _align_fastq(
        self,
        reads: Path | tuple[Path, Path],
        index_dir: Path,
        loci: list[str],
    ) -> list[AlleleMatch]:
        """reads → allele sequences (sr preset); accumulate per-allele depth."""
        mmi = index_dir / f"alleles.{_FASTQ_PRESET}.mmi"
        alleles_fasta = index_dir / "alleles.fasta"
        reference = str(mmi) if mmi.exists() else str(alleles_fasta)

        with temp_dir("gmlst_mm2_") as tmp:
            paf = tmp / "hits.paf"
            cmd = [
                "minimap2",
                "-x",
                _FASTQ_PRESET,
                "-t",
                str(self.threads),
                "-o",
                str(paf),
                reference,  # target = alleles
            ]
            if isinstance(reads, tuple):
                cmd.extend([str(reads[0]), str(reads[1])])
            else:
                cmd.append(str(reads))
            run_cmd(cmd)
            candidates_by_locus = _parse_paf_fastq_candidates(paf, loci)

        shortlist_by_locus = _shortlist_candidates_by_locus(candidates_by_locus)
        if not shortlist_by_locus:
            return []

        seqs = _load_allele_sequences(alleles_fasta)
        support = self._compute_kmer_support(shortlist_by_locus, reads, seqs)
        top_by_locus = _top_candidates_by_locus(shortlist_by_locus, support)
        if not top_by_locus:
            return []

        targeted_shortlist = _build_targeted_validation_shortlist(
            shortlist_by_locus,
            top_by_locus,
            seqs,
            support,
            total_loci=len(loci),
        )
        validated = _validate_top_candidates_with_targeted_mapping(
            reads,
            targeted_shortlist,
            seqs,
            support,
            threads=self.threads,
        )
        if validated:
            return validated

        return list(top_by_locus.values())

    def _compute_kmer_support(
        self,
        shortlist_by_locus: dict[str, list[AlleleMatch]],
        reads: Path | tuple[Path, Path],
        seqs: dict[tuple[str, str], str],
    ) -> dict[tuple[str, str], float]:
        engine = self.kmer_engine
        if engine == "auto":
            engine = "kmc" if _kmc_available() else "python"

        if engine == "kmc":
            try:
                return _rescore_with_unique_kmers_kmc(
                    shortlist_by_locus,
                    reads,
                    seqs,
                    threads=self.threads,
                )
            except RuntimeError as exc:
                logger.warning(
                    "KMC k-mer scoring unavailable (%s); "
                    "falling back to python scorer.",
                    exc,
                )

        return _rescore_with_unique_kmers(shortlist_by_locus, reads, seqs)


# ---------------------------------------------------------------------------
# PAF parsing helpers
# ---------------------------------------------------------------------------


def _parse_paf(
    path: Path,
    loci: list[str],
    *,
    query_is_allele: bool,
) -> list[AlleleMatch]:
    """Parse PAF for FASTA mode where the query is the allele sequence."""
    loci_set = set(loci)
    best: dict[tuple[str, str], AlleleMatch] = {}

    if not path.exists():
        return []

    with path.open() as fh:
        for line in fh:
            cols = line.rstrip().split("\t")
            if len(cols) < 12:
                continue

            if query_is_allele:
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
            else:
                allele_name = cols[5]  # target = allele
                qlen = int(cols[6])
                qstart = int(cols[7])
                qend = int(cols[8])
                strand = cols[4]
                contig_name = cols[0]
                contig_len = int(cols[1])
                contig_start = int(cols[2])
                contig_end = int(cols[3])
                nmatch = int(cols[9])
                blen = int(cols[10])

            locus, allele_id = _split_allele_id(allele_name)
            if locus not in loci_set:
                continue

            coverage = (qend - qstart) / qlen if qlen > 0 else 0.0
            identity = (nmatch / blen * 100.0) if blen > 0 else 0.0
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
                    alignment_length=blen,
                    score=identity * coverage,
                    query_contig=contig_name,
                    query_contig_length=contig_len,
                    query_start=min(contig_start, contig_end),
                    query_end=max(contig_start, contig_end),
                    allele_length=qlen,
                    allele_start=min(qstart, qend),
                    allele_end=max(qstart, qend),
                )

    return list(best.values())


def _parse_paf_fastq(path: Path, loci: list[str]) -> list[AlleleMatch]:
    candidates_by_locus = _parse_paf_fastq_candidates(path, loci)
    selected: list[AlleleMatch] = []
    for candidates in candidates_by_locus.values():
        if not candidates:
            continue
        selected.append(candidates[0])
    return selected


def _parse_paf_fastq_candidates(
    path: Path, loci: list[str]
) -> dict[str, list[AlleleMatch]]:
    """Parse PAF for FASTQ mode: reads mapped to alleles.

    Uses per-read, per-locus winner selection before allele aggregation to
    reduce ambiguous multi-mapping noise across highly similar alleles.
    """
    loci_set = set(loci)

    candidates_by_read_locus: dict[tuple[str, str], list[_ReadHit]] = {}
    total_cov_by_key: dict[tuple[str, str], float] = {}
    tlen_by_key: dict[tuple[str, str], int] = {}
    nmatch_by_key: dict[tuple[str, str], float] = {}
    blen_by_key: dict[tuple[str, str], float] = {}
    intervals_by_key: dict[tuple[str, str], list[tuple[int, int]]] = {}
    support_reads_by_key: dict[tuple[str, str], float] = {}

    if not path.exists():
        return {}

    with path.open() as fh:
        for line in fh:
            cols = line.rstrip().split("\t")
            if len(cols) < 12:
                continue

            qname = cols[0]
            qlen = int(cols[1])
            qstart = int(cols[2])
            qend = int(cols[3])
            # target = allele
            allele_name = cols[5]
            tlen = int(cols[6])
            tstart = int(cols[7])
            tend = int(cols[8])
            nmatch = int(cols[9])
            blen = int(cols[10])
            mapq = int(cols[11])

            locus, allele_id = _split_allele_id(allele_name)
            if locus not in loci_set:
                continue

            qspan = max(qend - qstart, 0)
            if qlen <= 0:
                continue
            query_cov = qspan / qlen
            if query_cov < 0.8:
                continue

            tspan = abs(tend - tstart)
            identity = (nmatch / blen) if blen > 0 else 0.0
            if blen <= 0:
                continue

            candidate = _ReadHit(
                locus=locus,
                allele_id=allele_id,
                tlen=tlen,
                tstart=min(tstart, tend),
                tend=max(tstart, tend),
                nmatch=nmatch,
                blen=blen,
                tspan=tspan,
                identity=identity,
                rank=(identity, query_cov, float(nmatch), float(mapq), float(tspan)),
            )

            read_locus_key = (qname, locus)
            candidates_by_read_locus.setdefault(read_locus_key, []).append(candidate)

    for hits in candidates_by_read_locus.values():
        if not hits:
            continue
        hits.sort(key=lambda h: h.rank, reverse=True)
        top = hits[0]
        tied_hits = [top]
        for candidate in hits[1:]:
            if not _is_ambiguous_read_locus_pair(top, candidate):
                break
            tied_hits.append(candidate)

        weight = 1.0 / float(len(tied_hits))
        for hit in tied_hits:
            key = (hit.locus, hit.allele_id)
            tlen_by_key[key] = hit.tlen
            total_cov_by_key[key] = total_cov_by_key.get(key, 0.0) + (
                hit.tspan * weight
            )
            nmatch_by_key[key] = nmatch_by_key.get(key, 0.0) + (hit.nmatch * weight)
            blen_by_key[key] = blen_by_key.get(key, 0.0) + (hit.blen * weight)
            intervals_by_key.setdefault(key, []).append((hit.tstart, hit.tend))
            support_reads_by_key[key] = support_reads_by_key.get(key, 0.0) + weight

    candidates_by_locus: dict[str, list[AlleleMatch]] = {}
    for (locus, allele_id), tlen_int in tlen_by_key.items():
        total_cov = total_cov_by_key.get((locus, allele_id), 0.0)
        tlen = float(tlen_int)
        nmatch_sum = nmatch_by_key.get((locus, allele_id), 0.0)
        blen_sum = blen_by_key.get((locus, allele_id), 0.0)
        intervals = intervals_by_key.get((locus, allele_id), [])

        covered_bases = _merged_interval_length(intervals)
        coverage = min(covered_bases / tlen, 1.0) if tlen > 0 else 0.0
        identity = (nmatch_sum / blen_sum * 100.0) if blen_sum > 0 else 0.0
        support_reads = support_reads_by_key.get((locus, allele_id), 0.0)
        depth = (total_cov / covered_bases) if covered_bases > 0 else 0.0
        match = AlleleMatch(
            locus=locus,
            allele_id=allele_id,
            identity=identity,
            coverage=coverage,
            depth=depth,
            score=float(support_reads),
        )
        candidates_by_locus.setdefault(locus, []).append(match)

    candidates_by_locus_out: dict[str, list[AlleleMatch]] = {}
    for _locus, candidates in candidates_by_locus.items():
        candidates.sort(
            key=lambda m: (
                m.score,
                m.coverage,
                m.identity,
                m.depth or 0.0,
            ),
            reverse=True,
        )
        candidates_by_locus_out[candidates[0].locus] = candidates

    return candidates_by_locus_out


def _select_fastq_alleles(
    candidates_by_locus: dict[str, list[AlleleMatch]],
    reads_path: Path | tuple[Path, Path],
    alleles_fasta: Path,
) -> list[AlleleMatch]:
    selected: list[AlleleMatch] = []
    if not candidates_by_locus:
        return selected

    seqs = _load_allele_sequences(alleles_fasta)
    support = _rescore_with_unique_kmers(candidates_by_locus, reads_path, seqs)
    for locus, candidates in candidates_by_locus.items():
        ranked = sorted(
            candidates,
            key=lambda c: (
                support.get((locus, c.allele_id), 0),
                c.score,
                c.coverage,
                c.identity,
                c.depth or 0.0,
            ),
            reverse=True,
        )
        for c in ranked[:200]:
            key = (locus, c.allele_id)
            merged_score = (
                float(support[key])
                if key in support and support[key] > 0
                else float(c.score)
            )
            selected.append(
                AlleleMatch(
                    locus=c.locus,
                    allele_id=c.allele_id,
                    identity=c.identity,
                    coverage=c.coverage,
                    strand=c.strand,
                    score=merged_score,
                    depth=c.depth,
                    alignment_length=c.alignment_length,
                    sequence=c.sequence,
                    copy_count=c.copy_count,
                )
            )
    return selected


def _shortlist_candidates_by_locus(
    candidates_by_locus: dict[str, list[AlleleMatch]],
    *,
    max_candidates: int = 50,
) -> dict[str, list[AlleleMatch]]:
    shortlist: dict[str, list[AlleleMatch]] = {}
    for locus, candidates in candidates_by_locus.items():
        ranked = sorted(
            candidates,
            key=lambda c: (c.score, c.coverage, c.identity, c.depth or 0.0),
            reverse=True,
        )
        if not ranked:
            continue
        shortlist[locus] = ranked[:max_candidates]
    return shortlist


def _top_candidates_by_locus(
    candidates_by_locus: dict[str, list[AlleleMatch]],
    support: dict[tuple[str, str], float],
) -> dict[str, AlleleMatch]:
    top: dict[str, AlleleMatch] = {}
    for locus, candidates in candidates_by_locus.items():
        ranked = sorted(
            candidates,
            key=lambda c: (
                support.get((locus, c.allele_id), 0.0),
                c.score,
                c.coverage,
                c.identity,
                c.depth or 0.0,
            ),
            reverse=True,
        )
        if not ranked:
            continue
        winner = ranked[0]
        key = (locus, winner.allele_id)
        merged_score = (
            float(support[key])
            if key in support and support[key] > 0
            else float(winner.score)
        )
        top[locus] = AlleleMatch(
            locus=winner.locus,
            allele_id=winner.allele_id,
            identity=winner.identity,
            coverage=winner.coverage,
            strand=winner.strand,
            score=merged_score,
            depth=winner.depth,
            alignment_length=winner.alignment_length,
            sequence=winner.sequence,
            copy_count=winner.copy_count,
        )
    return top


def _build_targeted_validation_shortlist(
    shortlist_by_locus: dict[str, list[AlleleMatch]],
    top_by_locus: dict[str, AlleleMatch],
    seqs: dict[tuple[str, str], str],
    support: dict[tuple[str, str], float],
    *,
    total_loci: int,
) -> dict[str, list[AlleleMatch]]:
    if total_loci > _EXHAUSTIVE_TARGETED_MAX_LOCI:
        return {locus: [match] for locus, match in top_by_locus.items()}

    expanded: dict[str, list[AlleleMatch]] = {}
    for locus, top_match in top_by_locus.items():
        if top_match.coverage >= _MLST_UNCERTAIN_COVERAGE_THRESHOLD:
            expanded[locus] = [top_match]
            continue

        candidates = shortlist_by_locus.get(locus, [top_match])
        seed_candidates = candidates[:_MLST_TARGETED_SHORTLIST_SIZE]
        if not seed_candidates:
            expanded[locus] = [top_match]
            continue

        seed = top_match

        by_allele_id = {candidate.allele_id: candidate for candidate in candidates}
        expanded_candidates = list(seed_candidates)
        seen_ids = {candidate.allele_id for candidate in expanded_candidates}
        neighbor_ids = _nearest_neighbor_alleles(
            locus,
            seed.allele_id,
            seqs,
            limit=_MLST_TARGETED_NEIGHBOR_COUNT,
        )
        for allele_id in neighbor_ids:
            if allele_id in seen_ids:
                continue
            existing = by_allele_id.get(allele_id)
            if existing is not None:
                expanded_candidates.append(existing)
                seen_ids.add(allele_id)
                continue

            expanded_candidates.append(
                AlleleMatch(
                    locus=locus,
                    allele_id=allele_id,
                    identity=seed.identity if seed is not None else 0.0,
                    coverage=seed.coverage if seed is not None else 0.0,
                    depth=seed.depth if seed is not None else None,
                    score=support.get((locus, allele_id), 0.0),
                )
            )
            seen_ids.add(allele_id)
        expanded[locus] = expanded_candidates

    return expanded


def _nearest_neighbor_alleles(
    locus: str,
    seed_allele_id: str,
    seqs: dict[tuple[str, str], str],
    *,
    limit: int,
) -> list[str]:
    seed_seq = seqs.get((locus, seed_allele_id))
    if seed_seq is None:
        return []

    ranked_neighbors: list[tuple[int, tuple[int, int | str], str]] = []
    for (seq_locus, allele_id), seq in seqs.items():
        if seq_locus != locus or allele_id == seed_allele_id:
            continue
        ranked_neighbors.append(
            (
                _sequence_distance(seed_seq, seq),
                _allele_sort_key(allele_id),
                allele_id,
            )
        )

    ranked_neighbors.sort(key=lambda item: (item[0], item[1]))
    return [allele_id for _, _, allele_id in ranked_neighbors[:limit]]


def _sequence_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        return abs(len(left) - len(right)) + 10_000
    return sum(
        1
        for left_base, right_base in zip(left, right, strict=False)
        if left_base != right_base
    )


def _validate_top_candidates_with_targeted_mapping(
    reads_path: Path | tuple[Path, Path],
    shortlist_by_locus: dict[str, list[AlleleMatch]],
    seqs: dict[tuple[str, str], str],
    support: dict[tuple[str, str], float],
    *,
    threads: int,
) -> list[AlleleMatch]:
    if not shortlist_by_locus:
        return []

    with temp_dir("gmlst_mm2_targeted_") as tmp:
        targets_fasta = tmp / "targets.fasta"
        with targets_fasta.open("w") as target_out:
            written: set[tuple[str, str]] = set()
            for locus in sorted(shortlist_by_locus):
                for candidate in shortlist_by_locus[locus]:
                    key = (locus, candidate.allele_id)
                    if key in written:
                        continue
                    seq = seqs.get(key)
                    if not seq:
                        continue
                    written.add(key)
                    target_out.write(f">{locus}_{candidate.allele_id}\n{seq}\n")

        sam = tmp / "targets.sam"
        cmd = [
            "minimap2",
            "-a",
            "-x",
            _FASTQ_PRESET,
            "-t",
            str(threads),
            "--secondary=no",
            "-o",
            str(sam),
            str(targets_fasta),
        ]
        if isinstance(reads_path, tuple):
            cmd.extend([str(reads_path[0]), str(reads_path[1])])
        else:
            cmd.append(str(reads_path))
        run_cmd(cmd)

        alignment_path = sam
        if _samtools_available():
            bam = tmp / "targets.bam"
            run_cmd(
                [
                    "samtools",
                    "view",
                    "-@",
                    str(max(1, threads)),
                    "-b",
                    "-o",
                    str(bam),
                    str(sam),
                ]
            )
            sam.unlink(missing_ok=True)
            alignment_path = bam

        evidence = _collect_targeted_evidence(alignment_path, seqs)

    validated_matches: list[AlleleMatch] = []
    for locus in sorted(shortlist_by_locus):
        candidates = shortlist_by_locus[locus]
        if not candidates:
            continue

        best: AlleleMatch | None = None
        best_rank: tuple[float, int, float, float, float, int] | None = None

        for candidate in candidates:
            key = (locus, candidate.allele_id)
            stats = evidence.get(key)
            if stats is None:
                stats_identity = 0.0
                stats_coverage = 0.0
                stats_depth = 0.0
                stats_edge = 0.0
                mismatch_positions = 10_000
            else:
                (
                    stats_identity,
                    stats_coverage,
                    stats_depth,
                    stats_edge,
                    mismatch_positions,
                ) = stats

            exact_like = int(
                mismatch_positions <= 2
                and stats_coverage >= 0.95
                and stats_depth >= 5.0
            )
            rank = (
                stats_coverage,
                -mismatch_positions,
                stats_identity,
                stats_depth,
                stats_edge,
                exact_like,
            )

            if (
                best_rank is None
                or rank > best_rank
                or (
                    rank == best_rank
                    and best is not None
                    and _allele_sort_key(candidate.allele_id)
                    < _allele_sort_key(best.allele_id)
                )
            ):
                best_rank = rank

                normalized_identity = stats_identity
                normalized_coverage = stats_coverage
                if exact_like:
                    normalized_identity = 100.0
                    normalized_coverage = 1.0

                best = AlleleMatch(
                    locus=candidate.locus,
                    allele_id=candidate.allele_id,
                    identity=normalized_identity,
                    coverage=normalized_coverage,
                    strand=candidate.strand,
                    score=max(
                        candidate.score,
                        support.get((locus, candidate.allele_id), 0.0),
                    ),
                    depth=stats_depth,
                    alignment_length=candidate.alignment_length,
                    sequence=candidate.sequence,
                    copy_count=candidate.copy_count,
                )

        if best is not None:
            validated_matches.append(best)
    return validated_matches


def _collect_targeted_evidence(
    alignment_path: Path,
    seqs: dict[tuple[str, str], str],
) -> dict[tuple[str, str], tuple[float, float, float, float, int]]:
    depth_by_key: dict[tuple[str, str], list[int]] = {}
    match_by_key: dict[tuple[str, str], list[int]] = {}
    mismatch_by_key: dict[tuple[str, str], list[int]] = {}

    for key, seq in seqs.items():
        n = len(seq)
        depth_by_key[key] = [0] * n
        match_by_key[key] = [0] * n
        mismatch_by_key[key] = [0] * n

    for line in _iter_alignment_lines(alignment_path):
        if not line or line.startswith("@"):
            continue
        fields = line.rstrip().split("\t")
        if len(fields) < 11:
            continue

        flag = int(fields[1])
        if flag & 0x4:
            continue

        rname = fields[2]
        if rname == "*":
            continue

        locus, allele_id = _split_allele_id(rname)
        key = (locus, allele_id)
        ref_seq = seqs.get(key)
        if ref_seq is None:
            continue

        ref_i = int(fields[3]) - 1
        cigar = fields[5]
        read_seq = fields[9].upper()
        read_i = 0

        for length_str, op in _CIGAR_RE.findall(cigar):
            length = int(length_str)

            if op in {"M", "=", "X"}:
                for i in range(length):
                    rp = ref_i + i
                    qp = read_i + i
                    if rp < 0 or qp < 0:
                        continue
                    if rp >= len(ref_seq) or qp >= len(read_seq):
                        continue
                    depth_by_key[key][rp] += 1
                    if read_seq[qp] == ref_seq[rp]:
                        match_by_key[key][rp] += 1
                    else:
                        mismatch_by_key[key][rp] += 1
                ref_i += length
                read_i += length
                continue

            if op in {"I", "S"}:
                read_i += length
                continue

            if op in {"D", "N"}:
                ref_i += length
                continue

            if op in {"H", "P"}:
                continue

    stats: dict[tuple[str, str], tuple[float, float, float, float, int]] = {}
    for key, ref_seq in seqs.items():
        n = len(ref_seq)
        if n == 0:
            continue
        depth = depth_by_key.get(key)
        matches = match_by_key.get(key)
        mismatches = mismatch_by_key.get(key)
        if depth is None or matches is None or mismatches is None:
            continue

        covered = 0
        covered_bases = 0
        match_bases = 0
        mismatch_positions = 0
        for d, m, mm in zip(depth, matches, mismatches, strict=False):
            if d <= 0:
                continue
            covered += 1
            covered_bases += d
            match_bases += m
            if mm > m:
                mismatch_positions += 1

        coverage = covered / float(n)
        identity = (
            (match_bases / float(covered_bases) * 100.0) if covered_bases > 0 else 0.0
        )
        avg_depth = covered_bases / float(n)

        left_edge = depth[:2] if n >= 2 else depth[:1]
        right_edge = depth[-2:] if n >= 2 else depth[-1:]
        left_avg = (sum(left_edge) / float(len(left_edge))) if left_edge else 0.0
        right_avg = (sum(right_edge) / float(len(right_edge))) if right_edge else 0.0
        edge_depth = min(left_avg, right_avg)

        stats[key] = (identity, coverage, avg_depth, edge_depth, mismatch_positions)

    return stats


def _iter_alignment_lines(alignment_path: Path) -> Iterable[str]:
    if alignment_path.suffix.lower() == ".bam":
        process = subprocess.Popen(
            ["samtools", "view", "-h", str(alignment_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if process.stdout is None:
            raise RuntimeError("samtools view did not provide stdout stream")
        if process.stderr is None:
            raise RuntimeError("samtools view did not provide stderr stream")

        try:
            for line in process.stdout:
                yield line
        finally:
            process.stdout.close()

        stderr = process.stderr.read().strip()
        process.stderr.close()
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(
                "Failed to read BAM evidence with samtools view "
                f"(exit {return_code}): {stderr}"
            )
        return

    with alignment_path.open() as fh:
        for line in fh:
            yield line


@lru_cache(maxsize=4096)
def _canonical_kmer_code_set(seq: str, k: int) -> tuple[int, ...]:
    return tuple(_iter_canonical_kmer_codes(seq, k))


def _rescore_with_unique_kmers(
    candidates_by_locus: dict[str, list[AlleleMatch]],
    reads_path: Path | tuple[Path, Path],
    seqs: dict[tuple[str, str], str],
) -> dict[tuple[str, str], float]:
    k = 31
    top_n = 30
    max_reads = 60_000

    kmer_index: dict[int, set[tuple[str, str]]] = {}
    support: dict[tuple[str, str], float] = {}

    for locus, candidates in candidates_by_locus.items():
        top = candidates[:top_n]
        if len(top) < 2:
            continue
        candidate_ids = [c.allele_id for c in top]
        kmer_sets: dict[str, set[int]] = {}
        for allele_id in candidate_ids:
            seq = seqs.get((locus, allele_id), "")
            if len(seq) < k:
                continue
            kmer_sets[allele_id] = set(_canonical_kmer_code_set(seq, k))

        if len(kmer_sets) < 2:
            continue

        for allele_id in candidate_ids:
            kmers = kmer_sets.get(allele_id)
            if not kmers:
                continue
            key = (locus, allele_id)
            support.setdefault(key, 0.0)
            for kmer in kmers:
                kmer_index.setdefault(kmer, set()).add(key)

    if not kmer_index:
        return support

    for i, seq in enumerate(_iter_fastq_sequences(reads_path), start=1):
        read_support: dict[tuple[str, str], float] = {}
        kmer_index_get = kmer_index.get
        read_support_get = read_support.get
        for kmer_code in _iter_canonical_kmer_codes(seq, k):
            keys = kmer_index_get(kmer_code)
            if not keys:
                continue
            weight = 1.0 / float(len(keys))
            for key in keys:
                read_support[key] = read_support_get(key, 0.0) + weight
        for key, value in read_support.items():
            support[key] = support.get(key, 0.0) + value
        if i >= max_reads:
            break

    return support


def _rescore_with_unique_kmers_kmc(
    candidates_by_locus: dict[str, list[AlleleMatch]],
    reads_path: Path | tuple[Path, Path],
    seqs: dict[tuple[str, str], str],
    *,
    threads: int,
) -> dict[tuple[str, str], float]:
    require_tool("kmc")
    require_tool("kmc_tools")

    k = 31
    top_n = 30
    max_reads = 60_000

    kmer_index: dict[str, set[tuple[str, str]]] = {}
    support: dict[tuple[str, str], float] = {}

    for locus, candidates in candidates_by_locus.items():
        top = candidates[:top_n]
        if len(top) < 2:
            continue
        candidate_ids = [c.allele_id for c in top]
        kmer_sets: dict[str, set[str]] = {}
        for allele_id in candidate_ids:
            seq = seqs.get((locus, allele_id), "")
            if len(seq) < k:
                continue
            kmer_sets[allele_id] = set(_iter_canonical_kmers(seq, k))

        if len(kmer_sets) < 2:
            continue

        for allele_id in candidate_ids:
            kmers = kmer_sets.get(allele_id)
            if not kmers:
                continue
            key = (locus, allele_id)
            support.setdefault(key, 0.0)
            for kmer in kmers:
                kmer_index.setdefault(kmer, set()).add(key)

    if not kmer_index:
        return support

    with temp_dir("gmlst_kmc_") as tmp:
        reads_subset = tmp / "reads_subset.fastq"
        _write_fastq_head(reads_path, reads_subset, max_reads=max_reads)

        db = tmp / "reads_k31"
        run_cmd(
            [
                "kmc",
                "-k31",
                "-ci1",
                "-cs65535",
                f"-t{max(1, threads)}",
                str(reads_subset),
                str(db),
                str(tmp),
            ]
        )

        dump_path = tmp / "reads_k31.dump"
        run_cmd(
            [
                "kmc_tools",
                "transform",
                str(db),
                "dump",
                "-s",
                str(dump_path),
            ]
        )

        with dump_path.open() as fh:
            for line in fh:
                parts = line.strip().split()
                if len(parts) != 2:
                    continue
                kmer, count_str = parts
                keys = kmer_index.get(kmer)
                if not keys:
                    continue
                count = float(int(count_str))
                weight = count / float(len(keys))
                for key in keys:
                    support[key] = support.get(key, 0.0) + weight

    return support


def _write_fastq_head(
    reads_path: Path | tuple[Path, Path], out_path: Path, *, max_reads: int
) -> None:
    copied = 0
    paths = reads_path if isinstance(reads_path, tuple) else (reads_path,)
    with out_path.open("w") as out:
        for path in paths:
            opener = gzip.open if path.suffix.lower() == ".gz" else Path.open
            with opener(path, "rt") as src:
                while copied < max_reads:
                    header = src.readline()
                    if not header:
                        break
                    sequence = src.readline()
                    plus = src.readline()
                    quality = src.readline()
                    if not (sequence and plus and quality):
                        break
                    out.write(header)
                    out.write(sequence)
                    out.write(plus)
                    out.write(quality)
                    copied += 1
            if copied >= max_reads:
                break


def _kmc_available() -> bool:
    try:
        require_tool("kmc")
        require_tool("kmc_tools")
    except RuntimeError:
        return False
    return True


def _samtools_available() -> bool:
    return shutil.which("samtools") is not None


def _load_allele_sequences(path: Path) -> dict[tuple[str, str], str]:
    seqs: dict[tuple[str, str], str] = {}
    if not path.exists():
        return seqs

    for name, sequence in iter_fasta_records(path):
        locus, allele_id = _split_allele_id(name)
        seqs[(locus, allele_id)] = sequence
    return seqs


def _iter_fastq_sequences(path: Path | tuple[Path, Path]) -> Iterable[str]:
    paths = path if isinstance(path, tuple) else (path,)
    for one in paths:
        opener = gzip.open if one.suffix.lower() == ".gz" else Path.open
        with opener(one, "rt") as fh:
            for line_no, line in enumerate(fh, start=1):
                if line_no % 4 == 2:
                    yield line.strip().upper()


def _iter_canonical_kmers(seq: str, k: int) -> Iterable[str]:
    if len(seq) < k:
        return
    for i in range(len(seq) - k + 1):
        kmer = seq[i : i + k]
        if "N" in kmer:
            continue
        rc = _revcomp(kmer)
        yield kmer if kmer <= rc else rc


def _iter_canonical_kmer_codes(seq: str, k: int) -> Iterable[int]:
    if len(seq) < k:
        return

    seq_bytes = seq.encode("ascii")
    mask = (1 << (2 * k)) - 1
    rc_shift = 2 * (k - 1)
    fwd_code = 0
    rc_code = 0
    valid = 0

    for base in seq_bytes:
        bits = _BASE_BITS.get(base)
        if bits is None:
            fwd_code = 0
            rc_code = 0
            valid = 0
            continue

        fwd_code = ((fwd_code << 2) | bits) & mask
        rc_code = (rc_code >> 2) | ((bits ^ 0b11) << rc_shift)
        valid += 1

        if valid >= k:
            yield fwd_code if fwd_code <= rc_code else rc_code


def _revcomp(seq: str) -> str:
    return seq.translate(_REVCOMP_TABLE)[::-1]


@dataclass(frozen=True)
class _ReadHit:
    locus: str
    allele_id: str
    tlen: int
    tstart: int
    tend: int
    nmatch: int
    blen: int
    tspan: int
    identity: float
    rank: tuple[float, float, float, float, float]


def _is_better_read_hit(candidate: _ReadHit, existing: _ReadHit) -> bool:
    if candidate.rank > existing.rank:
        return True
    if candidate.rank < existing.rank:
        return False
    return _allele_sort_key(candidate.allele_id) < _allele_sort_key(existing.allele_id)


def _is_ambiguous_read_locus_pair(best: _ReadHit, second: _ReadHit) -> bool:
    identity_close = abs(best.identity - second.identity) < 0.01
    nmatch_close = abs(best.nmatch - second.nmatch) <= 1
    blen_close = abs(best.blen - second.blen) <= 1
    return identity_close and nmatch_close and blen_close


def _allele_sort_key(allele_id: str) -> tuple[int, int | str]:
    if allele_id.isdigit():
        return (0, int(allele_id))
    return (1, allele_id)


def _merged_interval_length(intervals: list[tuple[int, int]]) -> float:
    if not intervals:
        return 0.0

    merged = sorted(intervals)
    start, end = merged[0]
    total = 0
    for cur_start, cur_end in merged[1:]:
        if cur_start <= end:
            if cur_end > end:
                end = cur_end
            continue
        total += end - start
        start, end = cur_start, cur_end
    total += end - start
    return float(total)
