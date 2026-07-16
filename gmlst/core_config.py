from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("gmlst.core")

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
    raw = os.getenv("GMLST_CGMLST_MINIMAP2_HASH_PREFILTER", "0").strip().lower()
    return raw in _TRUTHY


def minimap2_fasta_emit_cigar_enabled() -> bool:
    raw = os.getenv("GMLST_MINIMAP2_FASTA_EMIT_CIGAR", "1").strip().lower()
    return raw in _TRUTHY


def minimap2_hash_refine_max_loci() -> int:
    return _env_int("GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI", 0)


def minimap2_hash_locus_top_n() -> int:
    return _env_int("GMLST_CGMLST_MINIMAP2_HASH_LOCI_TOP_N", 0)


def minimap2_bsr_confirm_max_loci() -> int:
    return _env_int("GMLST_CGMLST_MINIMAP2_BSR_CONFIRM_MAX_LOCI", 0)


def minimap2_ultrafast_second_pass_max_loci() -> int | None:
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
    raw = os.getenv("GMLST_CGMLST_KMA_FASTQ_MEM_MODE", "1").strip().lower()
    return raw in _TRUTHY


def kma_fastq_mem_confirm_max_loci() -> int:
    return _env_int("GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI", 64)


def exact_hash_prefilter_enabled() -> bool:
    raw = os.getenv("GMLST_CGMLST_EXACT_HASH_PREFILTER", "0").strip().lower()
    return raw in _TRUTHY


def minimap2_fasta_speed_profile() -> str:
    raw = os.getenv("GMLST_MINIMAP2_FASTA_SPEED_PROFILE", "default").strip().lower()
    if raw in {"default", "fast", "ultrafast"}:
        return raw
    logger.warning(
        "Invalid GMLST_MINIMAP2_FASTA_SPEED_PROFILE=%r; using default 'default'",
        raw,
    )
    return "default"


def minimap2_representative_main_alignment() -> bool:
    raw = (
        os.getenv("GMLST_CGMLST_MINIMAP2_REPRESENTATIVE_MAIN_ALIGNMENT", "0")
        .strip()
        .lower()
    )
    return raw in _TRUTHY


def cgmlst_evidence_fallback_backend() -> str:
    raw = os.getenv("GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND", "none").strip().lower()
    if raw in {"none", "blastn", "kma", "nucmer"}:
        return raw
    logger.warning(
        "Invalid GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND=%r; using 'none'",
        raw,
    )
    return "none"


def cgmlst_evidence_fallback_max_loci() -> int:
    return _env_int("GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI", 300)


def cgmlst_cds_prediction_mode() -> str:
    raw = os.getenv("GMLST_CGMLST_CDS_PREDICTION_MODE", "single").strip().lower()
    if raw in {"single", "meta"}:
        return raw
    logger.warning(
        "Invalid GMLST_CGMLST_CDS_PREDICTION_MODE=%r; using default 'single'",
        raw,
    )
    return "single"


def configured_cgmlst_cds_training_file() -> Path | None:
    raw = os.getenv("GMLST_CGMLST_CDS_TRAINING_FILE", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def cgmlst_cds_closed_ends() -> bool:
    raw = os.getenv("GMLST_CGMLST_CDS_CLOSED_ENDS", "0").strip().lower()
    return raw in _TRUTHY


def cgmlst_cds_coordinates_out() -> Path | None:
    raw = os.getenv("GMLST_CGMLST_CDS_COORDINATES_OUT", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()
