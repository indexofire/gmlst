"""Behavior tests for core/pipeline.py orchestration functions.

Tests the individual pipeline functions directly with lightweight mock objects,
without requiring real alignment infrastructure or subprocess calls.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from gmlst.aligners.base import AlignmentResult, AlleleMatch
from gmlst.core.pipeline import (
    _finalize_sample_result,
    _resolve_sample_source,
    _run_direct_alignment_phase,
    _type_all_samples,
    _type_single_sample,
)
from gmlst.core.types import TypingContext

# ---------------------------------------------------------------------------
# Stubs / helpers
# ---------------------------------------------------------------------------


def _make_sample(
    path: Path,
    input_type: str = "fasta",
    mate: Path | None = None,
    sample_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        path=path,
        input_type=input_type,
        mate_path=mate,
        sample_id=sample_id or path.stem,
    )


def _make_scheme(loci: list[str]) -> SimpleNamespace:
    return SimpleNamespace(name="test_scheme", loci=loci, allele_files={})


def _make_match(
    locus: str, allele_id: str = "1", identity: float = 100.0
) -> AlleleMatch:
    return AlleleMatch(
        locus=locus,
        allele_id=allele_id,
        identity=identity,
        coverage=1.0,
    )


def _make_core_mod() -> MagicMock:
    """A MagicMock that mimics gmlst.core for pipeline function calls."""
    mod = MagicMock()
    mod.AlignmentResult = AlignmentResult
    mod.time = time
    mod.logger = MagicMock()
    mod.temp_dir = MagicMock(return_value=MagicMock())
    mod.temp_dir.return_value.__enter__ = lambda _self: MagicMock()
    mod.temp_dir.return_value.__exit__ = lambda *_a: None
    return mod


# ---------------------------------------------------------------------------
# _resolve_sample_source
# ---------------------------------------------------------------------------


class TestResolveSampleSource:
    def test_fasta_returns_single_path(self, tmp_path: Path) -> None:
        sample = _make_sample(tmp_path / "genome.fna", input_type="fasta")
        aligner = SimpleNamespace(supports_fastq=True)

        result = _resolve_sample_source(sample, aligner, "blastn")
        assert result == sample.path

    def test_fastq_with_mate_returns_tuple(self, tmp_path: Path) -> None:
        r1 = tmp_path / "reads_R1.fq"
        r2 = tmp_path / "reads_R2.fq"
        sample = _make_sample(r1, input_type="fastq", mate=r2)
        aligner = SimpleNamespace(supports_fastq=True)

        result = _resolve_sample_source(sample, aligner, "kma")
        assert result == (r1, r2)

    def test_fastq_without_support_raises_value_error(self, tmp_path: Path) -> None:
        sample = _make_sample(tmp_path / "reads.fq", input_type="fastq")
        aligner = SimpleNamespace(supports_fastq=False)

        with pytest.raises(ValueError, match="does not support FASTQ"):
            _resolve_sample_source(sample, aligner, "blastn")


# ---------------------------------------------------------------------------
# _run_direct_alignment_phase
# ---------------------------------------------------------------------------


class TestRunDirectAlignmentPhase:
    def test_raises_runtime_error_when_index_path_is_none(self, tmp_path: Path) -> None:
        core_mod = _make_core_mod()
        sample = _make_sample(tmp_path / "g.fna")
        scheme = _make_scheme(["abc", "def"])
        aligner = MagicMock()

        with pytest.raises(RuntimeError, match="missing aligner index path"):
            _run_direct_alignment_phase(
                core_mod,
                sample,
                scheme,
                aligner,
                "blastn",
                sample.path,
                exact_matches={},
                index_path=None,
            )

    def test_returns_empty_result_when_all_loci_exact_matched(
        self, tmp_path: Path
    ) -> None:
        core_mod = _make_core_mod()
        sample = _make_sample(tmp_path / "g.fna")
        scheme = _make_scheme(["abc", "def"])
        aligner = MagicMock()
        aligner.align.assert_not_called()  # should not call aligner

        exact = {
            "abc": _make_match("abc"),
            "def": _make_match("def"),
        }

        aln = _run_direct_alignment_phase(
            core_mod,
            sample,
            scheme,
            aligner,
            "blastn",
            sample.path,
            exact_matches=exact,
            index_path=tmp_path / "idx",
        )

        assert aln.matches == []
        assert aln.failed_loci == []
        aligner.align.assert_not_called()

    def test_calls_aligner_for_residual_loci(self, tmp_path: Path) -> None:
        core_mod = _make_core_mod()
        sample = _make_sample(tmp_path / "g.fna")
        scheme = _make_scheme(["abc", "def"])
        aligner = MagicMock()
        fake_aln = AlignmentResult(
            sample_id="g",
            matches=[_make_match("def")],
            failed_loci=[],
            backend="blastn",
        )
        aligner.align.return_value = fake_aln

        _run_direct_alignment_phase(
            core_mod,
            sample,
            scheme,
            aligner,
            "blastn",
            sample.path,
            exact_matches={"abc": _make_match("abc")},  # abc already matched
            index_path=tmp_path / "idx",
        )

        # aligner should be called only for residual loci (def, not abc)
        aligner.align.assert_called_once()
        call_args = aligner.align.call_args
        assert "def" in call_args[0][2]  # third positional arg = loci list
        assert "abc" not in call_args[0][2]


# ---------------------------------------------------------------------------
# _finalize_sample_result
# ---------------------------------------------------------------------------


class TestFinalizeSampleResult:
    def test_merges_exact_matches_into_alignment(self, tmp_path: Path) -> None:
        """Exact-hash matches are prepended to the alignment result before calling."""
        core_mod = _make_core_mod()
        core_mod.call_all_loci.return_value = {}
        core_mod._apply_post_alignment_refinements.return_value = {}
        core_mod.lookup_st.return_value = SimpleNamespace(sample_id="g", st="-")

        exact = {"abc": _make_match("abc", "42")}
        aln_matches = [_make_match("def", "7")]
        base_aln = AlignmentResult(
            sample_id="g", matches=aln_matches, failed_loci=[], backend="blastn"
        )

        ctx = TypingContext(
            core=core_mod,
            normalized_policy="default",
            min_identity=95.0,
            min_coverage=0.95,
            min_depth=10.0,
            count_same_copy=False,
            chew_cds_gate=False,
        )
        sample = _make_sample(tmp_path / "g.fna")
        scheme = _make_scheme(["abc", "def"])

        st_result, _ = _finalize_sample_result(
            ctx,
            core_mod,
            sample,
            scheme,
            "blastn",
            sample.path,
            base_aln,
            exact,
            tmp_path / "idx",
        )

        # call_all_loci should receive merged alignment with both exact + aln matches
        merged_aln = core_mod.call_all_loci.call_args[0][0]
        assert len(merged_aln.matches) == 2
        loci_in_merged = {m.locus for m in merged_aln.matches}
        assert loci_in_merged == {"abc", "def"}


# ---------------------------------------------------------------------------
# _type_all_samples
# ---------------------------------------------------------------------------


class TestTypeAllSamples:
    def test_calls_callback_for_each_sample(self) -> None:
        """on_result is invoked once per sample with the STResult."""
        results_from_single = [
            SimpleNamespace(sample_id="s1", st="1"),
            SimpleNamespace(sample_id="s2", st="2"),
        ]
        call_log: list[str] = []

        base_ctx = TypingContext(core=None, normalized_policy="default")

        # Patch _type_single_sample to avoid full pipeline.
        original = _type_single_sample

        def fake_single(ctx):
            idx = len(call_log)
            return results_from_single[idx], Path("/fake/idx")

        import gmlst.core.pipeline as pipeline_mod

        pipeline_mod._type_single_sample = fake_single
        try:
            samples = [
                _make_sample(Path("/fake/s1.fna"), sample_id="s1"),
                _make_sample(Path("/fake/s2.fna"), sample_id="s2"),
            ]
            results = _type_all_samples(base_ctx, samples, call_log.append)
        finally:
            pipeline_mod._type_single_sample = original

        assert len(results) == 2
        assert [r.sample_id for r in results] == ["s1", "s2"]
        assert [r.sample_id for r in call_log] == ["s1", "s2"]

    def test_accumulates_results_without_callback(self) -> None:
        """Works fine when on_result is None."""
        results_from_single = [SimpleNamespace(sample_id="s1", st="1")]

        base_ctx = TypingContext(core=None, normalized_policy="default")

        original = _type_single_sample

        def fake_single(_ctx):
            return results_from_single[0], Path("/fake/idx")

        import gmlst.core.pipeline as pipeline_mod

        pipeline_mod._type_single_sample = fake_single
        try:
            samples = [_make_sample(Path("/fake/s1.fna"), sample_id="s1")]
            results = _type_all_samples(base_ctx, samples, on_result=None)
        finally:
            pipeline_mod._type_single_sample = original

        assert len(results) == 1
        assert results[0].sample_id == "s1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
