"""Profile and report serialization for scheme-free typing (JSON/TSV)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _normalize_allele_call(locus: str, call: Any) -> str:
    if call is None:
        return "0"
    if isinstance(call, int):
        return str(call)

    call_str = str(call).strip()
    if call_str in {"", "-"}:
        return "0"
    if call_str.isdigit():
        return call_str

    prefix = f"{locus}_"
    if call_str.startswith(prefix):
        suffix = call_str[len(prefix) :]
        if suffix.isdigit():
            return suffix

    return call_str


def _normalize_profile_calls(profile: dict[str, Any]) -> dict[str, str]:
    return {
        locus: _normalize_allele_call(locus, call) for locus, call in profile.items()
    }


def profiles_to_json(profiles: list[dict[str, Any]]) -> str:
    """Serialize profiles to indented JSON with normalized allele calls."""
    normalized: list[dict[str, Any]] = []
    for profile in profiles:
        profile_copy = dict(profile)
        calls_map = profile_copy.get("profile")
        if isinstance(calls_map, dict):
            profile_copy["profile"] = _normalize_profile_calls(calls_map)
        normalized.append(profile_copy)
    return json.dumps(normalized, indent=2)


def profiles_to_tsv(profiles: list[dict[str, Any]], include_header: bool = True) -> str:
    """Render profiles as sample-by-locus TSV over the union of loci.

    Allele calls are normalized to bare numbers where possible; missing
    calls become "0".
    """
    all_loci = sorted({locus for p in profiles for locus in p.get("profile", {})})
    lines: list[str] = []
    if include_header:
        lines.append("sample\t" + "\t".join(all_loci))

    for profile in profiles:
        sample_id = str(profile.get("sample_id", ""))
        calls_map = profile.get("profile", {})
        if not isinstance(calls_map, dict):
            calls_map = {}
        calls = [
            _normalize_allele_call(locus, calls_map.get(locus)) for locus in all_loci
        ]
        lines.append(sample_id + "\t" + "\t".join(calls))

    return "\n".join(lines)


def write_scheme_json(
    output_path: Path,
    config: dict[str, Any],
    loci: dict[str, dict[str, str]],
    profiles: dict[str, dict[str, Any]],
    representatives: dict[str, str] | None = None,
) -> None:
    """Write a reusable discovered scheme as JSON.

    Shape: ``{config, loci, profiles, representatives}`` where ``loci``
    maps locus_id -> {allele_id -> sequence hash} and ``representatives``
    maps locus_id -> one representative sequence per locus.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "config": config,
        "loci": loci,
        "profiles": profiles,
        "representatives": representatives or {},
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n")


def read_scheme_json(input_path: Path) -> dict[str, Any]:
    """Load a scheme JSON previously written by :func:`write_scheme_json`.

    Legacy ``loci`` values written as allele-ID lists normalize to
    ``{allele_id: ""}`` (no hashes); a missing ``representatives`` key
    normalizes to ``{}`` so callers can detect legacy files.
    """
    scheme = json.loads(input_path.read_text())
    if not isinstance(scheme, dict):
        raise ValueError(f"Invalid scheme JSON (expected an object): {input_path}")

    loci = scheme.get("loci", {})
    if not isinstance(loci, dict):
        raise ValueError(
            f"Invalid scheme JSON ('loci' must be an object): {input_path}"
        )

    normalized_loci: dict[str, dict[str, str]] = {}
    for locus_id, alleles in loci.items():
        if isinstance(alleles, list):
            normalized_loci[str(locus_id)] = {
                str(allele_id): "" for allele_id in alleles
            }
        elif isinstance(alleles, dict):
            normalized_loci[str(locus_id)] = {
                str(allele_id): str(seq_hash) for allele_id, seq_hash in alleles.items()
            }
        else:
            raise ValueError(
                f"Invalid scheme JSON (locus '{locus_id}' must map allele IDs "
                f"to hashes or list allele IDs): {input_path}"
            )
    scheme["loci"] = normalized_loci

    representatives = scheme.get("representatives", {})
    if representatives is None:
        representatives = {}
    if not isinstance(representatives, dict):
        raise ValueError(
            f"Invalid scheme JSON ('representatives' must be an object): {input_path}"
        )
    scheme["representatives"] = {
        str(locus_id): str(sequence) for locus_id, sequence in representatives.items()
    }
    return scheme


def write_error_report_json(output_path: Path, errors: list[dict[str, str]]) -> None:
    """Write per-sample pipeline errors as an indented JSON list."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(errors, indent=2) + "\n")


def write_summary_report_json(output_path: Path, summary: dict[str, Any]) -> None:
    """Write the run summary dict as an indented JSON document."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n")
