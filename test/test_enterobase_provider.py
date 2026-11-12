from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from gmlst.database.providers.enterobase import (
    EnterobaseProvider,
    _convert_profiles_archive,
)


def test_enterobase_download_scheme_writes_remote_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = EnterobaseProvider()

    monkeypatch.setattr(
        provider,
        "_get_loci",
        lambda _dir_name: ["abc", "def"],
    )
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase.download_required_files",
        lambda url_dest_pairs, **_kwargs: [
            dest.write_bytes(b"gz") for _url, dest in url_dest_pairs
        ],
    )
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase.gzip.decompress",
        lambda _payload: b">abc_1\nATGC\n",
    )
    monkeypatch.setattr(
        provider,
        "_download_profiles",
        lambda *_args, **_kwargs: (tmp_path / "ecoli_1.txt").write_text(
            "ST\tabc\n1\t1\n"
        ),
    )
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase._head_remote_file",
        lambda url: {"etag": f"head:{url}"},
    )

    provider.download_scheme(
        "ecoli_mlst",
        tmp_path,
        extra={"directory": "Escherichia.Achtman7GeneMLST"},
    )

    meta = json.loads((tmp_path / ".meta.json").read_text())
    assert meta["profiles_remote"] == {
        "etag": "head:https://enterobase.warwick.ac.uk/schemes/Escherichia.Achtman7GeneMLST/profiles.list.gz"
    }
    # Per-locus fingerprints are NOT probed at download time (the first
    # `scheme update` records them); locus_remote starts empty.
    assert meta["locus_remote"] == {}


def test_enterobase_download_scheme_fails_on_decompression_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = EnterobaseProvider()

    monkeypatch.setattr(provider, "_get_loci", lambda _dir_name: ["abc"])
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase.download_required_files",
        lambda url_dest_pairs, **_kwargs: [
            dest.write_bytes(b"broken") for _url, dest in url_dest_pairs
        ],
    )
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase.gzip.decompress",
        lambda _payload: (_ for _ in ()).throw(OSError("bad gzip")),
    )
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase._head_remote_file",
        lambda url: {"etag": f"head:{url}"},
    )

    with pytest.raises(RuntimeError, match="Failed to decompress abc"):
        provider.download_scheme(
            "ecoli_mlst",
            tmp_path,
            extra={"directory": "Escherichia.Achtman7GeneMLST"},
        )


def test_enterobase_download_scheme_skips_already_extracted_loci(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Regression: extracted loci (.tfa) must never be re-downloaded.

    The .gz intermediate is deleted after extraction, so keying resume on
    .gz existence alone re-downloaded every already-extracted locus on each
    retry of a large scheme (e.g. senterica_2, 3002 loci).
    """
    provider = EnterobaseProvider()

    # 'abc' fully extracted in a previous run; a stale .gz sits next to it.
    (tmp_path / "abc.tfa").write_text(">abc_1\nATGC\n")
    (tmp_path / "abc.fasta.gz").write_bytes(b"stale-gz")

    monkeypatch.setattr(provider, "_get_loci", lambda _dir_name: ["abc", "def"])
    batch_pairs: list[list[tuple[str, Path]]] = []

    def _fake_batch(url_dest_pairs, **_kwargs):
        batch_pairs.append(list(url_dest_pairs))
        for _url, dest in url_dest_pairs:
            dest.write_bytes(b"gz")

    monkeypatch.setattr(
        "gmlst.database.providers.enterobase.download_required_files",
        _fake_batch,
    )
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase.gzip.decompress",
        lambda _payload: b">def_1\nATGC\n",
    )
    monkeypatch.setattr(
        provider,
        "_download_profiles",
        lambda *_args, **_kwargs: (tmp_path / "ecoli_1.txt").write_text(
            "ST\tabc\tdef\n1\t1\t1\n"
        ),
    )
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase._head_remote_file",
        lambda url: {"etag": f"head:{url}"},
    )

    provider.download_scheme(
        "ecoli_mlst",
        tmp_path,
        extra={"directory": "Escherichia.Achtman7GeneMLST"},
    )

    # Only the missing locus was queued for download.
    assert len(batch_pairs) == 1
    assert [dest.name for _url, dest in batch_pairs[0]] == ["def.fasta.gz"]

    # Extracted locus kept its .tfa content; the stale .gz was cleaned up.
    assert (tmp_path / "abc.tfa").read_text() == ">abc_1\nATGC\n"
    assert not (tmp_path / "abc.fasta.gz").exists()
    assert (tmp_path / "def.tfa").exists()
    assert not (tmp_path / "def.fasta.gz").exists()

    # Fingerprints are not recorded at download time (first update seeds them).
    meta = json.loads((tmp_path / ".meta.json").read_text())
    assert meta["locus_remote"] == {}


def test_enterobase_extract_loci_decompresses_all_in_parallel(
    tmp_path: Path,
) -> None:
    provider = EnterobaseProvider()
    loci = [f"loc{i}" for i in range(8)]
    for locus in loci:
        (tmp_path / f"{locus}.fasta.gz").write_bytes(
            gzip.compress(f">{locus}_1\nATGC\n".encode())
        )

    provider._extract_loci(tmp_path, loci, validate=True)

    for locus in loci:
        assert (tmp_path / f"{locus}.tfa").read_text() == f">{locus}_1\nATGC\n"
        assert not (tmp_path / f"{locus}.fasta.gz").exists()


def test_enterobase_extract_loci_keeps_successes_when_one_fails(
    tmp_path: Path,
) -> None:
    """A corrupt gz must not lose already-extracted loci (resume guarantee)."""
    provider = EnterobaseProvider()
    (tmp_path / "good.fasta.gz").write_bytes(gzip.compress(b">good_1\nATGC\n"))
    (tmp_path / "bad.fasta.gz").write_bytes(b"not-a-gzip")

    with pytest.raises(RuntimeError, match="Failed to decompress bad"):
        provider._extract_loci(tmp_path, ["good", "bad"], validate=False)

    # The healthy file was still extracted despite the failure.
    assert (tmp_path / "good.tfa").read_text() == ">good_1\nATGC\n"
    assert not (tmp_path / "good.fasta.gz").exists()


def test_enterobase_update_first_pass_trusts_fingerprintless_loci(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """First update after a fresh download must not re-download anything.

    Fresh downloads store no per-locus fingerprints, so the first update
    probes headers, trusts valid local .tfa files, and records the
    fingerprints for exact comparisons on later updates.
    """
    provider = EnterobaseProvider()

    # Local state as left by download_scheme: valid tfas, no fingerprints.
    (tmp_path / "abc.tfa").write_text(">abc_1\nATGC\n")
    (tmp_path / "def.tfa").write_text(">def_1\nATGC\n")
    (tmp_path / "ecoli_mlst.txt").write_text("ST\tabc\tdef\n1\t1\t1\n")
    (tmp_path / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": "ecoli_mlst",
                "provider": "enterobase",
                "loci": ["abc", "def"],
                "locus_remote": {},
                "profiles_remote": {"etag": "profiles-old"},
                "profile_meta": {"records": 1},
            }
        )
    )

    monkeypatch.setattr(provider, "_get_loci", lambda _dir_name: ["abc", "def"])
    monkeypatch.setattr(
        provider,
        "_fetch_locus_headers",
        lambda _dir_name, loci: {locus: {"etag": f"fresh:{locus}"} for locus in loci},
    )
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase._head_remote_file",
        lambda url: {"etag": "profiles-old"},  # unchanged
    )
    downloads: list[list[tuple[str, Path]]] = []
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase.download_required_files",
        lambda pairs, **_kwargs: downloads.append(list(pairs)),
    )

    changed = provider.update_scheme(
        "ecoli_mlst",
        tmp_path,
        extra={"directory": "Escherichia.Achtman7GeneMLST"},
    )

    assert changed is False
    assert downloads == []  # nothing re-downloaded

    # Fingerprints recorded for future exact comparisons.
    meta = json.loads((tmp_path / ".meta.json").read_text())
    assert meta["locus_remote"] == {
        "abc": {"etag": "fresh:abc"},
        "def": {"etag": "fresh:def"},
    }


def test_enterobase_update_redownloads_only_changed_fingerprints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Once fingerprints are known, only genuinely changed loci re-download."""
    provider = EnterobaseProvider()

    (tmp_path / "abc.tfa").write_text(">abc_1\nATGC\n")
    (tmp_path / "def.tfa").write_text(">def_1\nATGC\n")
    (tmp_path / "ecoli_mlst.txt").write_text("ST\tabc\tdef\n1\t1\t1\n")
    (tmp_path / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": "ecoli_mlst",
                "provider": "enterobase",
                "loci": ["abc", "def"],
                "locus_remote": {
                    "abc": {"etag": "abc-v1"},
                    "def": {"etag": "def-v1"},
                },
                "profiles_remote": {"etag": "profiles-old"},
            }
        )
    )

    monkeypatch.setattr(provider, "_get_loci", lambda _dir_name: ["abc", "def"])
    monkeypatch.setattr(
        provider,
        "_fetch_locus_headers",
        lambda _dir_name, loci: {
            "abc": {"etag": "abc-v2"},  # changed upstream
            "def": {"etag": "def-v1"},  # unchanged
        },
    )
    monkeypatch.setattr(
        "gmlst.database.providers.enterobase._head_remote_file",
        lambda url: {"etag": "profiles-old"},
    )

    downloads: list[list[tuple[str, Path]]] = []

    def _fake_download(pairs, **_kwargs):
        downloads.append(list(pairs))
        for _url, dest in pairs:
            dest.write_bytes(gzip.compress(b">abc_2\nATGC\n"))

    monkeypatch.setattr(
        "gmlst.database.providers.enterobase.download_required_files",
        _fake_download,
    )

    changed = provider.update_scheme(
        "ecoli_mlst",
        tmp_path,
        extra={"directory": "Escherichia.Achtman7GeneMLST"},
    )

    assert changed is True
    assert len(downloads) == 1
    assert [dest.name for _url, dest in downloads[0]] == ["abc.fasta.gz"]
    assert (tmp_path / "abc.tfa").read_text() == ">abc_2\nATGC\n"


def _write_profiles_gz(path: Path, rows: list[list[str]]) -> None:
    lines = ["\t".join(row) for row in rows]
    path.write_bytes(gzip.compress(("\n".join(lines) + "\n").encode()))


def test_convert_profiles_archive_streams_and_reorders_columns(
    tmp_path: Path,
) -> None:
    """Output columns follow the loci order, not the archive column order."""
    gz = tmp_path / "profiles.list.gz"
    # Archive columns: ST, locB, locA, extra — loci requested as [locA, locB].
    _write_profiles_gz(
        gz,
        [
            ["ST", "locB", "locA", "extra"],
            ["1", "b1", "a1", "x1"],
            ["2", "b2", "a2", "x2"],
        ],
    )
    dest = tmp_path / "scheme.txt"

    rows = _convert_profiles_archive(gz, dest, ["locA", "locB"])

    assert rows == 2
    assert dest.read_text() == "ST\tlocA\tlocB\n1\ta1\tb1\n2\ta2\tb2\n"
    assert not gz.parent.glob("*.tmp") or not list(dest.parent.glob("*.tmp"))


def test_convert_profiles_archive_marks_missing_locus_as_missing(
    tmp_path: Path,
) -> None:
    gz = tmp_path / "profiles.list.gz"
    _write_profiles_gz(gz, [["ST", "locA"], ["1", "a1"]])
    dest = tmp_path / "scheme.txt"

    rows = _convert_profiles_archive(gz, dest, ["locA", "absent_locus"])

    assert rows == 1
    assert dest.read_text() == "ST\tlocA\tabsent_locus\n1\ta1\t-\n"


def test_convert_profiles_archive_skips_short_rows(tmp_path: Path) -> None:
    gz = tmp_path / "profiles.list.gz"
    _write_profiles_gz(
        gz,
        [
            ["ST", "locA", "locB"],
            ["1", "a1", "b1"],
            ["broken"],
            ["2", "a2", "b2"],
        ],
    )
    dest = tmp_path / "scheme.txt"

    rows = _convert_profiles_archive(gz, dest, ["locA", "locB"])

    assert rows == 2
    assert "broken" not in dest.read_text()


def test_convert_profiles_archive_rejects_empty_archive(tmp_path: Path) -> None:
    gz = tmp_path / "profiles.list.gz"
    gz.write_bytes(gzip.compress(b""))
    dest = tmp_path / "scheme.txt"

    with pytest.raises(RuntimeError, match="no data"):
        _convert_profiles_archive(gz, dest, ["locA"])

    assert not dest.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_convert_profiles_archive_cleans_tmp_on_corrupt_gz(
    tmp_path: Path,
) -> None:
    gz = tmp_path / "profiles.list.gz"
    gz.write_bytes(b"not-a-gzip")
    dest = tmp_path / "scheme.txt"

    with pytest.raises(OSError):
        _convert_profiles_archive(gz, dest, ["locA"])

    assert not dest.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_download_profiles_keeps_gz_for_resume_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = EnterobaseProvider()

    def _fake_download(_url: str, dest: Path, **_kwargs: object) -> None:
        dest.write_bytes(b"truncated-download")

    monkeypatch.setattr(
        "gmlst.database.providers.enterobase.download_file",
        _fake_download,
    )

    with pytest.raises(RuntimeError, match="Failed to download profiles"):
        provider._download_profiles(
            "Salmonella.cgMLSTv2",
            ["locA"],
            tmp_path,
            "senterica_2",
        )

    # The partial archive is kept so the retry resumes instead of restarting.
    assert (tmp_path / "profiles.list.gz").exists()
    assert not (tmp_path / "senterica_2.txt").exists()
