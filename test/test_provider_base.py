from __future__ import annotations

from pathlib import Path

import pytest

from gmlst.database.providers.base import download_required_files


def test_download_required_files_raises_on_reported_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dest = tmp_path / "a.tfa"
    monkeypatch.setattr(
        "gmlst.database.providers.base.download_files_batch",
        lambda *_args, **_kwargs: (0, 1),
    )

    with pytest.raises(RuntimeError, match="Failed to download 1 files"):
        download_required_files(
            [("https://example.com/a", dest)],
            provider_name="demo",
        )


def test_download_required_files_raises_when_output_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dest = tmp_path / "a.tfa"
    monkeypatch.setattr(
        "gmlst.database.providers.base.download_files_batch",
        lambda *_args, **_kwargs: (1, 0),
    )

    with pytest.raises(RuntimeError, match="Missing or empty downloaded file"):
        download_required_files(
            [("https://example.com/a", dest)],
            provider_name="demo",
        )


def test_download_required_files_accepts_successful_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dest = tmp_path / "a.tfa"

    def _fake_download(*_args, **_kwargs):
        dest.write_text("ok")
        return (1, 0)

    monkeypatch.setattr(
        "gmlst.database.providers.base.download_files_batch",
        _fake_download,
    )

    download_required_files(
        [("https://example.com/a", dest)],
        provider_name="demo",
    )

    assert dest.read_text() == "ok"
