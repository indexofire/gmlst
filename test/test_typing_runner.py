from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from gmlst.commands.typing_runner import execute_typing_run


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
        console=SimpleNamespace(print=lambda *_args, **_kwargs: None),
    )

    assert [result.sample_id for result in results] == ["b_sample", "a_sample"]
    assert streamed == ["b_sample", "a_sample"]
    assert calls[0]["sample_paths"] == []
    assert calls[0]["threads"] == 1
    assert calls[1]["sample_paths"] == [sample_a]
    assert calls[2]["sample_paths"] == [sample_b]
