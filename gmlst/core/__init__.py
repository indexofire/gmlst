"""Core pipeline: tie together database, alignment, and ST calling."""

from __future__ import annotations

import logging
import time as time
from collections.abc import Callable
from pathlib import Path

from gmlst.aligners import get_aligner as get_aligner
from gmlst.aligners.base import AlignmentResult as AlignmentResult
from gmlst.aligners.base import AlleleMatch as AlleleMatch
from gmlst.calling.allele import LocusCall as LocusCall
from gmlst.calling.allele import call_all_loci as call_all_loci
from gmlst.calling.chew_policy import (
    classify_chew_style_calls as classify_chew_style_calls,
)
from gmlst.calling.st_lookup import STResult
from gmlst.calling.st_lookup import lookup_st as lookup_st
from gmlst.core.config import _cgmlst_cds_closed_ends as _cgmlst_cds_closed_ends
from gmlst.core.config import _cgmlst_cds_coordinates_out as _cgmlst_cds_coordinates_out
from gmlst.core.config import _cgmlst_cds_prediction_mode as _cgmlst_cds_prediction_mode
from gmlst.core.config import (
    _cgmlst_evidence_fallback_backend as _cgmlst_evidence_fallback_backend,
)
from gmlst.core.config import (
    _cgmlst_evidence_fallback_max_loci as _cgmlst_evidence_fallback_max_loci,
)
from gmlst.core.config import _cgmlst_prefilter_max_loci as _cgmlst_prefilter_max_loci
from gmlst.core.config import (
    _configured_cgmlst_cds_training_file as _configured_cgmlst_cds_training_file,
)
from gmlst.core.config import (
    _exact_hash_prefilter_enabled as _exact_hash_prefilter_enabled,
)
from gmlst.core.config import (
    _kma_fastq_mem_confirm_max_loci as _kma_fastq_mem_confirm_max_loci,
)
from gmlst.core.config import _kma_fastq_mem_mode_enabled as _kma_fastq_mem_mode_enabled
from gmlst.core.config import (
    _minimap2_bsr_confirm_max_loci as _minimap2_bsr_confirm_max_loci,
)
from gmlst.core.config import (
    _minimap2_fasta_emit_cigar_enabled as _minimap2_fasta_emit_cigar_enabled,
)
from gmlst.core.config import (
    _minimap2_fasta_speed_profile as _minimap2_fasta_speed_profile,
)
from gmlst.core.config import _minimap2_hash_locus_top_n as _minimap2_hash_locus_top_n
from gmlst.core.config import (
    _minimap2_hash_prefilter_enabled as _minimap2_hash_prefilter_enabled,
)
from gmlst.core.config import (
    _minimap2_hash_refine_max_loci as _minimap2_hash_refine_max_loci,
)
from gmlst.core.config import (
    _minimap2_representative_main_alignment as _minimap2_representative_main_alignment,
)
from gmlst.core.config import (
    _minimap2_ultrafast_second_pass_max_loci as _m2_ultrafast_second_pass_max_loci,
)
from gmlst.core.ranking import (
    _adaptive_ultrafast_second_pass_budget as _adaptive_ultrafast_second_pass_budget,
)
from gmlst.core.ranking import (
    _call_rank as _call_rank,
)
from gmlst.core.ranking import (
    _low_confidence_loci as _low_confidence_loci,
)
from gmlst.core.ranking import (
    _ultrafast_confirmation_rank as _ultrafast_confirmation_rank,
)
from gmlst.core.ranking import (
    _ultrafast_second_pass_rank as _ultrafast_second_pass_rank,
)
from gmlst.core.types import CgmlstModeOverrides as CgmlstModeOverrides
from gmlst.core.types import TypingContext as TypingContext
from gmlst.database.cache import DatabaseCache as DatabaseCache
from gmlst.kmer_prefilter import (
    prefilter_assembly_candidates as prefilter_assembly_candidates,
)
from gmlst.readers.sample import SampleInput
from gmlst.readers.sample import detect_sample as detect_sample
from gmlst.utils import temp_dir as temp_dir

from . import adapters_cds as _adapters_cds
from . import adapters_exact_hash as _adapters_exact_hash
from . import adapters_index_prefilter as _adapters_index_prefilter
from . import adapters_refinement as _adapters_refinement
from . import cds as _cds
from . import exact_hash as _exact_hash
from . import indexing as _indexing
from . import prefilter as _prefilter
from . import sequences as _sequences

_minimap2_ultrafast_second_pass_max_loci = _m2_ultrafast_second_pass_max_loci

logger = logging.getLogger("gmlst.core")

_index_is_empty = _indexing.index_is_empty_impl
_find_index = _indexing.find_index_impl
_purge_backend_index = _indexing.purge_backend_index_impl
_is_index_stale = _indexing.is_index_stale_impl

_split_allele_header = _sequences.split_allele_header_impl
_iter_fasta_sequences = _sequences.iter_fasta_sequences_impl

_prefilter_is_confident = _prefilter.prefilter_is_confident_impl
_flatten_allele_sequences = _prefilter.flatten_allele_sequences_impl
_allele_order_key = _prefilter.allele_order_key_impl
_select_candidate_locus_fastas = _prefilter.select_candidate_locus_fastas_impl

_scheme_precomputed_dir = _exact_hash.scheme_precomputed_dir_impl
_allele_files_fingerprint = _exact_hash.allele_files_fingerprint_impl
_build_allele_hash_index = _exact_hash.build_allele_hash_index_impl
_sample_cds_cache_config = _exact_hash.sample_cds_cache_config_impl
_translate_cds_to_protein = _exact_hash.translate_cds_to_protein_impl

_predict_cds_genes = _cds.predict_cds_genes_impl

_write_merged_fasta = _adapters_refinement.write_merged_fasta_impl
_align_targeted_loci = _adapters_refinement.align_targeted_loci_impl
_merge_calls_from_alignment = _adapters_refinement.merge_calls_from_alignment_impl
_recompute_all_loci_with_additional_alignment = (
    _adapters_refinement.recompute_all_loci_with_additional_alignment_impl
)
_confirm_loci_with_tuned_aligner = (
    _adapters_refinement.confirm_loci_with_tuned_aligner_impl
)
_align_evidence_fallback_loci = _adapters_refinement.align_evidence_fallback_loci_impl
_apply_post_alignment_refinements = (
    _adapters_refinement.apply_post_alignment_refinements_impl
)
_merge_fallback_calls = _adapters_refinement.merge_fallback_calls_impl

_ensure_full_index = _adapters_index_prefilter.ensure_full_index_impl
_load_scheme_allele_sequences = (
    _adapters_index_prefilter.load_scheme_allele_sequences_impl
)
_load_representative_allele_sequences = (
    _adapters_index_prefilter.load_representative_allele_sequences_impl
)
_representatives_from_nested_alleles = (
    _adapters_index_prefilter.representatives_from_nested_alleles_impl
)
_load_or_build_minimap2_representative_index = (
    _adapters_index_prefilter.load_or_build_minimap2_representative_index_impl
)
_representative_fingerprint = _adapters_index_prefilter.representative_fingerprint_impl
_write_candidate_fastas = _adapters_index_prefilter.write_candidate_fastas_impl
_representative_alleles = _adapters_index_prefilter.representative_alleles_impl
_minimap2_representative_prefilter_candidates = (
    _adapters_index_prefilter.minimap2_representative_prefilter_candidates_impl
)
_cgmlst_mode_overrides = _adapters_index_prefilter.cgmlst_mode_overrides_impl
_resolve_cgmlst_cds_training_file = _adapters_cds.resolve_cgmlst_cds_training_file_impl
_write_cds_coordinates = _adapters_cds.write_cds_coordinates_impl
_load_or_build_exact_hash_indexes = (
    _adapters_exact_hash.load_or_build_exact_hash_indexes_impl
)
_build_allele_protein_hash_index = (
    _adapters_exact_hash.build_allele_protein_hash_index_impl
)
_resolve_exact_cds_matches = _adapters_exact_hash.resolve_exact_cds_matches_impl
_predict_cds_sequences = _adapters_exact_hash.predict_cds_sequences_impl
_load_or_build_sample_cds_hashes = (
    _adapters_exact_hash.load_or_build_sample_cds_hashes_impl
)
_load_or_build_sample_cds_sequences = (
    _adapters_exact_hash.load_or_build_sample_cds_sequences_impl
)
_load_or_build_sample_cds_data = _adapters_exact_hash.load_or_build_sample_cds_data_impl
_hash_cds_and_protein = _adapters_exact_hash.hash_cds_and_protein_impl


def run_typing(
    sample_paths: list[Path | SampleInput],
    scheme_name: str,
    backend: str,
    *,
    provider: str = "pubmlst",
    scheme_type: str = "mlst",
    cgmlst_mode: str = "standard",
    cache_root: Path | None = None,
    min_identity: float = 95.0,
    min_coverage: float = 0.95,
    min_depth: float = 10.0,
    force_reindex: bool = False,
    threads: int = 1,
    count_same_copy: bool = False,
    prefilter_enabled: bool = True,
    prefilter_k: int = 31,
    prefilter_top_n: int = 20,
    prefilter_min_loci_fraction: float = 0.3,
    cds_coordinates_out: Path | None = None,
    call_policy: str = "default",
    chew_cds_gate: bool = True,
    on_result: Callable[[STResult], None] | None = None,
) -> list[STResult]:
    from .pipeline import run_typing_impl

    return run_typing_impl(
        sample_paths,
        scheme_name,
        backend,
        provider=provider,
        scheme_type=scheme_type,
        cgmlst_mode=cgmlst_mode,
        cache_root=cache_root,
        min_identity=min_identity,
        min_coverage=min_coverage,
        min_depth=min_depth,
        force_reindex=force_reindex,
        threads=threads,
        count_same_copy=count_same_copy,
        prefilter_enabled=prefilter_enabled,
        prefilter_k=prefilter_k,
        prefilter_top_n=prefilter_top_n,
        prefilter_min_loci_fraction=prefilter_min_loci_fraction,
        cds_coordinates_out=cds_coordinates_out,
        call_policy=call_policy,
        chew_cds_gate=chew_cds_gate,
        on_result=on_result,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
