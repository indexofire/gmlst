from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from gmlst.readers.sample import SampleInput


@dataclass(frozen=True)
class CgmlstModeOverrides:
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
        return replace(self, **overrides)
