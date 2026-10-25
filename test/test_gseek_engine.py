"""Tests for the optional gseek facade and lazy import policy."""

from __future__ import annotations

import subprocess
import sys

import pytest

from gmlst.aligners import get_aligner
from gmlst.aligners.blastn import BlastnAligner
from gmlst.aligners.minimap2 import Minimap2Aligner


def test_legacy_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMLST_ENGINE", raising=False)
    assert isinstance(get_aligner("blastn"), BlastnAligner)


def test_gseek_wraps_blastn(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("gseek")
    from gmlst.gseek_engine import GseekAligner

    monkeypatch.setenv("GMLST_ENGINE", "gseek")
    assert isinstance(get_aligner("blastn"), GseekAligner)


def test_other_backends_stay_legacy_in_gseek_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("gseek")
    monkeypatch.setenv("GMLST_ENGINE", "gseek")
    assert isinstance(get_aligner("minimap2"), Minimap2Aligner)


def test_invalid_engine_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMLST_ENGINE", "fastest")
    with pytest.raises(RuntimeError, match="unknown GMLST_ENGINE"):
        get_aligner("blastn")


def test_legacy_import_does_not_require_gseek() -> None:
    code = """
import sys
class Blocker:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "gseek" or fullname.startswith("gseek."):
            raise ImportError("gseek blocked")
sys.meta_path.insert(0, Blocker())
from gmlst.aligners import get_aligner
assert type(get_aligner("blastn")).__name__ == "BlastnAligner"
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
