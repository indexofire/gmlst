"""Tests for gmlst.utils shared helpers."""

from __future__ import annotations

import gzip
from pathlib import Path

from gmlst.utils import open_text


def test_open_text_accepts_path_plain(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hello\n")

    with open_text(target) as handle:
        assert handle.read() == "hello\n"


def test_open_text_accepts_str_path_plain(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hello\n")

    with open_text(str(target)) as handle:
        assert handle.read() == "hello\n"


def test_open_text_accepts_str_path_gzip(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt.gz"
    with gzip.open(target, "wt") as handle:
        handle.write("compressed hello\n")

    with open_text(str(target)) as handle:
        assert handle.read() == "compressed hello\n"
