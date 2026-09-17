"""Tests for process-level scheme load memoization."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from gmlst.core import exact_hash
from gmlst.core.sequences import (
    load_scheme_allele_sequences_impl,
    split_allele_header_impl,
)
from gmlst.database.schema import Scheme
from gmlst.scheme_load_cache import _MAX_MEMO_ENTRIES, clear_scheme_load_memos

logger = logging.getLogger("test_scheme_load_memos")

allele_logger = logging.getLogger("gmlst.core.adapters_exact_hash")


def _bump_mtime(path: Path) -> None:
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns + 1, stat.st_mtime_ns + 1))


def _write_scheme(dir_path: Path, tag: str) -> dict[str, Path]:
    dir_path.mkdir(parents=True, exist_ok=True)
    locus_file = dir_path / f"{tag}A.tfa"
    locus_file.write_text(f">{tag}A_1\nATGGCC\n>{tag}A_2\nATGAAA\n")
    return {f"{tag}A": locus_file}


def _load_sequences(allele_files: dict[str, Path]) -> dict[str, dict[str, str]]:
    return load_scheme_allele_sequences_impl(
        allele_files, split_allele_header_fn=split_allele_header_impl
    )


def _load_index(
    allele_files: dict[str, Path], allele_sequences: dict[str, dict[str, str]]
) -> dict[str, list[tuple[str, str]]]:
    return exact_hash.load_or_build_exact_hash_indexes_impl(
        allele_files=allele_files,
        allele_sequences=allele_sequences,
        scheme_precomputed_dir_fn=exact_hash.scheme_precomputed_dir_impl,
        allele_files_fingerprint_fn=exact_hash.allele_files_fingerprint_impl,
        build_allele_hash_index_fn=exact_hash.build_allele_hash_index_impl,
        logger=allele_logger,
    )


def test_allele_sequences_memo_returns_same_object(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    allele_files = _write_scheme(tmp_path, "x")
    first = _load_sequences(allele_files)
    second = _load_sequences(allele_files)
    assert second is first
    assert first == {"xA": {"1": "ATGGCC", "2": "ATGAAA"}}


def test_allele_sequences_memo_respects_max_per_locus(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    allele_files = _write_scheme(tmp_path, "x")
    capped = load_scheme_allele_sequences_impl(
        allele_files, split_allele_header_fn=split_allele_header_impl, max_per_locus=1
    )
    assert capped == {"xA": {"1": "ATGGCC"}}


def test_allele_sequences_memo_invalidates_on_file_change(
    tmp_path: Path,
) -> None:
    clear_scheme_load_memos()
    allele_files = _write_scheme(tmp_path, "x")
    first = _load_sequences(allele_files)
    locus_file = allele_files["xA"]
    locus_file.write_text(">xA_1\nATGGCC\n>xA_2\nATGAAA\n>xA_3\nATTTTT\n")
    _bump_mtime(locus_file)
    second = _load_sequences(allele_files)
    assert second is not first
    assert second["xA"]["3"] == "ATTTTT"


def test_exact_hash_index_memo_returns_same_object(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    allele_files = _write_scheme(tmp_path, "x")
    allele_sequences = _load_sequences(allele_files)
    first = _load_index(allele_files, allele_sequences)
    second = _load_index(allele_files, allele_sequences)
    assert second is first
    assert (tmp_path / "pre_computed" / "dna_hash_index.json").exists()


def test_exact_hash_index_reloads_after_index_rewrite(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    allele_files = _write_scheme(tmp_path, "x")
    allele_sequences = _load_sequences(allele_files)
    _load_index(allele_files, allele_sequences)

    dna_file = tmp_path / "pre_computed" / "dna_hash_index.json"
    digest = exact_hash.hash_cds_impl("ATGGCC")
    dna_file.write_text(f'{{"{digest}": [["xA", "9"]]}}')
    _bump_mtime(dna_file)

    reloaded = _load_index(allele_files, allele_sequences)
    assert reloaded[digest] == [("xA", "9")]


def test_exact_hash_index_rebuilds_on_allele_file_change(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    allele_files = _write_scheme(tmp_path, "x")
    allele_sequences = _load_sequences(allele_files)
    first = _load_index(allele_files, allele_sequences)
    assert set(first) == {
        exact_hash.hash_cds_impl("ATGGCC"),
        exact_hash.hash_cds_impl("ATGAAA"),
    }

    allele_sequences["xA"]["3"] = "ATTTTT"
    locus_file = allele_files["xA"]
    locus_file.write_text(">xA_1\nATGGCC\n>xA_2\nATGAAA\n>xA_3\nATTTTT\n")
    _bump_mtime(locus_file)
    second = _load_index(allele_files, allele_sequences)
    assert second is not first
    assert exact_hash.hash_cds_impl("ATTTTT") in second


def test_profile_table_shared_across_scheme_instances(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    allele_file = tmp_path / "dnaN.tfa"
    allele_file.write_text(">dnaN_1\nATGC\n")
    profile_file = tmp_path / "scheme.txt"
    profile_file.write_text("ST\tdnaN\n1\t1\n2\t2\n")
    locus_files = {"dnaN": allele_file}

    scheme_a = Scheme(
        name="a", loci=["dnaN"], allele_files=locus_files, profile_file=profile_file
    )
    scheme_b = Scheme(
        name="b", loci=["dnaN"], allele_files=locus_files, profile_file=profile_file
    )
    assert scheme_a.lookup_st({"dnaN": "2"}) == 2
    assert scheme_b.lookup_st({"dnaN": "1"}) == 1
    assert scheme_b._profiles is scheme_a._profiles


def test_profile_memo_invalidates_on_file_change(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    allele_file = tmp_path / "dnaN.tfa"
    allele_file.write_text(">dnaN_1\nATGC\n")
    profile_file = tmp_path / "scheme.txt"
    profile_file.write_text("ST\tdnaN\n1\t1\n")
    scheme = Scheme(
        name="a",
        loci=["dnaN"],
        allele_files={"dnaN": allele_file},
        profile_file=profile_file,
    )
    assert scheme.lookup_st({"dnaN": "1"}) == 1
    assert scheme.lookup_st({"dnaN": "2"}) is None

    profile_file.write_text("ST\tdnaN\n1\t1\n2\t2\n")
    _bump_mtime(profile_file)
    fresh = Scheme(
        name="b",
        loci=["dnaN"],
        allele_files={"dnaN": allele_file},
        profile_file=profile_file,
    )
    assert fresh.lookup_st({"dnaN": "2"}) == 2


def test_clear_scheme_load_memos_forces_rebuild(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    allele_files = _write_scheme(tmp_path, "x")
    first = _load_sequences(allele_files)
    clear_scheme_load_memos()
    second = _load_sequences(allele_files)
    assert second is not first
    assert second == first


def test_two_schemes_cached_simultaneously(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    files_a = _write_scheme(tmp_path / "a", "a")
    files_b = _write_scheme(tmp_path / "b", "b")
    seqs_a1 = _load_sequences(files_a)
    seqs_b1 = _load_sequences(files_b)
    seqs_a2 = _load_sequences(files_a)
    seqs_b2 = _load_sequences(files_b)
    assert seqs_a2 is seqs_a1
    assert seqs_b2 is seqs_b1


def test_memo_eviction_bounded(tmp_path: Path) -> None:
    clear_scheme_load_memos()
    scheme_files = [
        _write_scheme(tmp_path / f"s{i}", f"s{i}") for i in range(_MAX_MEMO_ENTRIES + 1)
    ]
    first_load = _load_sequences(scheme_files[0])
    for files in scheme_files[1:]:
        _load_sequences(files)
    reloaded = _load_sequences(scheme_files[0])
    assert reloaded is not first_load
    assert reloaded == first_load
