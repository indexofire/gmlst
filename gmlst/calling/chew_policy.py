"""chewBBACA-compatible classification of locus calls.

Converts per-locus :class:`~gmlst.calling.allele.LocusCall` results into
chewBBACA-style category codes so cgMLST output matches the familiar
schema-genome caller vocabulary:

* ``NIPHEM`` / ``NIPH`` — multiple exact / non-exact hits for the locus
* ``LNF`` — locus not found
* ``LOTSC`` — allele landed on a contig shorter than the allele itself
* ``PLOT5`` / ``PLOT3`` — allele truncated at a contig tip
* ``ASM`` / ``ALM`` — allele much smaller / larger than the locus mode size
* ``<allele_id>`` — exact match; ``INF-<allele_id>`` / ``INF`` — inferred

An optional CDS gate checks that the called allele is among the
pyrodigal-predicted CDSs; failing calls fall back to structural checks
(contig position, size, sequence containment) before being demoted to
``LNF``.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from gmlst.calling.allele import LocusCall
from gmlst.fasta_io import iter_fasta_records, iter_fasta_sequences


def classify_chew_style_calls(
    *,
    locus_calls: dict[str, LocusCall],
    allele_files: dict[str, Path],
    size_threshold: float = 0.2,
    cds_dna_hashes: set[str] | None = None,
    cds_sequences: list[str] | None = None,
    enforce_cds_gate: bool = True,
) -> dict[str, str]:
    """Classify every locus call into a chewBBACA-style category code.

    Classification precedence per locus: multiple hits → ``NIPHEM``
    (exact best hit) or ``NIPH``; missing → ``LNF``. Exact calls with an
    allele id return the allele id. Contig-position defects yield
    ``LOTSC`` / ``PLOT5`` / ``PLOT3``; size outliers yield ``ASM`` /
    ``ALM``; closest/novel calls yield ``INF-<allele_id>`` (or ``INF``).
    When the CDS gate is enforced and the called allele is absent from
    the predicted CDS set, only structural defects or the sequence
    containment fallback can still yield ``INF-*`` — otherwise the locus
    is demoted to ``LNF``.

    Parameters
    ----------
    locus_calls:
        Per-locus calls produced by the calling pipeline.
    allele_files:
        ``{locus: allele FASTA}`` used for length statistics, hashes,
        and sequences.
    size_threshold:
        Relative deviation from the locus mode allele length that
        triggers ``ASM`` / ``ALM`` (default 0.2 = 20%).
    cds_dna_hashes:
        SHA-256 hashes of predicted CDS DNA sequences (gate evidence).
    cds_sequences:
        Raw predicted CDS sequences for the containment fallback.
    enforce_cds_gate:
        Whether calls failing the CDS gate are demoted.

    Returns
    -------
    dict[str, str]
        ``{locus: classification}`` for every input locus call.
    """
    stats = _load_locus_length_stats(allele_files)
    allele_hashes = _load_allele_data(allele_files, as_hash=True)
    allele_sequences = _load_allele_data(allele_files)
    classified: dict[str, str] = {}
    for locus, call in locus_calls.items():
        classified[locus] = _classify_locus(
            locus=locus,
            call=call,
            stats=stats,
            size_threshold=size_threshold,
            allele_hashes=allele_hashes,
            cds_dna_hashes=cds_dna_hashes,
            allele_sequences=allele_sequences,
            cds_sequences=cds_sequences,
            enforce_cds_gate=enforce_cds_gate,
        )
    return classified


def _classify_locus(
    *,
    locus: str,
    call: LocusCall,
    stats: dict[str, tuple[int, int, int]],
    size_threshold: float,
    allele_hashes: dict[tuple[str, str], str],
    cds_dna_hashes: set[str] | None,
    allele_sequences: dict[tuple[str, str], str],
    cds_sequences: list[str] | None,
    enforce_cds_gate: bool,
) -> str:
    if call.multiple_hits:
        return "NIPHEM" if call.call_type == "exact" else "NIPH"
    if call.call_type == "missing":
        return "LNF"

    if (
        enforce_cds_gate
        and cds_dna_hashes is not None
        and not _passes_cds_gate(
            locus=locus,
            call=call,
            allele_hashes=allele_hashes,
            cds_dna_hashes=cds_dna_hashes,
        )
    ):
        pos_class = _contig_position_classification(call)
        if pos_class is not None:
            return pos_class

        size_class = _size_classification(
            call=call,
            locus=locus,
            stats=stats,
            size_threshold=size_threshold,
        )
        if size_class is not None:
            return size_class

        if _passes_cds_sequence_fallback(
            locus=locus,
            call=call,
            allele_sequences=allele_sequences,
            cds_sequences=cds_sequences,
        ):
            return f"INF-{call.allele_id}" if call.allele_id else "INF"

        return "LNF"

    if call.call_type == "exact" and call.allele_id:
        return call.allele_id

    pos_class = _contig_position_classification(call)
    if pos_class is not None:
        return pos_class

    size_class = _size_classification(
        call=call,
        locus=locus,
        stats=stats,
        size_threshold=size_threshold,
    )
    if size_class is not None:
        return size_class

    if call.call_type in {"closest", "novel"}:
        return f"INF-{call.allele_id}" if call.allele_id else "INF"
    if call.call_type == "partial":
        return "LNF"
    if call.allele_id:
        return call.allele_id
    return "LNF"


def _contig_position_classification(call: LocusCall) -> str | None:
    match = call.best_match
    if match is None:
        return None

    contig_len = match.query_contig_length
    contig_start = match.query_start
    contig_end = match.query_end
    allele_len = match.allele_length
    allele_start = match.allele_start
    allele_end = match.allele_end

    if (
        contig_len is None
        or contig_start is None
        or contig_end is None
        or allele_len is None
        or allele_start is None
        or allele_end is None
    ):
        return None

    if contig_len < allele_len:
        return "LOTSC"

    contig_left_rest = contig_start
    contig_right_rest = contig_len - contig_end
    allele_left_rest = allele_start
    allele_right_rest = allele_len - allele_end

    strand = match.strand
    if strand == "+":
        if contig_left_rest < allele_left_rest:
            return "PLOT5"
        if contig_right_rest < allele_right_rest:
            return "PLOT3"
    else:
        if contig_right_rest < allele_left_rest:
            return "PLOT5"
        if contig_left_rest < allele_right_rest:
            return "PLOT3"
    return None


def _size_classification(
    *,
    call: LocusCall,
    locus: str,
    stats: dict[str, tuple[int, int, int]],
    size_threshold: float,
) -> str | None:
    if locus not in stats:
        return None

    seq_len: int | None = None
    match = call.best_match
    if match is not None and isinstance(match.allele_length, int):
        seq_len = match.allele_length
    elif call.novel_sequence:
        seq_len = len(call.novel_sequence)
    if seq_len is None:
        return None

    mode_len = stats[locus][1]
    low = mode_len - int(mode_len * size_threshold)
    high = mode_len + int(mode_len * size_threshold)
    if seq_len < low:
        return "ASM"
    if seq_len > high:
        return "ALM"
    return None


def _load_locus_length_stats(
    allele_files: dict[str, Path],
) -> dict[str, tuple[int, int, int]]:
    stats: dict[str, tuple[int, int, int]] = {}
    for locus, allele_file in allele_files.items():
        lengths = _read_fasta_lengths(allele_file)
        if not lengths:
            continue
        stats[locus] = (min(lengths), _mode(lengths), max(lengths))
    return stats


def _resolve_allele_id(locus: str, header: str) -> str:
    """Strip the locus prefix from a FASTA header if present."""
    if "_" in header:
        maybe_locus, maybe_id = header.rsplit("_", 1)
        if maybe_locus == locus:
            return maybe_id
    return header


def _load_allele_data(
    allele_files: dict[str, Path],
    *,
    as_hash: bool = False,
) -> dict[tuple[str, str], str]:
    """Load allele sequences or hashes from FASTA files."""
    result: dict[tuple[str, str], str] = {}
    for locus, allele_file in allele_files.items():
        for header, sequence in iter_fasta_records(allele_file):
            allele_id = _resolve_allele_id(locus, header)
            if as_hash:
                result[(locus, allele_id)] = hashlib.sha256(
                    sequence.upper().encode("ascii")
                ).hexdigest()
            else:
                result[(locus, allele_id)] = sequence.upper()
    return result


def _passes_cds_gate(
    *,
    locus: str,
    call: LocusCall,
    allele_hashes: dict[tuple[str, str], str],
    cds_dna_hashes: set[str],
) -> bool:
    if call.allele_id is None:
        return False
    allele_hash = allele_hashes.get((locus, call.allele_id))
    if allele_hash is None:
        return False
    return allele_hash in cds_dna_hashes


def _passes_cds_sequence_fallback(
    *,
    locus: str,
    call: LocusCall,
    allele_sequences: dict[tuple[str, str], str],
    cds_sequences: list[str] | None,
) -> bool:
    if cds_sequences is None or call.allele_id is None:
        return False
    allele_seq = allele_sequences.get((locus, call.allele_id))
    if not allele_seq:
        return False
    for cds_seq in cds_sequences:
        if allele_seq in cds_seq or cds_seq in allele_seq:
            return True
    return False


def _read_fasta_lengths(path: Path) -> list[int]:
    return [len(sequence) for sequence in iter_fasta_sequences(path)]


def _mode(values: list[int]) -> int:
    counts = Counter(values)
    best = max(counts.items(), key=lambda item: (item[1], -item[0]))
    return best[0]
