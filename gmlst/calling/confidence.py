"""Confidence scoring utilities for MLST calls."""

from __future__ import annotations

from gmlst.calling.st_lookup import STResult


def overall_confidence(result: STResult) -> float:
    """Return an overall 0–1 confidence score for an ST result.

    Computed as the geometric mean of per-locus confidences.  A missing or
    partial locus contributes a confidence of 0 or 0.5 respectively.
    """
    if not result.locus_calls:
        return 0.0

    product = 1.0
    for call in result.locus_calls.values():
        if call.call_type == "missing":
            product *= 0.0
        elif call.call_type == "partial":
            product *= 0.5 * call.confidence
        else:
            product *= call.confidence

    n = len(result.locus_calls)
    return product ** (1.0 / n) if n > 0 else 0.0


def summarise_warnings(result: STResult) -> list[str]:
    """Return human-readable warning strings for quality issues."""
    warnings: list[str] = []

    for locus, call in result.locus_calls.items():
        if call.call_type == "missing":
            warnings.append(f"Locus '{locus}' not found in assembly")
        elif call.call_type == "partial":
            cov_str = (
                f"{call.best_match.coverage:.0%}" if call.best_match else "unknown"
            )
            warnings.append(f"Locus '{locus}' has partial coverage ({cov_str})")
        elif call.call_type in ("closest", "novel") and call.best_match:
            warnings.append(
                f"Locus '{locus}' allele {call.allele_id}: "
                f"{call.best_match.identity:.1f}% identity "
                f"(possible novel allele)"
            )
        if call.multiple_hits:
            warnings.append(
                f"Locus '{locus}': multiple high-quality hits (possible paralog)"
            )

    return warnings
