"""Security tests for path traversal protection in DatabaseCache.

Verifies that scheme names, providers, and backends are validated before
being joined into filesystem paths, and that the destructive
``shutil.rmtree`` in ``ensure_scheme(force=True)`` can never operate outside
the cache root - even if the upstream identifier validation is bypassed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gmlst.database.cache import DatabaseCache, _validate_scheme_identifier


class TestValidateSchemeIdentifier:
    @pytest.mark.parametrize(
        "value",
        [
            "saureus_1",
            "pubmlst",
            "vp_scheme",
            "new_scheme",
            "lmonocytogenes_1",
            "vparahaemolyticus_3",
            "blastn",
            "minimap2",
            "cgmlst",
            "enterobase",
            "local",
            "labdb",
            "scheme.with.dots",
            "scheme-with-dashes",
            "a",
            "A",
            "1abc",
            "_underscore",
        ],
    )
    def test_accepts_valid_identifiers(self, value: str) -> None:
        assert _validate_scheme_identifier(value, "test") == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "..",
            "../",
            "..\\",
            "../etc",
            "..\\windows",
            "/..",
            "/etc/passwd",
            "/absolute/path",
            "foo/../bar",
            "foo/..",
            "./hidden",
            ".hidden",
            ".",
            "scheme/name",
            "scheme\\name",
            "scheme\nname",
            "scheme name",
            "a..b",
            "ab..",
            "x\x00y",
            "\x00",
            "C:foo",
            "scheme;rm",
            "scheme$var",
            "scheme`cmd`",
        ],
    )
    def test_rejects_dangerous_identifiers(self, value: str) -> None:
        with pytest.raises(ValueError, match="Invalid test:"):
            _validate_scheme_identifier(value, "test")

    def test_error_message_contains_label_and_value(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            _validate_scheme_identifier("../etc", "scheme name")
        message = str(exc_info.value)
        assert "scheme name" in message
        assert "'../etc'" in message


class TestSchemeDirValidation:
    def test_valid_name_and_provider(self, tmp_path: Path) -> None:
        cache = DatabaseCache(tmp_path)
        result = cache.scheme_dir("saureus_1", "pubmlst")
        assert result == tmp_path / "pubmlst" / "saureus_1"

    def test_default_provider_works(self, tmp_path: Path) -> None:
        cache = DatabaseCache(tmp_path)
        assert cache.scheme_dir("saureus_1") == tmp_path / "pubmlst" / "saureus_1"

    @pytest.mark.parametrize(
        "name",
        ["../etc", "../../", "/etc/passwd", "..", ".", ".hidden", "a/b", "a..b"],
    )
    def test_rejects_traversal_name(self, tmp_path: Path, name: str) -> None:
        cache = DatabaseCache(tmp_path)
        with pytest.raises(ValueError, match="Invalid scheme name:"):
            cache.scheme_dir(name, "pubmlst")

    @pytest.mark.parametrize(
        "provider",
        ["../", "/absolute", "..", ".", ".hidden", "a/b", "p..mlst"],
    )
    def test_rejects_traversal_provider(self, tmp_path: Path, provider: str) -> None:
        cache = DatabaseCache(tmp_path)
        with pytest.raises(ValueError, match="Invalid provider:"):
            cache.scheme_dir("saureus_1", provider)

    def test_empty_name_rejected(self, tmp_path: Path) -> None:
        cache = DatabaseCache(tmp_path)
        with pytest.raises(ValueError, match="Invalid scheme name:"):
            cache.scheme_dir("", "pubmlst")

    def test_empty_provider_rejected(self, tmp_path: Path) -> None:
        cache = DatabaseCache(tmp_path)
        with pytest.raises(ValueError, match="Invalid provider:"):
            cache.scheme_dir("saureus_1", "")

    def test_null_byte_in_name_rejected(self, tmp_path: Path) -> None:
        cache = DatabaseCache(tmp_path)
        with pytest.raises(ValueError, match="contains null byte"):
            cache.scheme_dir("saureus\x00_1", "pubmlst")


class TestIndexDirValidation:
    def test_valid_index_dir(self, tmp_path: Path) -> None:
        cache = DatabaseCache(tmp_path)
        result = cache.index_dir("saureus_1", "blastn", provider="pubmlst")
        assert result == tmp_path / "_indexes" / "pubmlst" / "blastn" / "saureus_1"
        assert result.exists()

    def test_default_provider_works(self, tmp_path: Path) -> None:
        cache = DatabaseCache(tmp_path)
        result = cache.index_dir("saureus_1", "minimap2")
        assert result == tmp_path / "_indexes" / "pubmlst" / "minimap2" / "saureus_1"

    @pytest.mark.parametrize("scheme_name", ["../etc", "/abs", "..", "a/b", "x..y"])
    def test_rejects_traversal_scheme_name(
        self, tmp_path: Path, scheme_name: str
    ) -> None:
        cache = DatabaseCache(tmp_path)
        with pytest.raises(ValueError, match="Invalid scheme name:"):
            cache.index_dir(scheme_name, "blastn")

    @pytest.mark.parametrize("backend", ["../etc", "/abs", "..", "a/b", "x..y"])
    def test_rejects_traversal_backend(self, tmp_path: Path, backend: str) -> None:
        cache = DatabaseCache(tmp_path)
        with pytest.raises(ValueError, match="Invalid backend:"):
            cache.index_dir("saureus_1", backend)

    @pytest.mark.parametrize("provider", ["../", "/abs", "..", "a/b", "p..x"])
    def test_rejects_traversal_provider(self, tmp_path: Path, provider: str) -> None:
        cache = DatabaseCache(tmp_path)
        with pytest.raises(ValueError, match="Invalid provider:"):
            cache.index_dir("saureus_1", "blastn", provider=provider)


class TestEnsureSchemeForceSafety:
    def test_traversal_name_raises_before_any_deletion(self, tmp_path: Path) -> None:
        """Primary defense: identifier validation rejects before rmtree runs."""
        cache = DatabaseCache(tmp_path / "cache")
        # A sibling directory outside the cache root must never be touched.
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "important.txt").write_text("preserve me")

        with pytest.raises(ValueError, match="Invalid scheme name:"):
            cache.ensure_scheme("../outside", provider="pubmlst", force=True)

        assert (outside / "important.txt").exists()
        assert outside.exists()

    def test_traversal_provider_raises_before_any_deletion(
        self, tmp_path: Path
    ) -> None:
        cache = DatabaseCache(tmp_path / "cache")
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "important.txt").write_text("preserve me")

        with pytest.raises(ValueError, match="Invalid provider:"):
            cache.ensure_scheme("saureus_1", provider="../outside", force=True)

        assert (outside / "important.txt").exists()

    def test_defense_in_depth_blocks_rmtree_outside_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Secondary defense: even if scheme_dir were compromised to return
        a path outside the cache root, the resolve().relative_to() check
        must block the rmtree."""
        cache = DatabaseCache(tmp_path / "cache")
        outside = tmp_path / "outside_target"
        outside.mkdir()
        (outside / "important.txt").write_text("preserve me")

        # Simulate a regression or subclass that bypasses validation and
        # points scheme_dir outside the cache root.
        monkeypatch.setattr(
            cache, "scheme_dir", lambda name, provider="pubmlst": outside
        )

        with pytest.raises(ValueError, match="outside cache root"):
            cache.ensure_scheme("anything", force=True)

        assert (outside / "important.txt").exists()
        assert outside.exists()

    def test_force_with_valid_name_still_clears_existing_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression guard: legitimate force=True workflow still works."""
        cache = DatabaseCache(tmp_path)
        scheme_dir = cache.scheme_dir("demo", "pubmlst")
        scheme_dir.mkdir(parents=True)
        (scheme_dir / "stale.marker").write_text("old")

        def fake_download(
            name: str,
            *,
            provider: str,
            scheme_type: str,
            token: str | None,
            download_tool: object,
            max_connections: int | None,
        ) -> None:
            dest = cache.scheme_dir(name, provider)
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "abc.tfa").write_text(">abc_1\nATGC\n")
            (dest / "demo.txt").write_text("ST\tabc\n1\t1\n")
            (dest / ".meta.json").write_text(
                json.dumps(
                    {
                        "scheme": name,
                        "provider": provider,
                        "scheme_type": scheme_type,
                        "loci": ["abc"],
                    }
                )
            )

        monkeypatch.setattr(cache, "_download", fake_download)

        cache.ensure_scheme("demo", provider="pubmlst", force=True)

        assert not (scheme_dir / "stale.marker").exists()
