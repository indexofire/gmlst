from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import gmlst.database.download as dl


def test_download_file_preserves_partial_for_explicit_aria2c(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dest = tmp_path / "scheme.zip"
    dest.write_bytes(b"partial")
    aria2_state = tmp_path / "scheme.zip.aria2"
    aria2_state.write_text("state")

    monkeypatch.setattr(dl.shutil, "which", lambda _name: "/usr/bin/aria2c")
    monkeypatch.setattr(dl, "_try_aria2c", lambda *_args, **_kwargs: False)

    with pytest.raises(RuntimeError, match="Requested download tool failed: aria2c"):
        dl.download_file("https://example.com/scheme.zip", dest, tool="aria2c")

    assert dest.exists()
    assert aria2_state.exists()


def test_download_file_auto_preserves_partial_after_aria2c_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dest = tmp_path / "scheme.zip"
    dest.write_bytes(b"partial")
    call_order: list[str] = []

    monkeypatch.setattr(
        dl.shutil,
        "which",
        lambda name: "/usr/bin/tool" if name in {"aria2c", "curl"} else None,
    )

    def _fake_aria(*_args, **_kwargs):
        call_order.append("aria2c")
        return False

    def _fake_curl(*_args, **_kwargs):
        call_order.append("curl")
        return True

    monkeypatch.setattr(dl, "_try_aria2c", _fake_aria)
    monkeypatch.setattr(dl, "_try_curl", _fake_curl)
    dl.download_file("https://example.com/scheme.zip", dest, tool="auto")

    assert call_order[:2] == ["aria2c", "curl"]
    assert dest.exists()


def test_download_files_batch_treats_nonzero_aria2c_exit_as_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dest1 = tmp_path / "scheme1.txt"
    dest2 = tmp_path / "scheme2.txt"

    monkeypatch.setattr(dl.shutil, "which", lambda _name: "/usr/bin/aria2c")

    def _fake_run(*_args, **_kwargs):
        dest1.write_text("partial")
        dest2.write_text("partial")
        return subprocess.CompletedProcess(["aria2c"], 1)

    monkeypatch.setattr(dl.subprocess, "run", _fake_run)

    success, fail = dl.download_files_batch(
        [
            ("https://example.com/scheme1.txt", dest1),
            ("https://example.com/scheme2.txt", dest2),
        ],
        tool="aria2c",
    )

    assert (success, fail) == (0, 2)


def test_fetch_json_retries_on_invalid_json_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            calls["count"] += 1
            if calls["count"] == 1:
                raise ValueError("invalid json")
            return {"ok": True}

    monkeypatch.setattr("requests.get", lambda *_args, **_kwargs: _FakeResponse())
    monkeypatch.setattr(dl.time, "sleep", lambda _seconds: None)

    assert dl.fetch_json("https://example.com/api", retries=2, retry_delay=0) == {
        "ok": True
    }
