from __future__ import annotations

import json
from pathlib import Path

from gmlst.database.cache import DatabaseCache
from gmlst.database.download import DownloadTool


class _DummyProviderIncremental:
    def __init__(self) -> None:
        self.called = False
        self.last_scheme_type = ""

    def update_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "mlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict | None = None,
    ) -> bool:
        assert download_tool == "auto"
        assert max_connections is None
        self.called = True
        self.last_scheme_type = scheme_type
        (dest_dir / ".meta.json").write_text(
            json.dumps(
                {
                    "scheme": scheme_name,
                    "provider": "pubmlst",
                    "scheme_type": scheme_type,
                    "loci": ["abc"],
                }
            )
        )
        return False


class _DummyProviderFull:
    def __init__(self) -> None:
        self.download_called = False

    def download_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "mlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict | None = None,
    ) -> None:
        assert download_tool == "auto"
        assert max_connections is None
        self.download_called = True
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "abc.tfa").write_text(">abc_1\nATGC\n")
        (dest_dir / f"{scheme_name}.txt").write_text("ST\tabc\n1\t1\n")
        (dest_dir / ".meta.json").write_text(
            json.dumps(
                {
                    "scheme": scheme_name,
                    "provider": "pubmlst",
                    "scheme_type": scheme_type,
                    "loci": ["abc"],
                }
            )
        )


def test_update_scheme_prefers_provider_incremental(
    monkeypatch, tmp_path: Path
) -> None:
    cache = DatabaseCache(tmp_path)
    scheme_dir = cache.scheme_dir("demo", "pubmlst")
    scheme_dir.mkdir(parents=True)
    (scheme_dir / "abc.tfa").write_text(">abc_1\nATGC\n")
    (scheme_dir / "demo.txt").write_text("ST\tabc\n1\t1\n")
    (scheme_dir / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": "demo",
                "provider": "pubmlst",
                "scheme_type": "mlst",
                "loci": ["abc"],
            }
        )
    )

    provider = _DummyProviderIncremental()
    monkeypatch.setattr("gmlst.database.providers.get_provider", lambda _name: provider)

    scheme, changed = cache.update_scheme("demo", provider="pubmlst")

    assert provider.called is True
    assert changed is False
    assert scheme.name == "demo"


def test_update_scheme_records_update_date_and_keeps_download_date(
    monkeypatch,
    tmp_path: Path,
) -> None:
    cache = DatabaseCache(tmp_path)
    scheme_dir = cache.scheme_dir("demo", "pubmlst")
    scheme_dir.mkdir(parents=True)
    (scheme_dir / "abc.tfa").write_text(">abc_1\nATGC\n")
    (scheme_dir / "demo.txt").write_text("ST\tabc\n1\t1\n")
    (scheme_dir / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": "demo",
                "provider": "pubmlst",
                "scheme_type": "mlst",
                "downloaded_at": "2026-01-01T00:00:00Z",
                "loci": ["abc"],
            }
        )
    )

    provider = _DummyProviderIncremental()
    monkeypatch.setattr("gmlst.database.providers.get_provider", lambda _name: provider)

    _, changed = cache.update_scheme("demo", provider="pubmlst")

    meta = json.loads((scheme_dir / ".meta.json").read_text())
    assert changed is False
    assert meta["downloaded_at"] == "2026-01-01T00:00:00Z"
    assert meta["updated_at"]


def test_update_scheme_downloads_if_missing(monkeypatch, tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    provider = _DummyProviderFull()
    monkeypatch.setattr("gmlst.database.providers.get_provider", lambda _name: provider)

    scheme, changed = cache.update_scheme("new_scheme", provider="pubmlst")

    assert provider.download_called is True
    assert changed is True
    assert scheme.name == "new_scheme"
    meta_file = cache.scheme_dir("new_scheme", "pubmlst") / ".meta.json"
    meta = json.loads(meta_file.read_text())
    assert meta["downloaded_at"]
    assert "updated_at" not in meta


def test_list_cached_includes_update_date(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    scheme_dir = cache.scheme_dir("demo", "pubmlst")
    scheme_dir.mkdir(parents=True)
    (scheme_dir / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": "demo",
                "provider": "pubmlst",
                "scheme_type": "mlst",
                "loci": ["abc", "def"],
                "downloaded_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }
        )
    )

    assert cache.list_cached() == [
        {
            "scheme": "demo",
            "provider": "pubmlst",
            "scheme_type": "mlst",
            "loci": 2,
            "downloaded_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }
    ]


def test_update_scheme_prefers_cached_scheme_type(monkeypatch, tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    scheme_dir = cache.scheme_dir("vp_scheme", "pubmlst")
    scheme_dir.mkdir(parents=True)
    (scheme_dir / "abc.tfa").write_text(">abc_1\nATGC\n")
    (scheme_dir / "vp_scheme.txt").write_text("ST\tabc\n1\t1\n")
    (scheme_dir / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": "vp_scheme",
                "provider": "pubmlst",
                "scheme_type": "cgmlst",
                "loci": ["abc"],
            }
        )
    )

    provider = _DummyProviderIncremental()
    monkeypatch.setattr("gmlst.database.providers.get_provider", lambda _name: provider)

    _, _ = cache.update_scheme("vp_scheme", provider="pubmlst")

    assert provider.last_scheme_type == "cgmlst"


def test_ensure_scheme_force_clears_existing_directory(tmp_path: Path) -> None:
    cache = DatabaseCache(tmp_path)
    scheme_dir = cache.scheme_dir("demo", "pubmlst")
    scheme_dir.mkdir(parents=True)
    (scheme_dir / "stale.marker").write_text("old")
    (scheme_dir / "demo.txt").write_text("ST\tabc\n1\t1\n")
    (scheme_dir / "abc.tfa").write_text(">abc_1\nATGC\n")
    (scheme_dir / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": "demo",
                "provider": "pubmlst",
                "scheme_type": "mlst",
                "loci": ["abc"],
            }
        )
    )

    def fake_download(
        name: str,
        *,
        provider: str,
        scheme_type: str,
        token: str | None,
        download_tool: DownloadTool,
        max_connections: int | None,
    ):
        assert download_tool == "auto"
        assert max_connections is None
        dest = cache.scheme_dir(name, provider)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "abc.tfa").write_text(">abc_1\nATGC\n")
        (dest / "demo.txt").write_text("ST\tabc\n2\t1\n")
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

    cache._download = fake_download  # type: ignore[method-assign]  # monkeypatch private method for test fixture

    cache.ensure_scheme("demo", provider="pubmlst", force=True)

    assert not (scheme_dir / "stale.marker").exists()
