from __future__ import annotations

from pathlib import Path

from gmlst.fasta_io import iter_fasta_records, iter_fasta_sequences


def split_allele_header_impl(header: str) -> tuple[str, str]:
    if "_" in header:
        locus, allele_id = header.rsplit("_", 1)
        return locus, allele_id
    return header, ""


def iter_fasta_sequences_impl(path: Path):
    yield from iter_fasta_sequences(path)


def load_scheme_allele_sequences_impl(
    allele_files: dict[str, Path],
    *,
    split_allele_header_fn,
) -> dict[str, dict[str, str]]:
    sequences: dict[str, dict[str, str]] = {}
    for locus, path in allele_files.items():
        locus_seqs: dict[str, str] = {}
        for header, sequence in iter_fasta_records(path):
            _, allele_id = split_allele_header_fn(header)
            locus_seqs[allele_id] = sequence
        sequences[locus] = locus_seqs
    return sequences


def load_representative_allele_sequences_impl(
    allele_files: dict[str, Path],
    *,
    split_allele_header_fn,
    allele_order_key_fn,
) -> dict[tuple[str, str], str]:
    representatives: dict[tuple[str, str], str] = {}
    for locus, path in allele_files.items():
        best_allele_id: str | None = None
        best_sequence: str | None = None
        for header, sequence in iter_fasta_records(path):
            _, allele_id = split_allele_header_fn(header)
            if best_allele_id is None or allele_order_key_fn(
                allele_id
            ) < allele_order_key_fn(best_allele_id):
                best_allele_id = allele_id
                best_sequence = sequence
        if best_allele_id is not None and best_sequence is not None:
            representatives[(locus, best_allele_id)] = best_sequence
    return representatives


def representatives_from_nested_alleles_impl(
    allele_sequences: dict[str, dict[str, str]],
    *,
    allele_order_key_fn,
) -> dict[tuple[str, str], str]:
    representatives: dict[tuple[str, str], str] = {}
    for locus, alleles in allele_sequences.items():
        best_allele_id: str | None = None
        best_sequence: str | None = None
        for allele_id, sequence in alleles.items():
            if best_allele_id is None or allele_order_key_fn(
                allele_id
            ) < allele_order_key_fn(best_allele_id):
                best_allele_id = allele_id
                best_sequence = sequence
        if best_allele_id is not None and best_sequence is not None:
            representatives[(locus, best_allele_id)] = best_sequence
    return representatives


def write_candidate_fastas_impl(
    allele_sequences: dict[str, dict[str, str]],
    candidates: dict[str, list[tuple[str, float]]],
    out_dir: Path,
) -> list[Path]:
    paths: list[Path] = []
    for locus, ranked in candidates.items():
        locus_alleles = allele_sequences.get(locus)
        if not locus_alleles:
            continue
        lines: list[str] = []
        for allele_id, _score in ranked:
            seq = locus_alleles.get(allele_id)
            if not seq:
                continue
            lines.append(f">{locus}_{allele_id}")
            lines.append(seq)
        if not lines:
            continue
        path = out_dir / f"{locus}.tfa"
        path.write_text("\n".join(lines) + "\n")
        paths.append(path)
    return paths
