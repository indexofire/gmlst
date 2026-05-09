from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
import requests

import gmlst.database.providers.cgmlst as cgmlst
from gmlst.database.providers.cgmlst import CgmlstProvider


def _write_demo_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("abc.fasta", ">abc_1\nATGC\n")
        zf.writestr("def.fasta", ">def_1\nCGTA\n")


def test_download_scheme_reuses_existing_zip_and_extracts_only_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = CgmlstProvider()
    monkeypatch.setattr(
        cgmlst,
        "_CGMLST_SCHEMES",
        [
            {
                "name": "demo",
                "display": "Demo",
                "organism": "Demo organism",
                "schema_id": "999",
                "loci": 2,
            }
        ],
    )
    monkeypatch.setattr(
        cgmlst,
        "_fetch_schema_status",
        lambda _schema_id: {
            "version": "1",
            "last_change": "now",
            "locus_count": "2",
        },
    )

    zip_path = tmp_path / "demo_1.zip"
    _write_demo_zip(zip_path)
    existing = tmp_path / "abc.fasta"
    existing.write_text(">abc_1\nATGC\n")

    calls = {"download": 0}

    def _fake_download(*_args, **_kwargs):
        calls["download"] += 1

    monkeypatch.setattr(cgmlst, "download_file", _fake_download)

    provider.download_scheme("demo_1", tmp_path, download_tool="aria2c")

    assert calls["download"] == 0
    assert existing.read_text() == ">abc_1\nATGC\n"
    assert (tmp_path / "def.fasta").exists()
    assert not zip_path.exists()
    meta = json.loads((tmp_path / ".meta.json").read_text())
    assert sorted(meta["loci"]) == ["abc", "def"]


def test_download_scheme_keeps_zip_if_finalize_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = CgmlstProvider()
    monkeypatch.setattr(
        cgmlst,
        "_CGMLST_SCHEMES",
        [
            {
                "name": "demo",
                "display": "Demo",
                "organism": "Demo organism",
                "schema_id": "999",
                "loci": 2,
            }
        ],
    )

    def _fake_download(_url: str, dest: Path, **_kwargs) -> None:
        _write_demo_zip(dest)

    monkeypatch.setattr(cgmlst, "download_file", _fake_download)
    monkeypatch.setattr(
        cgmlst,
        "_fetch_schema_status",
        lambda _schema_id: (_ for _ in ()).throw(RuntimeError("status-failed")),
    )

    with pytest.raises(RuntimeError, match="status-failed"):
        provider.download_scheme("demo_1", tmp_path)

    assert (tmp_path / "demo_1.zip").exists()


def test_download_scheme_raises_when_extracted_loci_incomplete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = CgmlstProvider()
    monkeypatch.setattr(
        cgmlst,
        "_CGMLST_SCHEMES",
        [
            {
                "name": "demo",
                "display": "Demo",
                "organism": "Demo organism",
                "schema_id": "999",
                "loci": 2,
            }
        ],
    )

    def _fake_download(_url: str, dest: Path, **_kwargs) -> None:
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("abc.fasta", ">abc_1\nATGC\n")

    monkeypatch.setattr(cgmlst, "download_file", _fake_download)
    monkeypatch.setattr(
        cgmlst,
        "_fetch_schema_status",
        lambda _schema_id: {"version": "1", "last_change": "now", "locus_count": "2"},
    )

    with pytest.raises(RuntimeError, match="Incomplete cgMLST download"):
        provider.download_scheme("demo_1", tmp_path)

    assert (tmp_path / "demo_1.zip").exists()


def test_update_scheme_repairs_incomplete_local_loci(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = CgmlstProvider()
    monkeypatch.setattr(
        cgmlst,
        "_CGMLST_SCHEMES",
        [
            {
                "name": "demo",
                "display": "Demo",
                "organism": "Demo organism",
                "schema_id": "999",
                "loci": 2,
            }
        ],
    )
    monkeypatch.setattr(
        cgmlst,
        "_fetch_schema_status",
        lambda _schema_id: {
            "version": "1",
            "last_change": "now",
            "locus_count": "2",
        },
    )

    (tmp_path / "abc.fasta").write_text(">abc_1\nATGC\n")
    (tmp_path / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": "demo_1",
                "provider": "cgmlst",
                "scheme_type": "cgmlst",
                "schema_id": "999",
                "remote": {
                    "version": "1",
                    "last_change": "now",
                    "locus_count": "2",
                },
            }
        )
    )

    calls = {"n": 0}

    def _fake_download_scheme(*_args, **_kwargs):
        calls["n"] += 1

    monkeypatch.setattr(provider, "download_scheme", _fake_download_scheme)

    changed = provider.update_scheme("demo_1", tmp_path)

    assert changed is True
    assert calls["n"] == 1


def test_download_scheme_raises_when_locus_count_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = CgmlstProvider()
    monkeypatch.setattr(
        cgmlst,
        "_CGMLST_SCHEMES",
        [
            {
                "name": "demo",
                "display": "Demo",
                "organism": "Demo organism",
                "schema_id": "999",
                "loci": 2,
            }
        ],
    )

    def _fake_download(_url: str, dest: Path, **_kwargs) -> None:
        _write_demo_zip(dest)

    monkeypatch.setattr(cgmlst, "download_file", _fake_download)
    monkeypatch.setattr(
        cgmlst,
        "_fetch_schema_status",
        lambda _schema_id: {"version": "1", "last_change": "now", "locus_count": ""},
    )

    with pytest.raises(RuntimeError, match="Could not determine expected locus count"):
        provider.download_scheme("demo_1", tmp_path)


def test_fetch_schema_status_wraps_request_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_timeout(*_args, **_kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(cgmlst.requests, "get", _raise_timeout)

    with pytest.raises(RuntimeError, match="Failed to fetch cgMLST schema status"):
        cgmlst._fetch_schema_status("999")


def test_extract_schema_field_handles_whitespace() -> None:
    html = (
        "<tr><td> Version </td> <td>  7  </td></tr>"
        "<tr><td>\nLocus Count\n</td>\n<td> 2,345 </td></tr>"
    )
    assert cgmlst._extract_schema_field(html, "Version") == "7"
    assert cgmlst._extract_schema_field(html, "Locus Count") == "2,345"
