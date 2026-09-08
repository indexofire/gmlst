"""Runtime configuration for cgMLST workflows via environment variables.

Each accessor reads a ``GMLST_*`` variable with validation and a safe
default: invalid values log a warning and fall back, so runs keep
documented behaviour instead of crashing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PREFILTER_MAX_LOCI = 3000
_TRUTHY = {"1", "true", "yes", "on"}


def _env_int(env_var: str, default: int) -> int:
    raw = os.getenv(env_var, str(default))
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %d", env_var, raw, default)
        return default
    return max(0, value)


def cgmlst_prefilter_max_loci() -> int:
    """Max loci for enabling the cgMLST prefilter (0 = disabled)."""
    raw = os.getenv("GMLST_CGMLST_PREFILTER_MAX_LOCI")
    if raw is None:
        return DEFAULT_PREFILTER_MAX_LOCI
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid GMLST_CGMLST_PREFILTER_MAX_LOCI=%r; using default %d",
            raw,
            DEFAULT_PREFILTER_MAX_LOCI,
        )
        return DEFAULT_PREFILTER_MAX_LOCI
    return max(0, value)


def minimap2_hash_prefilter_enabled() -> bool:
    """Whether the minimap2 representative prefilter is on."""
    raw = os.getenv("GMLST_CGMLST_MINIMAP2_HASH_PREFILTER", "0").strip().lower()
    return raw in _TRUTHY


def minimap2_fasta_emit_cigar_enabled() -> bool:
    """Whether minimap2 FASTA output includes CIGAR (-c)."""
    raw = os.getenv("GMLST_MINIMAP2_FASTA_EMIT_CIGAR", "1").strip().lower()
    return raw in _TRUTHY


def minimap2_hash_refine_max_loci() -> int:
    """Cap on missing-loci refinement passes (0 = off)."""
    return _env_int("GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI", 0)


def minimap2_hash_locus_top_n() -> int:
    """Per-locus allele cap from the k-mer prefilter (0 = all)."""
    return _env_int("GMLST_CGMLST_MINIMAP2_HASH_LOCI_TOP_N", 0)


def candidate_max_alleles_per_locus() -> int:
    """Max alleles per locus written to candidate FASTA (0 = all alleles)."""
    return _env_int("GMLST_CGMLST_CANDIDATE_MAX_ALLELES", 0)


def minimap2_bsr_confirm_max_loci() -> int:
    """Cap on BSR-style confirmation loci (0 = off)."""
    return _env_int("GMLST_CGMLST_MINIMAP2_BSR_CONFIRM_MAX_LOCI", 0)


def minimap2_ultrafast_second_pass_max_loci() -> int | None:
    """Cap on second-pass rescue loci in ultrafast mode.

    ``None`` (from "adaptive"/"auto") lets the runner choose a budget
    based on the run.
    """
    raw = (
        os.getenv(
            "GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI",
            "adaptive",
        )
        .strip()
        .lower()
    )
    if raw in {"", "adaptive", "auto"}:
        return None
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI=%r; "
            "using adaptive budget",
            raw,
        )
        return None
    return max(0, value)


def kma_fastq_mem_mode_enabled() -> bool:
    """Whether KMA FASTQ typing uses -mem_mode."""
    raw = os.getenv("GMLST_CGMLST_KMA_FASTQ_MEM_MODE", "1").strip().lower()
    return raw in _TRUTHY


def kma_fastq_mem_confirm_max_loci() -> int:
    """Strict re-check cap after the fast -mem_mode pass."""
    return _env_int("GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI", 64)


def exact_hash_prefilter_enabled() -> bool:
    """Whether exact-hash pre-resolution runs before alignment."""
    raw = os.getenv("GMLST_CGMLST_EXACT_HASH_PREFILTER", "0").strip().lower()
    return raw in _TRUTHY


def minimap2_fasta_speed_profile() -> str:
    """minimap2 FASTA speed profile: default/fast/ultrafast."""
    raw = os.getenv("GMLST_MINIMAP2_FASTA_SPEED_PROFILE", "default").strip().lower()
    if raw in {"default", "fast", "ultrafast"}:
        return raw
    logger.warning(
        "Invalid GMLST_MINIMAP2_FASTA_SPEED_PROFILE=%r; using default 'default'",
        raw,
    )
    return "default"


def minimap2_representative_main_alignment() -> bool:
    """Whether the main alignment uses one representative allele per locus."""
    raw = (
        os.getenv("GMLST_CGMLST_MINIMAP2_REPRESENTATIVE_MAIN_ALIGNMENT", "0")
        .strip()
        .lower()
    )
    return raw in _TRUTHY


def cgmlst_evidence_fallback_backend() -> str:
    """Fallback aligner for low-confidence loci (none = off)."""
    raw = os.getenv("GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND", "none").strip().lower()
    if raw in {"none", "blastn", "kma", "nucmer"}:
        return raw
    logger.warning(
        "Invalid GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=%r; using 'none'",
        raw,
    )
    return "none"


def cgmlst_evidence_fallback_max_loci() -> int:
    """Cap on evidence-fallback loci (0 = unlimited)."""
    return _env_int("GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI", 300)


def cgmlst_cds_prediction_mode() -> str:
    """CDS prediction mode for cgMLST: meta or single."""
    raw = os.getenv("GMLST_CGMLST_CDS_PREDICTION_MODE", "single").strip().lower()
    if raw in {"single", "meta"}:
        return raw
    logger.warning(
        "Invalid GMLST_CGMLST_CDS_PREDICTION_MODE=%r; using default 'single'",
        raw,
    )
    return "single"


def configured_cgmlst_cds_training_file() -> Path | None:
    """Configured Prodigal training file path, if any."""
    raw = os.getenv("GMLST_CGMLST_CDS_TRAINING_FILE", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def cgmlst_cds_closed_ends() -> bool:
    """Whether predicted CDSs are closed (complete gene models)."""
    raw = os.getenv("GMLST_CGMLST_CDS_CLOSED_ENDS", "0").strip().lower()
    return raw in _TRUTHY


def cgmlst_cds_coordinates_out() -> Path | None:
    """Optional path to write predicted CDS coordinates TSV."""
    raw = os.getenv("GMLST_CGMLST_CDS_COORDINATES_OUT", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()
