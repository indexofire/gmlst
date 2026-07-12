from __future__ import annotations

import json
from pathlib import Path

import pytest

from gmlst.database.providers.enterobase import EnterobaseProvider


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
    assert meta["locus_remote"] == {
        "abc": {
            "etag": "head:https://enterobase.warwick.ac.uk/schemes/Escherichia.Achtman7GeneMLST/abc.fasta.gz"
        },
        "def": {
            "etag": "head:https://enterobase.warwick.ac.uk/schemes/Escherichia.Achtman7GeneMLST/def.fasta.gz"
        },
    }


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
