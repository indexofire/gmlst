"""Tests for cache root resolution in DatabaseCache."""

from __future__ import annotations

from pathlib import Path

import pytest

from gmlst.database.cache import _resolve_cache_root


class TestResolveCacheRoot:
    def _clear_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ("GMLST_CACHE_DIR", "CONDA_PREFIX", "VIRTUAL_ENV"):
            monkeypatch.delenv(var, raising=False)

    def test_gmlst_cache_dir_env_takes_priority(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GMLST_CACHE_DIR", str(tmp_path / "custom"))
        monkeypatch.setenv("CONDA_PREFIX", str(tmp_path / "conda"))
        monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "venv"))
        assert _resolve_cache_root() == tmp_path / "custom"

    def test_conda_prefix_used_when_no_gmlst_cache_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("CONDA_PREFIX", str(tmp_path / "myenv"))
        assert _resolve_cache_root() == tmp_path / "myenv" / "share" / "gmlst"

    def test_virtualenv_used_when_no_conda(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "venv"))
        assert _resolve_cache_root() == tmp_path / "venv" / ".cache" / "gmlst"

    def test_conda_takes_priority_over_virtualenv(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("CONDA_PREFIX", str(tmp_path / "conda"))
        monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "venv"))
        assert _resolve_cache_root() == tmp_path / "conda" / "share" / "gmlst"

    def test_home_fallback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._clear_env(monkeypatch)
        result = _resolve_cache_root()
        assert result == Path.home() / ".cache" / "gmlst"

    def test_explicit_root_skips_resolution(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from gmlst.database.cache import DatabaseCache

        self._clear_env(monkeypatch)
        explicit = tmp_path / "explicit"
        cache = DatabaseCache(root=explicit)
        assert cache.root == explicit
        assert cache.root.exists()
