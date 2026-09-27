"""TypingOptions carries --guess's shared settings to every scheme route."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from gmlst.commands.typing_options import TypingOptions


def _options() -> TypingOptions:
    return TypingOptions(
        mode="cgmlst",
        backend="kma",
        cgmlst_mode="balanced",
        min_id=91.0,
        min_cov=0.8,
        min_depth=7.0,
        min_join_overlap=3,
        minscore=42.0,
        fmt="json",
        cache_dir=Path("/tmp/c"),
        force_reindex=True,
        no_header=True,
        threads=6,
        max_workers=2,
        count_same_copy=True,
        quiet=True,
        detail=True,
    )


def test_run_scheme_forwards_every_field(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        lambda **kwargs: captured.update(kwargs),
    )
    options = _options()
    sink: list = []

    options.run_scheme(
        samples=(Path("a.fna"),), scheme="x_1", provider="pubmlst", result_sink=sink
    )

    for field in dataclasses.fields(options):
        assert captured[field.name] == getattr(options, field.name), field.name
    assert captured["samples"] == (Path("a.fna"),)
    assert captured["scheme"] == "x_1"
    assert captured["provider"] == "pubmlst"
    assert captured["result_sink"] is sink


def test_run_scheme_collects_instead_of_writing(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "gmlst.commands.typing._run_mlst_like_typing",
        lambda **kwargs: captured.update(kwargs),
    )

    _options().run_scheme(samples=(), scheme="x_1", provider=None, result_sink=[])

    assert captured["suppress_output"] is True
    assert captured["output"] is None
    assert captured["novel_allele"] is False
    assert captured["novel_profile"] is False
    assert captured["output_dir"] is None
