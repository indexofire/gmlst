"""Tests that remote URLs/file names cannot inject lines into aria2c input files."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import gmlst.database.download as dl
from gmlst.database.providers.bigsdb import BigSdbProvider
from gmlst.database.url_guard import UrlGuardError, assert_public_url

_INJECTED_URL = "https://example.com/x\n  dir=/tmp/x\n  out=.bashrc"


@pytest.mark.parametrize(
    "url",
    [
        _INJECTED_URL,
        "https://example.com/x\r\n  dir=/tmp/x",
        "https://example.com/x\tdir=/tmp/x",
        "https://example.com/a b",
        "https://example.com/x\x00",
    ],
)
def test_assert_public_url_rejects_control_chars(url: str) -> None:
    with pytest.raises(UrlGuardError, match="control characters"):
        assert_public_url(url)


def test_assert_public_url_rejects_control_chars_even_with_bypass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("gmlst.database.url_guard._ALLOW_PRIVATE", True)
    with pytest.raises(UrlGuardError):
        assert_public_url(_INJECTED_URL)


def test_download_files_batch_rejects_newline_url_before_input_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(dl.shutil, "which", lambda _name: "/usr/bin/aria2c")
    monkeypatch.setattr(dl, "_retry_rounds", lambda: 0)
    run_calls: list[object] = []
    monkeypatch.setattr(
        dl.subprocess, "run", lambda *a, **k: run_calls.append(a) or None
    )
    pairs = [
        (_INJECTED_URL, tmp_path / "a.tfa"),
        ("https://example.com/b", tmp_path / "b.tfa"),
    ]

    with (
        patch.object(tempfile, "NamedTemporaryFile") as mock_tmp,
        pytest.raises(UrlGuardError),
    ):
        dl.download_files_batch(pairs, tool="aria2c")

    mock_tmp.assert_not_called()
    assert run_calls == []


@pytest.mark.parametrize("name", ["a\n  dir=x.tfa", "a\r.tfa", "a\x1b.tfa"])
def test_download_files_batch_rejects_control_chars_in_file_name(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    name: str,
) -> None:
    monkeypatch.setattr(dl.shutil, "which", lambda _name: "/usr/bin/aria2c")
    monkeypatch.setattr(dl, "_retry_rounds", lambda: 0)
    monkeypatch.setattr(dl, "assert_public_url", lambda _url: None)
    pairs = [
        ("https://example.com/a", tmp_path / name),
        ("https://example.com/b", tmp_path / "b.tfa"),
    ]

    with (
        patch.object(tempfile, "NamedTemporaryFile") as mock_tmp,
        pytest.raises(UrlGuardError, match="file name"),
    ):
        dl.download_files_batch(pairs, tool="aria2c")

    mock_tmp.assert_not_called()


@pytest.mark.parametrize(
    "locus_url",
    [
        "https://example.com/loci/..",
        "https://example.com/loci/a\n  dir=x",
        "https://example.com/loci/abc\n",
        "https://example.com/loci/.hidden",
    ],
)
def test_bigsdb_download_scheme_rejects_unsafe_locus_names(
    tmp_path: Path,
    locus_url: str,
) -> None:
    provider = BigSdbProvider("pubmlst", "https://rest.pubmlst.org", "PubMLST")
    detail = {"loci": [locus_url, "https://example.com/loci/abcZ"]}
    with (
        patch.object(
            provider,
            "_fetch_scheme_detail",
            return_value=("seqdef", "scheme", detail),
        ),
        patch("gmlst.database.providers.bigsdb.download_required_files") as mock_dl,
        pytest.raises(ValueError, match="BIGSdb locus name"),
    ):
        provider.download_scheme("demo", tmp_path / "out")

    mock_dl.assert_not_called()
