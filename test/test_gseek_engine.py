"""Tests for the gseek/legacy alignment engine switch."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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


def test_gseek_align_passes_threads_to_gseek(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """-t/--threads must reach gseek.align (regression: it was dropped).

    With threads silently defaulting to 1 in gseek, the gseek engine ran
    minimap2 single-cored while the legacy path honored -t (3m48s vs
    1m20s on a 3002-locus scheme with -t 16).
    """
    import types

    from gmlst import gseek_engine

    captured: dict[str, object] = {}

    class _FakeRecords:
        records: list = []

    def _fake_gseek_align(**kwargs):
        captured.update(kwargs)
        return _FakeRecords()

    fake_gseek = types.SimpleNamespace(align=_fake_gseek_align)
    fake_execution = types.SimpleNamespace(ToolResolver=lambda: object())

    def _fake_import(name: str):
        if name == "gseek.execution":
            return fake_execution
        return fake_gseek

    class _FakeLegacy:
        name = "minimap2"
        fasta_emit_cigar = False
        fasta_speed_profile = "default"
        threads = 16

    gseek_engine._resolver.cache_clear()
    monkeypatch.setattr(gseek_engine.importlib, "import_module", _fake_import)
    monkeypatch.setattr(
        "gmlst.readers.sample.SampleInput.from_path",
        lambda _p: types.SimpleNamespace(sample_id="s1"),
    )

    sample_fna = tmp_path / "s1.fna"
    sample_fna.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "alleles.fasta").write_text(">abc_1\nATGC\n")

    gseek_engine._gseek_minimap2(
        sample_fna,
        index_dir,
        ["abc"],
        "fasta",
        _FakeLegacy(),  # type: ignore[arg-type]
        threads=16,
    )

    assert captured.get("threads") == 16
    gseek_engine._resolver.cache_clear()
