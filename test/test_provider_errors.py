#!/usr/bin/env python3
"""Behavior tests for provider network and parsing error handling.

Replaces the previous inspect.getsource() string-matching tests with real
behavior tests that mock network calls and verify actual error handling.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from gmlst.database.providers.cgmlst import CgmlstProvider
from gmlst.database.providers.enterobase import EnterobaseProvider

# ---------------------------------------------------------------------------
# cgMLST.org provider — network + parsing error handling
# ---------------------------------------------------------------------------


class TestCgmlstErrorHandling:
    """Test cgmlst provider error handling through real behavior."""

    def test_fetch_schema_status_raises_runtime_error_on_network_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_fetch_schema_status wraps requests errors as RuntimeError."""
        from gmlst.database.providers import cgmlst

        def raise_connection_error(url: str, **kwargs: object) -> object:
            raise requests.ConnectionError("simulated DNS failure")

        monkeypatch.setattr("requests.get", raise_connection_error)

        with pytest.raises(RuntimeError, match="Failed to fetch cgMLST schema status"):
            cgmlst._fetch_schema_status("Abaumannii")

    def test_download_scheme_rejects_unknown_scheme(self, tmp_path: Path) -> None:
        """download_scheme raises ValueError for schemes not in the catalog."""
        provider = CgmlstProvider()

        with pytest.raises(ValueError, match="Unknown cgMLST scheme"):
            provider.download_scheme("nonexistent_1", tmp_path)

    def test_download_scheme_raises_runtime_error_on_corrupt_zip(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Corrupt ZIP archive is caught and re-raised as RuntimeError."""

        # Create a corrupt file masquerading as a valid ZIP.
        zip_path = tmp_path / "abaumannii_1.zip"
        zip_path.write_bytes(b"this is definitely not a ZIP file")

        # Force the code to skip download and attempt extraction.
        monkeypatch.setattr(
            "gmlst.database.providers.cgmlst._has_valid_zip", lambda _p: True
        )

        provider = CgmlstProvider()

        with pytest.raises(RuntimeError, match="Invalid ZIP"):
            provider.download_scheme(
                "abaumannii_1",
                tmp_path,
                download_tool="requests",
            )


# ---------------------------------------------------------------------------
# Enterobase provider — decompression + HTML format error handling
# ---------------------------------------------------------------------------


class TestEnterobaseErrorHandling:
    """Test enterobase provider error handling through real behavior."""

    def test_download_scheme_raises_runtime_error_on_bad_gzip(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-gzip .fasta.gz file triggers RuntimeError, not a raw crash."""
        provider = EnterobaseProvider()

        # Stub _get_loci so we control the locus list.
        monkeypatch.setattr(provider, "_get_loci", lambda _dir: ["test_locus"])

        # Stub network-dependent helpers.
        monkeypatch.setattr(
            "gmlst.database.providers.enterobase.download_required_files",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "gmlst.database.providers.enterobase._head_remote_file",
            lambda _url: {"etag": "", "last_modified": "", "content_length": ""},
        )
        monkeypatch.setattr(provider, "_download_profiles", lambda *a, **k: None)

        # Create a corrupt .fasta.gz that will fail gzip decompression.
        gz_path = tmp_path / "test_locus.fasta.gz"
        gz_path.write_bytes(b"not gzip data")

        with pytest.raises(RuntimeError, match="Failed to decompress test_locus"):
            provider.download_scheme(
                "test_scheme",
                tmp_path,
                extra={"directory": "test.dir"},
            )

    def test_count_loci_returns_zero_on_forbidden(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_count_loci returns 0 on HTTP 403 instead of crashing."""
        provider = EnterobaseProvider()

        fake_resp = MagicMock()
        fake_resp.status_code = 403

        monkeypatch.setattr("requests.get", lambda *a, **k: fake_resp)

        result = provider._count_loci("senterica.cgMLST")
        assert result == 0

    def test_count_loci_returns_zero_on_empty_directory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_count_loci returns 0 when the HTML listing has no .fasta.gz links."""
        provider = EnterobaseProvider()

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.raise_for_status = lambda: None
        fake_resp.text = "<html><body>No files here.</body></html>"

        monkeypatch.setattr("requests.get", lambda *a, **k: fake_resp)

        result = provider._count_loci("senterica.cgMLST")
        assert result == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
