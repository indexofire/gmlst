"""Tests for the SSRF guard in :mod:`gmlst.database.url_guard`."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from gmlst.database.url_guard import UrlGuardError, assert_public_url

# ---------------------------------------------------------------------------
# Happy path: public URLs are accepted
# ---------------------------------------------------------------------------


def test_assert_public_url_allows_https() -> None:
    # Should not raise. PubMLST is the canonical public BIGSdb instance.
    assert_public_url("https://rest.pubmlst.org/db")


def test_assert_public_url_allows_http_public() -> None:
    assert_public_url("http://example.com/")


# ---------------------------------------------------------------------------
# Blocked literal IPs
# ---------------------------------------------------------------------------


def test_assert_public_url_blocks_localhost() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("http://127.0.0.1/")


def test_assert_public_url_blocks_localhost_name_via_dns() -> None:
    # "localhost" is a hostname; we mock DNS to return the loopback IP.
    with patch("gmlst.database.url_guard.socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))
        ]
        with pytest.raises(UrlGuardError):
            assert_public_url("http://localhost/")


def test_assert_public_url_blocks_metadata() -> None:
    # AWS / GCP / Azure cloud metadata endpoint
    with pytest.raises(UrlGuardError):
        assert_public_url("http://169.254.169.254/latest/meta-data/")


def test_assert_public_url_blocks_private_10() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("http://10.0.0.1/")


def test_assert_public_url_blocks_private_192() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("http://192.168.1.1/")


def test_assert_public_url_blocks_private_172() -> None:
    # 172.16.0.0/12 is private; 172.32.x is NOT (sanity for boundary).
    with pytest.raises(UrlGuardError):
        assert_public_url("http://172.16.5.5/")


def test_assert_public_url_blocks_ipv6_loopback() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("http://[::1]/")


def test_assert_public_url_blocks_ipv6_link_local() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("http://[fe80::1]/")


def test_assert_public_url_blocks_unspecified() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("http://0.0.0.0/")


# ---------------------------------------------------------------------------
# Scheme validation
# ---------------------------------------------------------------------------


def test_assert_public_url_rejects_file_scheme() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("file:///etc/passwd")


def test_assert_public_url_rejects_ftp_scheme() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("ftp://example.com/file")


def test_assert_public_url_rejects_gopher_scheme() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("gopher://example.com/")


# ---------------------------------------------------------------------------
# allow= bypass for the private-BIGSdb workflow
# ---------------------------------------------------------------------------


def test_assert_public_url_allow_bypass() -> None:
    # With allow={"127.0.0.1"}, the loopback literal is permitted.
    assert_public_url("http://127.0.0.1/", allow={"127.0.0.1"})


def test_assert_public_url_allow_bypass_is_case_insensitive() -> None:
    assert_public_url("http://127.0.0.1/", allow={"127.0.0.1"})


def test_assert_public_url_allow_bypass_hostname() -> None:
    # Allow-listing by hostname (no DNS lookup needed) should also work.
    assert_public_url("http://my.local.bigsdb/", allow={"my.local.bigsdb"})


def test_assert_public_url_allow_does_not_open_other_hosts() -> None:
    # Allowing one host must not whitelist an unrelated blocked host.
    with pytest.raises(UrlGuardError):
        assert_public_url("http://10.0.0.1/", allow={"127.0.0.1"})


# ---------------------------------------------------------------------------
# DNS resolution behaviour
# ---------------------------------------------------------------------------


def test_assert_public_url_blocks_hostname_resolving_only_private() -> None:
    fake_records = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.1.2.3", 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.0.1", 0)),
    ]
    with patch("gmlst.database.url_guard.socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = fake_records
        with pytest.raises(UrlGuardError):
            assert_public_url("http://internal.lab/")


def test_assert_public_url_allows_hostname_with_mixed_ips() -> None:
    # If a hostname resolves to at least one public IP, accept it (dual-stack
    # hosts that include a blocked IPv6 alongside a public IPv4 are OK).
    fake_records = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0)),
    ]
    with patch("gmlst.database.url_guard.socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = fake_records
        assert_public_url("http://dual-stack.example/")


def test_assert_public_url_fails_closed_on_dns_failure() -> None:
    with patch("gmlst.database.url_guard.socket.getaddrinfo") as mock_gai:
        mock_gai.side_effect = OSError("DNS lookup failed")
        with pytest.raises(UrlGuardError):
            assert_public_url("http://nonexistent.invalid/")


def test_assert_public_url_fails_closed_on_empty_resolution() -> None:
    with patch("gmlst.database.url_guard.socket.getaddrinfo") as mock_gai:
        mock_gai.return_value = []
        with pytest.raises(UrlGuardError):
            assert_public_url("http://empty.invalid/")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_assert_public_url_rejects_url_without_host() -> None:
    with pytest.raises(UrlGuardError):
        assert_public_url("https:///path-only")


def test_assert_public_url_blocks_ipv4_mapped_ipv6_loopback() -> None:
    # ::ffff:127.0.0.1 is still loopback.
    with pytest.raises(UrlGuardError):
        assert_public_url("http://[::ffff:127.0.0.1]/")


# ---------------------------------------------------------------------------
# Integration: download.py chokepoints call the guard
# ---------------------------------------------------------------------------


def test_fetch_json_calls_guard_and_blocks_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SSRF guard in fetch_json must fire before any HTTP call."""
    import gmlst.database.download as dl

    # If the guard is bypassed, this would attempt a real HTTP request to
    # localhost; ensure that never happens.
    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("requests.get should not be called for blocked URL")

    monkeypatch.setattr("requests.get", _fail_if_called)

    with pytest.raises(UrlGuardError):
        dl.fetch_json("http://127.0.0.1:9000/secret", retries=1, retry_delay=0)


def test_download_file_calls_guard_and_blocks_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """The SSRF guard in download_file must fire before any backend runs."""
    import gmlst.database.download as dl

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("subprocess.run should not be called for blocked URL")

    monkeypatch.setattr(dl.subprocess, "run", _fail_if_called)
    monkeypatch.setattr(dl.shutil, "which", lambda _name: "/usr/bin/aria2c")

    with pytest.raises(UrlGuardError):
        dl.download_file(
            "http://169.254.169.254/latest/meta-data/",
            tmp_path / "out.bin",
            tool="aria2c",
        )


def test_download_file_requests_calls_guard_and_blocks_private(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """The SSRF guard in download_file_requests must fire first."""
    import gmlst.database.download as dl

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("requests.get should not be called for blocked URL")

    monkeypatch.setattr("requests.get", _fail_if_called)

    with pytest.raises(UrlGuardError):
        dl.download_file_requests(
            "http://10.0.0.5/file",
            tmp_path / "out.bin",
            retries=1,
            retry_delay=0,
        )


# ---------------------------------------------------------------------------
# Opt-in bypass via GMLST_ALLOW_PRIVATE_URLS
# ---------------------------------------------------------------------------


def test_assert_public_url_respects_env_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    """When GMLST_ALLOW_PRIVATE_URLS is set, the guard must return without checking."""
    import gmlst.database.url_guard as guard

    monkeypatch.setenv("GMLST_ALLOW_PRIVATE_URLS", "1")
    monkeypatch.setattr(guard, "_ALLOW_PRIVATE", True)

    # Should NOT raise, even though the URL is private.
    guard.assert_public_url("http://127.0.0.1/")
    guard.assert_public_url("http://169.254.169.254/latest/meta-data/")


def test_assert_public_url_env_bypass_defaults_off() -> None:
    # By default, the guard must be active (the env var is unset in tests).
    with pytest.raises(UrlGuardError):
        assert_public_url("http://127.0.0.1/")
