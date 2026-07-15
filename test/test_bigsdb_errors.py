#!/usr/bin/env python3
"""Behavior tests for bigsdb provider error handling and correctness.

Replaces the previous inspect.getsource() string-matching tests with real
behavior tests that exercise _resolve_seqdef_url suffix handling and
_get_json retry behavior.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

import gmlst.database.providers.bigsdb as bigsdb
from gmlst.database.providers.bigsdb import BigSdbProvider

# ---------------------------------------------------------------------------
# _resolve_seqdef_url — suffix handling and error paths
# ---------------------------------------------------------------------------


class TestResolveSeqdefUrl:
    """Verify _resolve_seqdef_url behavior through actual method calls."""

    def test_strips_numeric_suffix_and_resolves(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Suffixed scheme name (e.g. 'testorg_1') resolves via base name."""
        provider = BigSdbProvider(
            name="pubmlst",
            base_url="https://rest.pubmlst.org/db",
            label="PubMLST",
        )

        def fake_get_json(url: str, headers: dict[str, str] | None = None):
            return [
                {
                    "name": "testorg",
                    "description": "Test Organism REST API",
                    "databases": [
                        {
                            "name": "pubmlst_testorg_seqdef",
                            "href": "https://rest.pubmlst.org/db/pubmlst_testorg_seqdef",
                        }
                    ],
                }
            ]

        monkeypatch.setattr("gmlst.database.providers.bigsdb._get_json", fake_get_json)

        # The '_1' suffix should be stripped so 'testorg' matches the database.
        href, db_name = provider._resolve_seqdef_url("testorg_1")
        assert db_name == "pubmlst_testorg_seqdef"
        assert href == "https://rest.pubmlst.org/db/pubmlst_testorg_seqdef"

    def test_raises_value_error_with_helpful_hint_when_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unresolvable scheme raises ValueError pointing to 'gmlst scheme list'."""
        provider = BigSdbProvider(
            name="pubmlst",
            base_url="https://rest.pubmlst.org/db",
            label="PubMLST",
        )

        monkeypatch.setattr(
            "gmlst.database.providers.bigsdb._get_json", lambda _u, **_k: []
        )

        with pytest.raises(ValueError, match="gmlst scheme list"):
            provider._resolve_seqdef_url("nonexistent_1")


# ---------------------------------------------------------------------------
# _get_json — retry behavior via fetch_json delegation
# ---------------------------------------------------------------------------


class TestGetJsonRetry:
    """Verify _get_json retries transient network failures."""

    def test_retries_and_succeeds_on_transient_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_get_json delegates to fetch_json which retries on ConnectionError."""
        # Bypass DNS resolution check inside fetch_json.
        monkeypatch.setattr(
            "gmlst.database.download.assert_public_url", lambda _url: None
        )
        # Skip real sleeps between retries.
        monkeypatch.setattr("gmlst.database.download.time.sleep", lambda _s: None)

        call_count = 0

        def flaky_get(url: str, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.ConnectionError("simulated transient failure")
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = lambda: {"databases": []}
            return mock_resp

        monkeypatch.setattr("requests.get", flaky_get)

        result = bigsdb._get_json("https://rest.pubmlst.org/db")

        assert result == {"databases": []}
        assert call_count == 3  # 2 failures + 1 success

    def test_raises_runtime_error_after_exhausting_retries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_get_json raises RuntimeError when all retries are exhausted."""
        monkeypatch.setattr(
            "gmlst.database.download.assert_public_url", lambda _url: None
        )
        monkeypatch.setattr("gmlst.database.download.time.sleep", lambda _s: None)

        def always_fail(url: str, **kwargs: object) -> object:
            raise requests.ConnectionError("persistent network failure")

        monkeypatch.setattr("requests.get", always_fail)

        with pytest.raises(RuntimeError, match="JSON fetch failed"):
            bigsdb._get_json("https://rest.pubmlst.org/db")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
