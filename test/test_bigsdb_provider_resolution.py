from __future__ import annotations

import json
from pathlib import Path

import pytest

import gmlst.database.providers.bigsdb as bigsdb
from gmlst.database.providers.bigsdb import BigSdbProvider


def test_resolve_seqdef_url_uses_provider_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = BigSdbProvider(
        name="pasteur",
        base_url="https://bigsdb.pasteur.fr/api/db",
        label="Institut Pasteur",
    )

    def fake_get_json(url: str, headers=None):
        assert url == "https://bigsdb.pasteur.fr/api/db"
        return [
            {
                "name": "bordetella",
                "description": "Bordetella REST API group",
                "databases": [
                    {
                        "name": "pubmlst_bordetella_seqdef",
                        "href": "https://bigsdb.pasteur.fr/api/db/pubmlst_bordetella_seqdef",
                    }
                ],
            }
        ]

    monkeypatch.setattr("gmlst.database.providers.bigsdb._get_json", fake_get_json)

    seqdef_url, db_name = provider._resolve_seqdef_url("bpertussis_1")

    assert db_name == "pubmlst_bordetella_seqdef"
    assert seqdef_url == "https://bigsdb.pasteur.fr/api/db/pubmlst_bordetella_seqdef"


def test_resolve_seqdef_url_error_hint_uses_scheme_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = BigSdbProvider(
        name="pasteur",
        base_url="https://bigsdb.pasteur.fr/api/db",
        label="Institut Pasteur",
    )

    monkeypatch.setattr(
        "gmlst.database.providers.bigsdb._get_json", lambda _u, **_k: []
    )

    with pytest.raises(ValueError, match="gmlst scheme list"):
        provider._resolve_seqdef_url("missing_1")


def test_resolve_scheme_url_prefers_suffix_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = BigSdbProvider(
        name="pubmlst",
        base_url="https://rest.pubmlst.org/db",
        label="PubMLST",
    )

    monkeypatch.setattr(
        "gmlst.database.providers.bigsdb._fetch_schemes",
        lambda _seqdef_url: [
            {
                "scheme": "https://rest.pubmlst.org/db/pubmlst_vparahaemolyticus_seqdef/schemes/1",
                "description": "MLST",
            },
            {
                "scheme": "https://rest.pubmlst.org/db/pubmlst_vparahaemolyticus_seqdef/schemes/20",
                "description": "cgMLST alpha",
            },
            {
                "scheme": "https://rest.pubmlst.org/db/pubmlst_vparahaemolyticus_seqdef/schemes/31",
                "description": "cgMLST beta",
            },
            {
                "scheme": "https://rest.pubmlst.org/db/pubmlst_vparahaemolyticus_seqdef/schemes/55",
                "description": "cgMLST",
            },
        ],
    )

    resolved = bigsdb._resolve_scheme_url(
        provider,
        "https://rest.pubmlst.org/db/pubmlst_vparahaemolyticus_seqdef",
        "vparahaemolyticus_3",
        "cgmlst",
    )

    assert resolved.endswith("/schemes/55")


def test_download_scheme_uses_batch_download_with_selected_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = BigSdbProvider(
        name="pubmlst",
        base_url="https://rest.pubmlst.org/db",
        label="PubMLST",
    )

    monkeypatch.setattr(
        provider,
        "_resolve_seqdef_url",
        lambda _scheme_name: (
            "https://rest.pubmlst.org/db/pubmlst_demo_seqdef",
            "demo",
        ),
    )
    monkeypatch.setattr(
        bigsdb,
        "_resolve_scheme_url",
        lambda *_args, **_kwargs: (
            "https://rest.pubmlst.org/db/pubmlst_demo_seqdef/schemes/1"
        ),
    )
    monkeypatch.setattr(
        bigsdb,
        "_get_json",
        lambda url, **_kw: (
            {
                "loci": [
                    "https://rest.pubmlst.org/db/pubmlst_demo_seqdef/loci/abc",
                    "https://rest.pubmlst.org/db/pubmlst_demo_seqdef/loci/def",
                ],
                "profiles_csv": "https://rest.pubmlst.org/db/pubmlst_demo_seqdef/schemes/1/profiles_csv",
            }
            if url.endswith("/schemes/1")
            else {}
        ),
    )

    captured: dict[str, object] = {}

    def _fake_download_required_files(
        url_dest_pairs,
        *,
        provider_name,
        download_tool="auto",
        max_connections=None,
        headers=None,
    ):
        captured["pairs"] = url_dest_pairs
        captured["max_concurrent"] = max_connections
        captured["tool"] = download_tool
        captured["provider_name"] = provider_name
        for _, dest in url_dest_pairs:
            dest.write_text(">locus_1\nATGC\n")

    monkeypatch.setattr(
        bigsdb, "download_required_files", _fake_download_required_files
    )
    monkeypatch.setattr(
        bigsdb,
        "_download_file",
        lambda _url, dest, tool="auto", max_connections=None: dest.write_text(
            "ST\tabc\tdef\n1\t1\t1\n"
        ),
    )

    provider.download_scheme("demo_1", tmp_path, download_tool="aria2c")

    assert captured["tool"] == "aria2c"
    assert captured["max_concurrent"] == 4
    assert captured["provider_name"] == "pubmlst"
    assert len(captured["pairs"]) == 2


def test_update_scheme_noop_when_meta_missing_but_local_files_complete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = BigSdbProvider(
        name="pubmlst",
        base_url="https://rest.pubmlst.org/db",
        label="PubMLST",
    )

    monkeypatch.setattr(
        provider,
        "_resolve_seqdef_url",
        lambda _scheme_name: (
            "https://rest.pubmlst.org/db/pubmlst_demo_seqdef",
            "demo",
        ),
    )
    monkeypatch.setattr(
        bigsdb,
        "_resolve_scheme_url",
        lambda *_args, **_kwargs: (
            "https://rest.pubmlst.org/db/pubmlst_demo_seqdef/schemes/1"
        ),
    )

    def _fake_get_json(url: str, headers=None):
        if url.endswith("/schemes/1"):
            return {
                "loci": [
                    "https://rest.pubmlst.org/db/pubmlst_demo_seqdef/loci/abc",
                    "https://rest.pubmlst.org/db/pubmlst_demo_seqdef/loci/def",
                ],
                "profiles_csv": "https://rest.pubmlst.org/db/pubmlst_demo_seqdef/schemes/1/profiles_csv",
                "records": 1,
                "last_updated": "2026-01-01T00:00:00",
                "last_added": "2026-01-01T00:00:00",
            }
        if url.endswith("/loci/abc/alleles"):
            return {"records": 1, "last_updated": "2026-01-01T00:00:00"}
        if url.endswith("/loci/def/alleles"):
            return {"records": 1, "last_updated": "2026-01-01T00:00:00"}
        return {}

    monkeypatch.setattr(bigsdb, "_get_json", _fake_get_json)

    (tmp_path / "abc.tfa").write_text(">abc_1\nATGC\n")
    (tmp_path / "def.tfa").write_text(">def_1\nATGC\n")
    (tmp_path / "demo_1.txt").write_text("ST\tabc\tdef\n1\t1\t1\n")
    (tmp_path / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": "demo_1",
                "provider": "pubmlst",
                "scheme_type": "mlst",
                "loci": ["abc", "def"],
            }
        )
    )

    calls = {"batch": 0, "single": 0}

    def _fake_download_required_files(*_args, **_kwargs):
        calls["batch"] += 1

    def _fake_download(*_args, **_kwargs):
        calls["single"] += 1

    monkeypatch.setattr(
        bigsdb, "download_required_files", _fake_download_required_files
    )
    monkeypatch.setattr(bigsdb, "_download_file", _fake_download)

    changed = provider.update_scheme("demo_1", tmp_path)

    assert changed is False
    assert calls["batch"] == 0
    assert calls["single"] == 0
