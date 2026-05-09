from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gmlst.metadata_io import read_json_metadata, write_json_metadata


def load_or_build_exact_hash_indexes_impl(
    *,
    allele_files: dict[str, Path],
    allele_sequences: dict[str, dict[str, str]],
    include_protein: bool,
    scheme_precomputed_dir_fn,
    allele_files_fingerprint_fn,
    build_allele_hash_index_fn,
    build_allele_protein_hash_index_fn,
    logger,
) -> tuple[
    dict[str, list[tuple[str, str]]],
    dict[str, list[tuple[str, str]]] | None,
]:
    precomputed_dir = scheme_precomputed_dir_fn(allele_files)
    meta_file = precomputed_dir / "exact_hash_meta.json"
    dna_file = precomputed_dir / "dna_hash_index.json"
    protein_file = precomputed_dir / "protein_hash_index.json"
    legacy_dna_file = precomputed_dir / "dna_hash_index.pkl"
    legacy_protein_file = precomputed_dir / "protein_hash_index.pkl"
    current_fingerprint = allele_files_fingerprint_fn(allele_files)

    if (
        meta_file.exists()
        and dna_file.exists()
        and ((not include_protein) or protein_file.exists())
    ):
        try:
            cached_meta = read_json_metadata(meta_file, default={})
            if cached_meta.get("fingerprint") == current_fingerprint:
                dna_index = {
                    str(digest): [
                        (str(locus), str(allele_id)) for locus, allele_id in hits
                    ]
                    for digest, hits in json.loads(dna_file.read_text()).items()
                }
                protein_index = (
                    {
                        str(digest): [
                            (str(locus), str(allele_id)) for locus, allele_id in hits
                        ]
                        for digest, hits in json.loads(protein_file.read_text()).items()
                    }
                    if include_protein and protein_file.exists()
                    else None
                )
                logger.info(
                    "Loaded precomputed exact-hash index from %s",
                    precomputed_dir,
                )
                return dna_index, protein_index
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            logger.warning(
                "Failed to load precomputed index from %s, rebuilding",
                precomputed_dir,
                exc_info=True,
            )

    dna_index = build_allele_hash_index_fn(allele_sequences)
    protein_index = (
        build_allele_protein_hash_index_fn(allele_sequences)
        if include_protein
        else None
    )
    dna_json = json.dumps(dna_index)
    dna_file.write_text(dna_json)
    legacy_dna_file.write_text(dna_json)
    if protein_index is not None:
        protein_json = json.dumps(protein_index)
        protein_file.write_text(protein_json)
        legacy_protein_file.write_text(protein_json)
    write_json_metadata(meta_file, {"fingerprint": current_fingerprint})
    logger.info(
        "Wrote precomputed exact-hash index to %s",
        precomputed_dir,
    )
    return dna_index, protein_index


def scheme_precomputed_dir_impl(allele_files: dict[str, Path]) -> Path:
    first_file = next(iter(allele_files.values()))
    precomputed_dir = first_file.parent / "pre_computed"
    precomputed_dir.mkdir(parents=True, exist_ok=True)
    return precomputed_dir


def allele_files_fingerprint_impl(allele_files: dict[str, Path]) -> str:
    hasher = hashlib.sha256()
    for locus, path in sorted(allele_files.items()):
        stat = path.stat()
        hasher.update(locus.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(stat.st_size).encode("ascii"))
        hasher.update(b"\0")
        hasher.update(str(stat.st_mtime_ns).encode("ascii"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def build_allele_hash_index_impl(
    allele_sequences: dict[str, dict[str, str]],
) -> dict[str, list[tuple[str, str]]]:
    index: dict[str, list[tuple[str, str]]] = {}
    for locus, alleles in allele_sequences.items():
        for allele_id, sequence in alleles.items():
            digest = hashlib.sha256(sequence.upper().encode("ascii")).hexdigest()
            index.setdefault(digest, []).append((locus, allele_id))
    return index


def build_allele_protein_hash_index_impl(
    allele_sequences: dict[str, dict[str, str]],
    *,
    translate_cds_to_protein_fn,
) -> dict[str, list[tuple[str, str]]]:
    index: dict[str, list[tuple[str, str]]] = {}
    for locus, alleles in allele_sequences.items():
        for allele_id, sequence in alleles.items():
            protein = translate_cds_to_protein_fn(sequence)
            if not protein:
                continue
            digest = hashlib.sha256(protein.encode("ascii")).hexdigest()
            index.setdefault(digest, []).append((locus, allele_id))
    return index


def resolve_exact_cds_matches_impl(
    sample_path: Path,
    hash_index: dict[str, list[tuple[str, str]]],
    *,
    protein_hash_index: dict[str, list[tuple[str, str]]] | None = None,
    sample_cache_root: Path | None = None,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
    load_or_build_sample_cds_hashes_fn,
    allele_match_cls,
) -> dict[str, object]:
    hashed_sequences = load_or_build_sample_cds_hashes_fn(
        sample_path,
        cache_root=sample_cache_root,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
    )

    by_locus: dict[str, set[str]] = {}
    by_locus_protein: dict[str, set[str]] = {}
    for digest, protein_digest in hashed_sequences:
        hits = hash_index.get(digest)
        if not hits:
            hits = []
        for locus, allele_id in hits:
            by_locus.setdefault(locus, set()).add(allele_id)
        if protein_hash_index and protein_digest:
            protein_hits = protein_hash_index.get(protein_digest, [])
            for locus, allele_id in protein_hits:
                by_locus_protein.setdefault(locus, set()).add(allele_id)

    resolved: dict[str, object] = {}
    for locus, allele_ids in by_locus.items():
        if len(allele_ids) != 1:
            continue
        allele_id = next(iter(allele_ids))
        resolved[locus] = allele_match_cls(
            locus=locus,
            allele_id=allele_id,
            identity=100.0,
            coverage=1.0,
            score=100.0,
        )
    for locus, allele_ids in by_locus_protein.items():
        if locus in resolved or len(allele_ids) != 1:
            continue
        allele_id = next(iter(allele_ids))
        resolved[locus] = allele_match_cls(
            locus=locus,
            allele_id=allele_id,
            identity=99.0,
            coverage=1.0,
            score=99.0,
        )
    return resolved


def predict_cds_sequences_impl(
    sample_path: Path,
    *,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
    predict_cds_genes_fn,
) -> list[str]:
    predicted = predict_cds_genes_fn(
        sample_path,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
    )
    return [gene.sequence.upper() for gene in predicted]


def load_or_build_sample_cds_hashes_impl(
    sample_path: Path,
    *,
    cache_root: Path | None,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
    load_or_build_sample_cds_data_fn,
) -> list[tuple[str, str | None]]:
    records, _sequences = load_or_build_sample_cds_data_fn(
        sample_path,
        cache_root=cache_root,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
    )
    return records


def load_or_build_sample_cds_sequences_impl(
    sample_path: Path,
    *,
    cache_root: Path | None,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
    load_or_build_sample_cds_data_fn,
) -> list[str]:
    _records, sequences = load_or_build_sample_cds_data_fn(
        sample_path,
        cache_root=cache_root,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
    )
    return sequences


def load_or_build_sample_cds_data_impl(
    sample_path: Path,
    *,
    cache_root: Path | None,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
    predict_cds_sequences_fn,
    hash_cds_and_protein_fn,
    sample_cds_cache_config_fn,
    logger,
) -> tuple[list[tuple[str, str | None]], list[str]]:
    if cache_root is None:
        sequences = predict_cds_sequences_fn(
            sample_path,
            cds_prediction_mode=cds_prediction_mode,
            cds_training_file=cds_training_file,
            cds_closed_ends=cds_closed_ends,
        )
        return [hash_cds_and_protein_fn(sequence) for sequence in sequences], sequences

    sample_cache_dir = cache_root / "_sample_cds_hashes"
    sample_cache_dir.mkdir(parents=True, exist_ok=True)
    sample_key = hashlib.sha256(str(sample_path.resolve()).encode("utf-8")).hexdigest()
    cache_file = sample_cache_dir / f"{sample_key}.json"
    stat = sample_path.stat()
    fingerprint = f"{stat.st_size}:{stat.st_mtime_ns}"
    cds_config = sample_cds_cache_config_fn(
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
    )

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if (
                cached.get("fingerprint") == fingerprint
                and cached.get("cds_config") == cds_config
            ):
                records = cached.get("records", [])
                sequences = cached.get("sequences", [])
                logger.info("Loaded sample CDS hash cache for %s", sample_path.name)
                normalized_records = [
                    (str(record[0]), (None if record[1] is None else str(record[1])))
                    for record in records
                ]
                normalized_sequences = [str(sequence).upper() for sequence in sequences]
                if len(normalized_sequences) == len(normalized_records):
                    return normalized_records, normalized_sequences
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            logger.warning(
                "Failed to load precomputed index from %s, rebuilding",
                cache_file,
                exc_info=True,
            )

    sequences = predict_cds_sequences_fn(
        sample_path,
        cds_prediction_mode=cds_prediction_mode,
        cds_training_file=cds_training_file,
        cds_closed_ends=cds_closed_ends,
    )
    records = [hash_cds_and_protein_fn(sequence) for sequence in sequences]
    cache_file.write_text(
        json.dumps(
            {
                "fingerprint": fingerprint,
                "cds_config": cds_config,
                "records": records,
                "sequences": sequences,
            }
        )
    )
    logger.info("Wrote sample CDS hash cache for %s", sample_path.name)
    return records, sequences


def sample_cds_cache_config_impl(
    *,
    cds_prediction_mode: str,
    cds_training_file: Path | None,
    cds_closed_ends: bool,
) -> str:
    training_marker = ""
    if cds_training_file is not None:
        if cds_training_file.exists() and cds_training_file.is_file():
            stat = cds_training_file.stat()
            training_marker = (
                f"{cds_training_file.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
            )
        else:
            training_marker = str(cds_training_file)
    return f"{cds_prediction_mode}|{int(cds_closed_ends)}|{training_marker}"


def hash_cds_and_protein_impl(
    sequence: str,
    *,
    translate_cds_to_protein_fn,
) -> tuple[str, str | None]:
    dna = sequence.upper()
    dna_digest = hashlib.sha256(dna.encode("ascii")).hexdigest()
    protein = translate_cds_to_protein_fn(dna)
    if not protein:
        return dna_digest, None
    return dna_digest, hashlib.sha256(protein.encode("ascii")).hexdigest()


def translate_cds_to_protein_impl(sequence: str) -> str:
    dna = sequence.upper()
    usable = len(dna) - (len(dna) % 3)
    if usable < 3:
        return ""
    protein_chars: list[str] = []
    for i in range(0, usable, 3):
        aa = CODON_TABLE.get(dna[i : i + 3], "X")
        if aa == "*":
            break
        protein_chars.append(aa)
    return "".join(protein_chars)


CODON_TABLE = {
    "TTT": "F",
    "TTC": "F",
    "TTA": "L",
    "TTG": "L",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "TAT": "Y",
    "TAC": "Y",
    "TAA": "*",
    "TAG": "*",
    "TGT": "C",
    "TGC": "C",
    "TGA": "*",
    "TGG": "W",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "CAT": "H",
    "CAC": "H",
    "CAA": "Q",
    "CAG": "Q",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "ATT": "I",
    "ATC": "I",
    "ATA": "I",
    "ATG": "M",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "AAT": "N",
    "AAC": "N",
    "AAA": "K",
    "AAG": "K",
    "AGT": "S",
    "AGC": "S",
    "AGA": "R",
    "AGG": "R",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
}
