from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from gmlst.core.types import CgmlstModeOverrides, TypingContext
from gmlst.readers.sample import SampleInput


def _sample_overrides() -> CgmlstModeOverrides:
    return CgmlstModeOverrides(
        protein_exact_hash_prefilter=False,
        exact_hash_prefilter=False,
        minimap2_hash_prefilter=False,
        minimap2_hash_locus_top_n=None,
        minimap2_hash_refine_max_loci=None,
        minimap2_fasta_emit_cigar=None,
        minimap2_fasta_speed_profile=None,
        minimap2_representative_main_alignment=None,
        minimap2_bsr_confirm_max_loci=None,
        minimap2_ultrafast_second_pass_max_loci=None,
        evidence_fallback_backend=None,
        evidence_fallback_max_loci=None,
    )


def test_typing_context_constructs_with_required_fields() -> None:
    ctx = TypingContext(
        backend="blastn",
        scheme_type="cgmlst",
        scheme_name="test",
        provider="pubmlst",
        mode_overrides=_sample_overrides(),
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=10.0,
        threads=1,
        count_same_copy=False,
    )
    assert ctx.backend == "blastn"
    assert ctx.scheme_type == "cgmlst"
    assert ctx.threads == 1


def test_typing_context_optional_fields_default_to_none() -> None:
    ctx = TypingContext(
        backend="minimap2",
        scheme_type="mlst",
        scheme_name="test",
        provider="pubmlst",
        mode_overrides=_sample_overrides(),
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=10.0,
        threads=1,
        count_same_copy=False,
    )
    assert ctx.sample is None
    assert ctx.scheme is None
    assert ctx.aligner is None
    assert ctx.cache is None
    assert ctx.cache_root is None
    assert ctx.exact_hash_index is None
    assert ctx.protein_hash_index is None
    assert ctx.allele_sequence_cache is None
    assert ctx.prefilter_alleles is None
    assert ctx.minimap2_prefilter_index_path is None
    assert ctx.index_path is None
    assert ctx.index_dir is None
    assert ctx.allele_fastas is None
    assert ctx.cds_training_file is None


def test_typing_context_frozen() -> None:
    ctx = TypingContext(
        backend="blastn",
        scheme_type="cgmlst",
        scheme_name="test",
        provider="pubmlst",
        mode_overrides=_sample_overrides(),
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=10.0,
        threads=1,
        count_same_copy=False,
    )
    with pytest.raises(FrozenInstanceError):
        ctx.backend = "minimap2"


def test_typing_context_all_fields_set() -> None:
    overrides = _sample_overrides()
    sample = SampleInput(sample_id="s1", path=Path("/tmp/s1.fna"), input_type="fasta")
    ctx = TypingContext(
        core=None,
        sample=sample,
        scheme={"loci": ["abc"]},
        backend="minimap2",
        aligner=None,
        cache=None,
        cache_root=Path("/tmp/cache"),
        scheme_name="cgmlst",
        provider="pubmlst",
        mode_overrides=overrides,
        scheme_type="cgmlst",
        use_prefilter=True,
        use_minimap2_hash_prefilter=True,
        use_exact_hash_prefilter=False,
        exact_hash_index=None,
        protein_hash_index=None,
        allele_sequence_cache={"abc": {"abc_1": "ATGC"}},
        prefilter_alleles=None,
        minimap2_prefilter_representatives={("abc", "abc_1"): "ATGC"},
        minimap2_prefilter_index_path=Path("/tmp/rep.mmi"),
        prefilter_k=31,
        effective_prefilter_top_n=20,
        effective_prefilter_stride=1,
        prefilter_min_loci_fraction=0.3,
        index_dir=Path("/tmp/idx"),
        index_path=Path("/tmp/idx/main.mmi"),
        allele_fastas=[Path("/tmp/abc.tfa")],
        force_reindex=False,
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=10.0,
        threads=4,
        count_same_copy=True,
        kma_fastq_mem_mode=False,
        minimap2_representative_main_alignment=True,
        ultrafast_second_pass_max_loci=50,
        cds_prediction_mode="prodigal",
        cds_training_file=None,
        cds_closed_ends=False,
        normalized_policy="default",
        chew_cds_gate=True,
    )
    assert ctx.sample.sample_id == "s1"
    assert ctx.allele_sequence_cache == {"abc": {"abc_1": "ATGC"}}
    assert ctx.threads == 4
    assert ctx.minimap2_representative_main_alignment is True


def test_typing_context_evolve_creates_copy() -> None:
    ctx = TypingContext(
        backend="blastn",
        scheme_type="cgmlst",
        scheme_name="test",
        provider="pubmlst",
        mode_overrides=_sample_overrides(),
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=10.0,
        threads=1,
        count_same_copy=False,
    )
    ctx2 = ctx.evolve(backend="minimap2", threads=4)
    assert ctx.backend == "blastn"
    assert ctx.threads == 1
    assert ctx2.backend == "minimap2"
    assert ctx2.threads == 4
