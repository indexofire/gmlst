from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from gmlst.commands.typing_runner import execute_typing_run

SHARED_KWARGS = [
    "scheme_name",
    "backend",
    "provider",
    "scheme_type",
    "cgmlst_mode",
    "cache_root",
    "min_identity",
    "min_coverage",
    "min_depth",
    "min_join_overlap",
    "count_same_copy",
    "prefilter_enabled",
    "prefilter_k",
    "prefilter_top_n",
    "prefilter_min_loci_fraction",
    "cds_coordinates_out",
    "call_policy",
    "chew_cds_gate",
]


def test_execute_typing_run_parallel_preserves_input_order(
    monkeypatch, tmp_path: Path
) -> None:
    sample_a = tmp_path / "b_sample.fna"
    sample_b = tmp_path / "a_sample.fna"
    sample_a.write_text(">b\nATGC\n")
    sample_b.write_text(">a\nATGC\n")

    calls: list[dict[str, object]] = []

    def fake_run_typing(**kwargs):
        calls.append(kwargs)
        if kwargs["sample_paths"] == []:
            return []
        sample_path = kwargs["sample_paths"][0]
        return [SimpleNamespace(sample_id=sample_path.stem)]

    streamed: list[str] = []

    results = execute_typing_run(
        run_typing_fn=fake_run_typing,
        prepared_samples=[sample_a, sample_b],
        scheme_name="demo",
        backend="kma",
        provider="pubmlst",
        scheme_type="cgmlst",
        cgmlst_mode="fast",
        cache_root=None,
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=10.0,
        force_reindex=False,
        threads=4,
        count_same_copy=False,
        prefilter_enabled=True,
        prefilter_k=31,
        prefilter_top_n=20,
        prefilter_min_loci_fraction=0.3,
        cds_coordinates_out=None,
        call_policy="default",
        chew_cds_gate=True,
        max_workers=2,
        on_result=lambda result: streamed.append(result.sample_id),
    )

    assert [result.sample_id for result in results] == ["b_sample", "a_sample"]
    assert streamed == ["b_sample", "a_sample"]
    assert calls[0]["sample_paths"] == []
    assert calls[0]["threads"] == 1
    assert calls[1]["sample_paths"] == [sample_a]
    assert calls[2]["sample_paths"] == [sample_b]


@pytest.mark.parametrize("max_workers", [1, 2])
def test_execute_typing_run_passes_identical_shared_kwargs(
    monkeypatch, tmp_path: Path, max_workers: int
) -> None:
    """All run_typing_fn invocations see identical values for shared fields.

    Behavior lock for the base_kwargs consolidation: warm-up, per-sample
    worker, and serial call sites must agree on every one of the 18
    shared keyword arguments.
    """
    samples = []
    for name in ("s1.fna", "s2.fna", "s3.fna"):
        path = tmp_path / name
        path.write_text(">c\nATGC\n")
        samples.append(path)

    calls: list[dict[str, object]] = []

    def fake_run_typing(**kwargs):
        calls.append(kwargs)
        if kwargs["sample_paths"] == []:
            return []
        sample_path = kwargs["sample_paths"][0]
        return [SimpleNamespace(sample_id=sample_path.stem)]

    shared_values = {
        "scheme_name": "demo",
        "backend": "kma",
        "provider": "pubmlst",
        "scheme_type": "cgmlst",
        "cgmlst_mode": "fast",
        "cache_root": None,
        "min_identity": 95.0,
        "min_coverage": 0.95,
        "min_depth": 10.0,
        "min_join_overlap": 12,
        "count_same_copy": True,
        "prefilter_enabled": True,
        "prefilter_k": 31,
        "prefilter_top_n": 20,
        "prefilter_min_loci_fraction": 0.3,
        "cds_coordinates_out": None,
        "call_policy": "default",
        "chew_cds_gate": True,
    }

    execute_typing_run(
        run_typing_fn=fake_run_typing,
        prepared_samples=samples,
        force_reindex=False,
        threads=4,
        max_workers=max_workers,
        on_result=lambda _result: None,
        **shared_values,
    )

    if max_workers > 1:
        # kma backend triggers a warm-up call plus one worker per sample.
        assert len(calls) == 1 + len(samples)
        assert calls[0]["sample_paths"] == []
        assert calls[0]["threads"] == 1
        for worker_call in calls[1:]:
            assert worker_call["sample_paths"]
            assert worker_call["threads"] == 1
            assert worker_call["force_reindex"] is False
            assert worker_call["on_result"] is None
    else:
        assert len(calls) == 1
        assert calls[0]["sample_paths"] == samples
        assert calls[0]["threads"] == 4
        assert calls[0]["force_reindex"] is False

    for call in calls:
        for key in SHARED_KWARGS:
            assert key in call, key
            assert call[key] == shared_values[key], (key, call.get(key))
