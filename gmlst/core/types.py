"""Shared data types for the core typing pipeline.

Defines the immutable per-run configuration bundle
(:class:`TypingContext`) and the cgMLST mode override table
(:class:`CgmlstModeOverrides`) that together parameterize the pipeline
without threading dozens of keyword arguments through every phase.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from gmlst.readers.sample import SampleInput


@dataclass(frozen=True)
class CgmlstModeOverrides:
    """Pipeline knobs overridden per cgMLST mode (fast/ultrafast/balanced).

    ``None`` means "no override": the environment-configured default
    applies. Non-``None`` values force the behavior for the mode:

    - ``exact_hash_prefilter``: resolve exact alleles via CDS hashing
      before alignment.
    - ``minimap2_hash_prefilter``: shortlist loci against a representative
      minimap2 index instead of a k-mer prefilter.
    - ``minimap2_hash_locus_top_n``: candidate alleles kept per locus when
      narrowing the hash prefilter's loci.
    - ``minimap2_hash_refine_max_loci``: cap (0 disables) on "missing"
      loci eligible for targeted refinement re-alignment.
    - ``minimap2_fasta_emit_cigar``: request CIGAR output in minimap2
      FASTA alignments.
    - ``minimap2_fasta_speed_profile``: minimap2 speed preset name
      (e.g. ``"default"``, ``"ultrafast"``).
    - ``minimap2_representative_main_alignment``: reuse the
      representative-index alignment as the main alignment, skipping
      per-sample candidate FASTAs.
    - ``minimap2_bsr_confirm_max_loci``: cap on low-confidence loci
      re-aligned in the BSR-like confirmation pass.
    - ``minimap2_ultrafast_second_pass_max_loci``: budget for the
      ultrafast second pass (``None`` selects the adaptive budget, ``0``
      disables the pass).
    - ``evidence_fallback_backend``: backend (e.g. ``"blastn"``) used to
      re-align low-confidence loci; ``"none"`` disables the fallback.
    - ``evidence_fallback_max_loci``: cap on loci sent to the evidence
      fallback (larger sets skip it).
    """

    exact_hash_prefilter: bool
    minimap2_hash_prefilter: bool
    minimap2_hash_locus_top_n: int | None
    minimap2_hash_refine_max_loci: int | None
    minimap2_fasta_emit_cigar: bool | None
    minimap2_fasta_speed_profile: str | None
    minimap2_representative_main_alignment: bool | None
    minimap2_bsr_confirm_max_loci: int | None
    minimap2_ultrafast_second_pass_max_loci: int | None
    evidence_fallback_backend: str | None
    evidence_fallback_max_loci: int | None


@dataclass(frozen=True)
class TypingContext:
    """Immutable configuration bundle shared across one typing run.

    Carries everything a pipeline phase needs — the core facade, scheme
    and cache handles, aligner and index paths, prefilter state (exact-hash
    index, allele caches, representative index), CDS prediction settings,
    and calling thresholds — so per-sample phases receive a single frozen
    object instead of long keyword chains. Use :meth:`evolve` to derive a
    copy bound to one sample.
    """

    core: object | None = None
    sample: SampleInput | None = None
    scheme: object | None = None
    backend: str = ""
    aligner: object | None = None
    cache: object | None = None
    cache_root: Path | None = None
    scheme_name: str = ""
    provider: str = ""
    mode_overrides: CgmlstModeOverrides | None = None
    scheme_type: str = ""
    use_prefilter: bool = False
    use_minimap2_hash_prefilter: bool = False
    use_exact_hash_prefilter: bool = False
    exact_hash_index: dict[str, list[tuple[str, str]]] | None = None
    allele_sequence_cache: dict[str, dict[str, str]] | None = None
    prefilter_alleles: dict[tuple[str, str], str] | None = None
    minimap2_prefilter_representatives: dict[tuple[str, str], str] | None = None
    minimap2_prefilter_index_path: Path | None = None
    prefilter_k: int = 31
    effective_prefilter_top_n: int = 20
    effective_prefilter_stride: int = 1
    prefilter_min_loci_fraction: float = 0.3
    index_dir: Path | None = None
    index_path: Path | None = None
    allele_fastas: list[Path] | None = None
    force_reindex: bool = False
    min_identity: float = 95.0
    min_coverage: float = 0.95
    min_depth: float = 10.0
    threads: int = 1
    count_same_copy: bool = False
    kma_fastq_mem_mode: bool = False
    minimap2_representative_main_alignment: bool = False
    ultrafast_second_pass_max_loci: int | None = None
    cds_prediction_mode: str = ""
    cds_training_file: Path | None = None
    cds_closed_ends: bool = False
    normalized_policy: str = "default"
    chew_cds_gate: bool = True

    def evolve(self, **overrides) -> TypingContext:
        """Return a copy of this context with fields replaced by *overrides*."""
        return replace(self, **overrides)
