"""Tests for cache root resolution and legacy migration in DatabaseCache."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from gmlst.database.cache import (
    DatabaseCache,
    _merge_move,
    _resolve_cache_root,
)

ENV_VARS = ("GMLST_CACHE_DIR", "CONDA_PREFIX", "VIRTUAL_ENV", "XDG_DATA_HOME")


class TestResolveCacheRoot:
    def _clear_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ENV_VARS:
            monkeypatch.delenv(var, raising=False)

    def test_gmlst_cache_dir_env_takes_priority(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("GMLST_CACHE_DIR", str(tmp_path / "custom"))
        monkeypatch.setenv("CONDA_PREFIX", str(tmp_path / "conda"))
        monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "venv"))
        assert _resolve_cache_root() == tmp_path / "custom"

    def test_xdg_data_home_used_when_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdgdata"))
        assert _resolve_cache_root() == tmp_path / "xdgdata" / "gmlst"

    def test_default_is_shared_local_share(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))
        # Path.home() caches nothing but reads HOME lazily on POSIX.
        if sys.platform != "win32":
            assert _resolve_cache_root() == tmp_path / ".local" / "share" / "gmlst"

    def test_conda_prefix_no_longer_isolates_cache(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """pixi/conda environments must share the user-wide data root."""
        self._clear_env(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CONDA_PREFIX", str(tmp_path / "pixi" / "envs" / "default"))
        if sys.platform != "win32":
            assert _resolve_cache_root() == tmp_path / ".local" / "share" / "gmlst", (
                "CONDA_PREFIX must not redirect the cache into the environment"
            )

    def test_virtualenv_no_longer_isolates_cache(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "venv"))
        if sys.platform != "win32":
            assert _resolve_cache_root() == tmp_path / ".local" / "share" / "gmlst", (
                "VIRTUAL_ENV must not redirect the cache into the environment"
            )

    def test_explicit_root_skips_resolution(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self._clear_env(monkeypatch)
        explicit = tmp_path / "explicit"
        cache = DatabaseCache(root=explicit)
        assert cache.root == explicit
        assert cache.root.exists()


class TestLegacyMigration:
    def _setup_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> tuple[Path, Path]:
        """Point HOME/XDG at a sandbox and return (home, conda_prefix)."""
        for var in ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        conda_prefix = tmp_path / "pixi" / "envs" / "default"
        monkeypatch.setenv("CONDA_PREFIX", str(conda_prefix))
        return home, conda_prefix

    def test_migrates_conda_prefix_cache_into_shared_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home, conda_prefix = self._setup_home(monkeypatch, tmp_path)
        legacy = conda_prefix / "share" / "gmlst"
        (legacy / "pubmlst" / "ecoli_1").mkdir(parents=True)
        (legacy / "pubmlst" / "ecoli_1" / ".meta.json").write_text("{}")

        root = _resolve_cache_root()
        assert root == home / ".local" / "share" / "gmlst"
        assert (root / "pubmlst" / "ecoli_1" / ".meta.json").exists()
        assert not legacy.exists(), "empty legacy dir should be removed"

    def test_merges_all_legacy_roots(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home, conda_prefix = self._setup_home(monkeypatch, tmp_path)
        conda_legacy = conda_prefix / "share" / "gmlst" / "cgmlst"
        conda_legacy.mkdir(parents=True)
        home_cache = home / ".cache" / "gmlst" / "_catalog"
        home_cache.mkdir(parents=True)
        (home_cache / "pubmlst.json").write_text("{}")

        root = _resolve_cache_root()
        assert (root / "cgmlst").is_dir()
        assert (root / "_catalog" / "pubmlst.json").exists()

    def test_skips_migration_when_shared_root_has_data(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home, conda_prefix = self._setup_home(monkeypatch, tmp_path)
        legacy = conda_prefix / "share" / "gmlst" / "pubmlst"
        legacy.mkdir(parents=True)
        shared = home / ".local" / "share" / "gmlst"
        (shared / "local").mkdir(parents=True)

        root = _resolve_cache_root()
        assert root == shared
        assert legacy.exists(), "existing data must not be touched"
        assert not (shared / "pubmlst").exists()

    def test_file_conflict_keeps_destination(
        self,
        tmp_path: Path,
    ) -> None:
        src_dir = tmp_path / "src"
        dest_dir = tmp_path / "dest"
        (src_dir / "_catalog").mkdir(parents=True)
        (dest_dir / "_catalog").mkdir(parents=True)
        (src_dir / "_catalog" / "pubmlst.json").write_text('{"stale": true}')
        (dest_dir / "_catalog" / "pubmlst.json").write_text('{"fresh": true}')
        (src_dir / "_catalog" / "enterobase.json").write_text("{}")

        _merge_move(src_dir, dest_dir)

        assert (dest_dir / "_catalog" / "pubmlst.json").read_text() == '{"fresh": true}'
        assert (dest_dir / "_catalog" / "enterobase.json").exists()
        # conflicting source file is left in place, never deleted
        assert (src_dir / "_catalog" / "pubmlst.json").exists()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="ownership check requires os.geteuid (POSIX)",
    )
    def test_skips_legacy_root_owned_by_another_user(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home, conda_prefix = self._setup_home(monkeypatch, tmp_path)
        legacy = conda_prefix / "share" / "gmlst"
        legacy.mkdir(parents=True)
        # Pretend we are a different user than the directory owner.
        real_uid = os.geteuid()
        monkeypatch.setattr(os, "geteuid", lambda: real_uid + 1)

        root = _resolve_cache_root()
        assert root == home / ".local" / "share" / "gmlst"
        assert legacy.exists(), "other users' data must not be moved"

    def test_migration_via_database_cache_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home, conda_prefix = self._setup_home(monkeypatch, tmp_path)
        legacy = conda_prefix / "share" / "gmlst" / "local" / "custom_1"
        legacy.mkdir(parents=True)

        cache = DatabaseCache()
        assert cache.root == home / ".local" / "share" / "gmlst"
        assert (cache.root / "local" / "custom_1").is_dir()

    def test_migration_not_triggered_when_gmlst_cache_dir_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home, conda_prefix = self._setup_home(monkeypatch, tmp_path)
        legacy = conda_prefix / "share" / "gmlst" / "pubmlst"
        legacy.mkdir(parents=True)
        override = tmp_path / "override"
        monkeypatch.setenv("GMLST_CACHE_DIR", str(override))

        assert _resolve_cache_root() == override
        assert legacy.exists(), "explicit override must not migrate anything"
