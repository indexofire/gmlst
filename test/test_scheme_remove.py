from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gmlst.cli import main
from gmlst.database.cache import DatabaseCache


def _make_cached_scheme(cache: DatabaseCache, scheme: str, provider: str) -> Path:
    scheme_dir = cache.scheme_dir(scheme, provider)
    scheme_dir.mkdir(parents=True)
    (scheme_dir / "abc.tfa").write_text(">abc_1\nATGC\n")
    (scheme_dir / f"{scheme}.txt").write_text("ST\tabc\n1\t1\n")
    (scheme_dir / ".meta.json").write_text(
        json.dumps(
            {
                "scheme": scheme,
                "provider": provider,
                "scheme_type": "mlst",
                "loci": ["abc"],
            }
        )
    )
    return scheme_dir


def _write_local_catalog(cache: DatabaseCache, names: list[str]) -> Path:
    catalog_path = cache.local_catalog_path()
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    schemes = [
        {
            "scheme_name": name,
            "display_name": name,
            "organism": f"Custom (ecoli_1) {name}",
            "scheme_type": "mlst",
            "n_loci": 1,
            "provider": "local",
            "extra": {"based_on": "ecoli_1", "custom": True},
        }
        for name in names
    ]
    payload = {
        "provider": "local",
        "scheme_type": "mlst",
        "updated_at": "2026-01-01T00:00:00Z",
        "count": len(schemes),
        "schemes": schemes,
    }
    catalog_path.write_text(json.dumps(payload))
    return catalog_path


def _local_catalog_names(catalog_path: Path) -> list[str]:
    data = json.loads(catalog_path.read_text())
    return [s["scheme_name"] for s in data["schemes"]]


def _parse_trailing_json(output: str) -> dict:
    return json.loads(output[output.index("{") :])


def test_scheme_remove_custom_scheme_success(tmp_path: Path) -> None:
    runner = CliRunner()
    cache = DatabaseCache(tmp_path)
    scheme_dir = _make_cached_scheme(cache, "custom_1", "local")
    catalog_path = _write_local_catalog(cache, ["custom_1", "custom_2"])

    result = runner.invoke(
        main,
        ["scheme", "remove", "custom_1", "--yes", "--cache-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert not scheme_dir.exists()
    assert _local_catalog_names(catalog_path) == ["custom_2"]
    assert "Removed custom_1" in result.output
    assert "{" not in result.output.split("Removed")[0]


def test_scheme_remove_prompt_declined_keeps_scheme(tmp_path: Path) -> None:
    runner = CliRunner()
    cache = DatabaseCache(tmp_path)
    scheme_dir = _make_cached_scheme(cache, "custom_1", "local")
    catalog_path = _write_local_catalog(cache, ["custom_1"])

    result = runner.invoke(
        main,
        ["scheme", "remove", "custom_1", "--cache-dir", str(tmp_path)],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "Remove cached scheme 'custom_1' (local)?" in result.output
    assert "Aborted." in result.output
    assert scheme_dir.exists()
    assert _local_catalog_names(catalog_path) == ["custom_1"]


def test_scheme_remove_json_envelope(tmp_path: Path) -> None:
    runner = CliRunner()
    cache = DatabaseCache(tmp_path)
    scheme_dir = _make_cached_scheme(cache, "custom_1", "local")
    _write_local_catalog(cache, ["custom_1"])

    result = runner.invoke(
        main,
        [
            "scheme",
            "remove",
            "custom_1",
            "--yes",
            "--format",
            "json",
            "--cache-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert not scheme_dir.exists()
    payload = _parse_trailing_json(result.output)
    assert payload["schema_version"] == "gmlst-scheme-op-v1"
    data = payload["data"]
    assert data["scheme"] == "custom_1"
    assert data["provider"] == "local"
    assert data["path"] == str(scheme_dir)
    assert data["removed"] is True
    # Status messages precede the JSON document; confirmation happens first.
    assert "Cached scheme to remove" in result.output


def test_scheme_remove_not_found(tmp_path: Path) -> None:
    runner = CliRunner()
    DatabaseCache(tmp_path)

    result = runner.invoke(
        main,
        ["scheme", "remove", "ghost_1", "--yes", "--cache-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "Scheme 'ghost_1' not found in cache." in result.output
    assert "Traceback" not in result.output


def test_scheme_remove_wrong_provider_not_found(tmp_path: Path) -> None:
    runner = CliRunner()
    cache = DatabaseCache(tmp_path)
    _make_cached_scheme(cache, "ecoli_1", "pubmlst")

    result = runner.invoke(
        main,
        [
            "scheme",
            "remove",
            "ecoli_1",
            "-p",
            "local",
            "--yes",
            "--cache-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "not found in cache for provider 'local'" in result.output


def test_scheme_remove_invalid_provider(tmp_path: Path) -> None:
    runner = CliRunner()
    cache = DatabaseCache(tmp_path)
    _make_cached_scheme(cache, "ecoli_1", "pubmlst")

    result = runner.invoke(
        main,
        [
            "scheme",
            "remove",
            "ecoli_1",
            "-p",
            "bogus",
            "--yes",
            "--cache-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "Unknown provider 'bogus'" in result.output


def test_scheme_remove_pubmlst_scheme_keeps_local_catalog(tmp_path: Path) -> None:
    runner = CliRunner()
    cache = DatabaseCache(tmp_path)
    scheme_dir = _make_cached_scheme(cache, "ecoli_1", "pubmlst")
    catalog_path = _write_local_catalog(cache, ["custom_1"])
    local_dir = _make_cached_scheme(cache, "custom_1", "local")

    result = runner.invoke(
        main,
        [
            "scheme",
            "remove",
            "ecoli_1",
            "-p",
            "pubmlst",
            "--yes",
            "--cache-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert not scheme_dir.exists()
    assert local_dir.exists()
    assert _local_catalog_names(catalog_path) == ["custom_1"]
    assert "Removed ecoli_1" in result.output


def test_scheme_remove_requires_scheme_name(tmp_path: Path) -> None:
    runner = CliRunner()
    DatabaseCache(tmp_path)

    result = runner.invoke(main, ["scheme", "remove", "--cache-dir", str(tmp_path)])

    assert result.exit_code == 2
    assert "Scheme name is required." in result.output
