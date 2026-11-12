"""Tests for download politeness throttling (rate-limit protection)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import requests

import gmlst.database.download as dl


class TestRetryWaitSeconds:
    def test_exponential_backoff_growth(self) -> None:
        exc = RuntimeError("boom")
        assert dl._retry_wait_seconds(exc, 1, 5.0) == 5.0
        assert dl._retry_wait_seconds(exc, 2, 5.0) == 10.0
        assert dl._retry_wait_seconds(exc, 3, 5.0) == 20.0

    def test_backoff_capped_at_max(self) -> None:
        exc = RuntimeError("boom")
        assert dl._retry_wait_seconds(exc, 10, 5.0) == dl._MAX_RETRY_BACKOFF

    def test_retry_after_header_honored(self) -> None:
        class _Resp:
            headers = {"Retry-After": "30"}

        class _Exc(Exception):
            response = _Resp()

        assert dl._retry_wait_seconds(_Exc(), 1, 5.0) == 30.0

    def test_retry_after_lower_than_backoff_uses_backoff(self) -> None:
        class _Resp:
            headers = {"Retry-After": "2"}

        class _Exc(Exception):
            response = _Resp()

        assert dl._retry_wait_seconds(_Exc(), 3, 5.0) == 20.0

    def test_invalid_retry_after_falls_back_to_backoff(self) -> None:
        class _Resp:
            headers = {"Retry-After": "not-a-number"}

        class _Exc(Exception):
            response = _Resp()

        assert dl._retry_wait_seconds(_Exc(), 1, 5.0) == 5.0


class TestThrottleRequest:
    def test_no_sleep_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GMLST_DOWNLOAD_DELAY", raising=False)
        sleeps: list[float] = []
        monkeypatch.setattr(dl.time, "sleep", sleeps.append)

        dl._throttle_request()
        assert sleeps == []

    def test_sleeps_configured_delay(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GMLST_DOWNLOAD_DELAY", "1.5")
        sleeps: list[float] = []
        monkeypatch.setattr(dl.time, "sleep", sleeps.append)

        dl._throttle_request()
        assert sleeps == [1.5]

    def test_invalid_env_value_is_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GMLST_DOWNLOAD_DELAY", "not-a-number")
        sleeps: list[float] = []
        monkeypatch.setattr(dl.time, "sleep", sleeps.append)

        dl._throttle_request()
        assert sleeps == []


class TestChunkPause:
    def _pairs(self, tmp_path: Path, count: int) -> list[tuple[str, Path]]:
        return [
            (f"https://example.com/f{i}.tfa", tmp_path / f"f{i}.tfa")
            for i in range(count)
        ]

    @staticmethod
    def _succeed_by_writing(
        pending: list[tuple[str, Path]], *_args: object, **_kwargs: object
    ) -> tuple[int, int]:
        # Real batches leave files on disk; the retry logic re-lists by
        # file existence, so a fake that writes files counts as success.
        for _url, dest in pending:
            dest.write_text("done")
        return (len(pending), 0)

    def test_pause_between_chunks_not_after_last(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GMLST_DOWNLOAD_CHUNK_PAUSE", raising=False)
        monkeypatch.setattr(dl, "_BATCH_SIZE", 2)
        sleeps: list[float] = []
        monkeypatch.setattr(dl.time, "sleep", sleeps.append)
        monkeypatch.setattr(dl, "_download_single_batch", self._succeed_by_writing)

        dl.download_files_batch(self._pairs(tmp_path, 5))

        # 3 chunks -> pauses between chunk 1->2 and 2->3, none after the last
        assert sleeps == [dl._DEFAULT_CHUNK_PAUSE] * 2

    def test_env_override_disables_pause(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GMLST_DOWNLOAD_CHUNK_PAUSE", "0")
        monkeypatch.setattr(dl, "_BATCH_SIZE", 2)
        sleeps: list[float] = []
        monkeypatch.setattr(dl.time, "sleep", sleeps.append)
        monkeypatch.setattr(dl, "_download_single_batch", self._succeed_by_writing)

        dl.download_files_batch(self._pairs(tmp_path, 5))

        assert sleeps == []

    def test_single_chunk_never_pauses(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GMLST_DOWNLOAD_CHUNK_PAUSE", raising=False)
        sleeps: list[float] = []
        monkeypatch.setattr(dl.time, "sleep", sleeps.append)
        monkeypatch.setattr(dl, "_download_single_batch", self._succeed_by_writing)

        dl.download_files_batch(self._pairs(tmp_path, 3))

        assert sleeps == []


class TestBatchRetry:
    def _pairs(self, tmp_path: Path, count: int) -> list[tuple[str, Path]]:
        return [
            (f"https://example.com/f{i}.tfa", tmp_path / f"f{i}.tfa")
            for i in range(count)
        ]

    def test_transient_failures_retried_within_one_run(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """First pass fails, retry round downloads the missing files."""
        monkeypatch.delenv("GMLST_DOWNLOAD_RETRY_ROUNDS", raising=False)
        monkeypatch.delenv("GMLST_DOWNLOAD_RETRY_PAUSE", raising=False)
        sleeps: list[float] = []
        monkeypatch.setattr(dl.time, "sleep", sleeps.append)
        pass_calls: list[list[tuple[str, Path]]] = []

        def _flaky_single_batch(pending, *args, **kwargs):
            pass_calls.append(list(pending))
            if len(pass_calls) == 1:
                return (0, len(pending))  # everything fails (e.g. TLS reset)
            # Retry round: succeed, writing files so they count as done.
            for _url, dest in pending:
                dest.write_text("done")
            return (len(pending), 0)

        monkeypatch.setattr(dl, "_download_single_batch", _flaky_single_batch)

        success, fail = dl.download_files_batch(self._pairs(tmp_path, 3))

        assert (success, fail) == (3, 0)
        assert len(pass_calls) == 2
        # one retry pause between the two passes, none after the last
        assert sleeps == [dl._DEFAULT_RETRY_PAUSE]

    def test_retry_rounds_can_be_disabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GMLST_DOWNLOAD_RETRY_ROUNDS", "0")
        sleeps: list[float] = []
        monkeypatch.setattr(dl.time, "sleep", sleeps.append)
        monkeypatch.setattr(
            dl, "_download_single_batch", lambda *a, **k: (0, len(a[0]))
        )

        success, fail = dl.download_files_batch(self._pairs(tmp_path, 2))

        assert (success, fail) == (0, 2)
        assert sleeps == []

    def test_successful_files_neer_redownloaded_across_rounds(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("GMLST_DOWNLOAD_RETRY_ROUNDS", raising=False)
        monkeypatch.setenv("GMLST_DOWNLOAD_RETRY_PAUSE", "0")
        pass_calls: list[list[tuple[str, Path]]] = []

        def _partial_batch(pending, *args, **kwargs):
            pass_calls.append(list(pending))
            if len(pass_calls) == 1:
                # Only the first file lands on the opening pass.
                pending[0][1].write_text("done")
                return (1, len(pending) - 1)
            for _url, dest in pending:
                dest.write_text("done")
            return (len(pending), 0)

        monkeypatch.setattr(dl, "_download_single_batch", _partial_batch)

        success, fail = dl.download_files_batch(self._pairs(tmp_path, 3))

        assert (success, fail) == (3, 0)
        assert [len(p) for p in pass_calls] == [3, 2]  # refiltered each round


class TestFetchWithRetry:
    def _fake_session(self, monkeypatch: pytest.MonkeyPatch, behavior) -> None:
        class _FakeResponse:
            def __init__(self, status: int) -> None:
                self.status_code = status

            def raise_for_status(self) -> None:
                if self.status_code >= 400:
                    raise requests.HTTPError(f"{self.status_code}", response=self)

        class _FakeSession:
            def __init__(self) -> None:
                self.headers = {}

            def request(self, *_args: object, **_kwargs: object) -> object:
                return _FakeResponse(behavior())

            def __enter__(self) -> _FakeSession:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        monkeypatch.setattr(dl, "_public_session", _FakeSession)

    def test_transient_error_then_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"count": 0}

        def behavior() -> int:
            calls["count"] += 1
            if calls["count"] == 1:
                raise requests.exceptions.SSLError("tls reset")
            return 200

        self._fake_session(monkeypatch, behavior)
        monkeypatch.setattr(dl.time, "sleep", lambda _s: None)

        resp = dl.fetch_with_retry("HEAD", "https://example.com/x")

        assert resp.status_code == 200
        assert calls["count"] == 2

    def test_deterministic_client_error_fails_immediately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._fake_session(monkeypatch, lambda: 404)
        sleeps: list[float] = []
        monkeypatch.setattr(dl.time, "sleep", sleeps.append)

        with pytest.raises(RuntimeError, match="HTTP 404"):
            dl.fetch_with_retry("GET", "https://example.com/x")

        assert sleeps == []

    def test_exhausted_retries_raise_classified_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._fake_session(
            monkeypatch,
            lambda: (_ for _ in ()).throw(requests.exceptions.SSLError("tls reset")),
        )
        monkeypatch.setattr(dl.time, "sleep", lambda _s: None)

        with pytest.raises(RuntimeError, match="after 3 attempts"):
            dl.fetch_with_retry("HEAD", "https://example.com/x", retries=3)


class TestAria2cPoliteness:
    def test_batch_command_uses_single_connection_per_server(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict[str, list[str]] = {}

        def _fake_run(cmd: list[str], **_kwargs: object):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setenv("GMLST_DOWNLOAD_RETRY_ROUNDS", "0")  # fake writes no files
        monkeypatch.setattr(dl.shutil, "which", lambda _name: "/usr/bin/aria2c")
        monkeypatch.setattr(dl.subprocess, "run", _fake_run)

        # Destinations do not exist, so both are pending and the fake runner
        # records the aria2c command (it writes no files; the success counts
        # are irrelevant for this assertion).
        pairs = [
            (f"https://example.com/{name}", tmp_path / name)
            for name in ("a.tfa", "b.tfa")
        ]

        dl.download_files_batch(pairs, tool="aria2c")

        cmd = captured["cmd"]
        assert "--max-connection-per-server=1" in cmd
        assert "--split=1" in cmd
        assert "--max-connection-per-server=2" not in cmd
        assert "--split=2" not in cmd

    def test_fetch_json_throttles_each_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        throttle_calls: list[str] = []

        class _FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"ok": True}

        class _FakeSession:
            def __init__(self) -> None:
                self.headers = {}

            def get(self, *_args: object, **_kwargs: object) -> object:
                return _FakeResponse()

            def __enter__(self) -> _FakeSession:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        monkeypatch.setattr(dl, "_public_session", _FakeSession)
        monkeypatch.setattr(
            dl, "_throttle_request", lambda: throttle_calls.append("called")
        )

        assert dl.fetch_json("https://example.com/api") == {"ok": True}
        assert throttle_calls == ["called"]
