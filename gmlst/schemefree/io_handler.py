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
    normalized: list[dict[str, Any]] = []
    for profile in profiles:
        profile_copy = dict(profile)
        calls_map = profile_copy.get("profile")
        if isinstance(calls_map, dict):
            profile_copy["profile"] = _normalize_profile_calls(calls_map)
        normalized.append(profile_copy)
    return json.dumps(normalized, indent=2)


def profiles_to_tsv(profiles: list[dict[str, Any]], include_header: bool = True) -> str:
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
    loci: dict[str, list[str]],
    profiles: dict[str, dict[str, Any]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "config": config,
        "loci": loci,
        "profiles": profiles,
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n")


def read_scheme_json(input_path: Path) -> dict[str, Any]:
    return json.loads(input_path.read_text())


def write_error_report_json(output_path: Path, errors: list[dict[str, str]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(errors, indent=2) + "\n")


def write_summary_report_json(output_path: Path, summary: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n")
