from __future__ import annotations

import json
from pathlib import Path

from gmlst.metadata_io import read_json_metadata, write_json_metadata


def test_read_json_metadata_returns_default_for_missing_or_invalid_file(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.json"
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json")

    assert read_json_metadata(missing, default={"x": 1}) == {"x": 1}
    assert read_json_metadata(invalid, default={"x": 1}) == {"x": 1}


def test_write_json_metadata_creates_parent_and_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "meta.json"

    write_json_metadata(path, {"fingerprint": "abc"})

    assert json.loads(path.read_text()) == {"fingerprint": "abc"}
