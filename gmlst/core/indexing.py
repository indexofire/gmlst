from __future__ import annotations

import hashlib
from contextlib import suppress
from pathlib import Path

from gmlst.metadata_io import read_json_metadata, write_json_metadata


def index_is_empty_impl(index_dir: Path) -> bool:
    if not index_dir.exists():
        return True
    return not any(index_dir.iterdir())


def find_index_impl(index_dir: Path, backend: str) -> Path | None:
    patterns = {
        "blastn": "*.nhr",
        "minimap2": "*.mmi",
        "nucmer": "alleles.fasta",
        "kma": "*.name",
    }
    pattern = patterns.get(backend, "*")
    candidates = list(index_dir.glob(pattern))
    if candidates:
        if backend == "blastn":
            return candidates[0].with_suffix("")
        if backend == "nucmer":
            return candidates[0]
        return index_dir
    return None


def purge_backend_index_impl(*, index_dir: Path, backend: str) -> None:
    patterns: dict[str, list[str]] = {
        "blastn": ["alleles.fasta", "*.n*"],
        "minimap2": ["alleles.fasta", "*.mmi"],
        "kma": ["alleles.fasta", "kma_db*"],
        "nucmer": ["alleles.fasta"],
    }
    for pattern in patterns.get(backend, []):
        for path in index_dir.glob(pattern):
            if path.is_file():
                with suppress(FileNotFoundError):
                    # race: file may be deleted between glob and unlink
                    path.unlink()


def is_index_stale_impl(
    *,
    backend: str,
    index_dir: Path,
    allele_fastas: list[Path],
) -> bool:
    if not allele_fastas:
        return False

    latest_allele_mtime = max(path.stat().st_mtime for path in allele_fastas)

    artifact_patterns: dict[str, list[str]] = {
        "blastn": ["*.nhr"],
        "minimap2": ["alleles.fasta", "*.mmi"],
        "kma": [
            "alleles.fasta",
            "kma_db.name",
            "kma_db.length.b",
            "kma_db.seq.b",
            "kma_db.comp.b",
        ],
        "nucmer": ["alleles.fasta"],
    }
    patterns = artifact_patterns.get(backend, ["*"])

    artifacts: list[Path] = []
    for pattern in patterns:
        artifacts.extend(index_dir.glob(pattern))
    if not artifacts:
        return True

    if backend == "kma":
        required = [
            index_dir / "kma_db.name",
            index_dir / "kma_db.length.b",
            index_dir / "kma_db.seq.b",
            index_dir / "kma_db.comp.b",
        ]
        if any((not path.exists()) or path.stat().st_size == 0 for path in required):
            return True

    merged = index_dir / "alleles.fasta"
    if merged.exists():
        expected_merged_size = sum(path.stat().st_size for path in allele_fastas)
        if merged.stat().st_size != expected_merged_size:
            return True

    latest_index_mtime = max(path.stat().st_mtime for path in artifacts)
    return latest_index_mtime < latest_allele_mtime


def ensure_full_index_impl(
    *,
    aligner,
    backend: str,
    scheme_name: str,
    allele_fastas: list[Path],
    index_dir: Path,
    force_reindex: bool,
    logger,
    index_is_empty_fn,
    purge_backend_index_fn,
    find_index_fn,
    is_index_stale_fn,
) -> Path:
    if force_reindex or index_is_empty_fn(index_dir):
        if force_reindex:
            purge_backend_index_fn(index_dir=index_dir, backend=backend)
        logger.info("Building '%s' index for scheme '%s' …", backend, scheme_name)
        return aligner.index(allele_fastas, index_dir)

    index_path = find_index_fn(index_dir, backend)
    if index_path is not None and not is_index_stale_fn(
        backend=backend,
        index_dir=index_dir,
        allele_fastas=allele_fastas,
    ):
        return index_path
    if index_path is not None:
        logger.info(
            "Rebuilding stale '%s' index for scheme '%s' …", backend, scheme_name
        )
        purge_backend_index_fn(index_dir=index_dir, backend=backend)
    return aligner.index(allele_fastas, index_dir)


def representative_fingerprint_impl(
    representatives: dict[tuple[str, str], str],
    *,
    allele_order_key_fn,
    hasher,
) -> str:
    for (locus, allele_id), sequence in sorted(
        representatives.items(),
        key=lambda item: (item[0][0], allele_order_key_fn(item[0][1])),
    ):
        hasher.update(locus.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(allele_id.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(sequence.encode("ascii"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def load_or_build_minimap2_representative_index_impl(
    *,
    aligner,
    index_dir: Path,
    representatives: dict[tuple[str, str], str],
    force_reindex: bool,
    representative_fingerprint_fn,
    is_index_stale_fn,
    purge_backend_index_fn,
    allele_order_key_fn,
    logger,
) -> Path:
    index_dir.mkdir(parents=True, exist_ok=True)
    source_fasta = index_dir / "representatives.fasta"
    meta_file = index_dir / "representative_meta.json"
    fingerprint = representative_fingerprint_fn(
        representatives,
        allele_order_key_fn=allele_order_key_fn,
        hasher=hashlib.sha256(),
    )
    needs_rebuild = force_reindex
    if not needs_rebuild:
        if not source_fasta.exists() or not meta_file.exists():
            needs_rebuild = True
        else:
            cached_meta = read_json_metadata(meta_file, default={})
            needs_rebuild = cached_meta.get("fingerprint") != fingerprint
            if not needs_rebuild:
                needs_rebuild = is_index_stale_fn(
                    index_dir=index_dir,
                    backend="minimap2",
                    allele_fastas=[source_fasta],
                )

    if needs_rebuild:
        with source_fasta.open("w") as out:
            for (locus, allele_id), sequence in sorted(
                representatives.items(),
                key=lambda item: (item[0][0], allele_order_key_fn(item[0][1])),
            ):
                out.write(f">{locus}_{allele_id}\n{sequence}\n")
        write_json_metadata(meta_file, {"fingerprint": fingerprint})
        purge_backend_index_fn(index_dir=index_dir, backend="minimap2")
        aligner.index([source_fasta], index_dir)
        logger.info(
            "Built persistent minimap2 representative index at %s",
            index_dir,
        )
    else:
        logger.info(
            "Reusing persistent minimap2 representative index from %s",
            index_dir,
        )
    return index_dir
