"""Tests for the gseek/legacy alignment engine switch."""

from __future__ import annotations

import subprocess
import sys

import pytest

from gmlst.aligners import get_aligner
from gmlst.aligners.blastn import BlastnAligner


def test_gseek_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("gseek")
    from gmlst.gseek_engine import GseekAligner

    monkeypatch.delenv("GMLST_ENGINE", raising=False)
    assert isinstance(get_aligner("blastn"), GseekAligner)


def test_legacy_mode_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMLST_ENGINE", "legacy")
    assert isinstance(get_aligner("blastn"), BlastnAligner)


def test_gseek_wraps_all_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("gseek")
    from gmlst.gseek_engine import GseekAligner

    monkeypatch.setenv("GMLST_ENGINE", "gseek")
    assert isinstance(get_aligner("blastn"), GseekAligner)
    assert isinstance(get_aligner("minimap2"), GseekAligner)
    assert isinstance(get_aligner("kma"), GseekAligner)
    assert isinstance(get_aligner("nucmer"), GseekAligner)


def test_invalid_engine_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMLST_ENGINE", "fastest")
    with pytest.raises(RuntimeError, match="unknown GMLST_ENGINE"):
        get_aligner("blastn")


def test_default_without_gseek_falls_back_to_legacy() -> None:
    code = """
import sys

class Blocker:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "gseek" or fullname.startswith("gseek."):
            raise ImportError("gseek blocked")

sys.meta_path.insert(0, Blocker())
import os
os.environ.pop("GMLST_ENGINE", None)
from gmlst.aligners import get_aligner
from gmlst.gseek_engine import engine_mode

assert type(get_aligner("blastn")).__name__ == "BlastnAligner"
assert engine_mode() == "legacy"
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "falling back to the legacy alignment engine" in result.stderr


def test_explicit_gseek_without_gseek_raises() -> None:
    code = """
import sys

class Blocker:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "gseek" or fullname.startswith("gseek."):
            raise ImportError("gseek blocked")

sys.meta_path.insert(0, Blocker())
import os
os.environ["GMLST_ENGINE"] = "gseek"
from gmlst.aligners import get_aligner

get_aligner("blastn")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "requires the gseek package" in result.stderr


def test_legacy_import_does_not_require_gseek() -> None:
    code = """
import sys
class Blocker:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "gseek" or fullname.startswith("gseek."):
            raise ImportError("gseek blocked")
sys.meta_path.insert(0, Blocker())
import os
os.environ["GMLST_ENGINE"] = "legacy"
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
