"""Per-sample species resolution for ``--guess`` mode.

Guess mode types mixed-species batches unattended: every assembly is
sketched against the fingerprint database, the top organism's candidate
schemes are ranked (curated preference order, then a lone cached
candidate, then natural order), missing schemes download automatically,
and samples group into one route per scheme for the typing engine.
Samples that cannot be resolved are skipped with a reason instead of
blocking the batch.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gmlst.commands.common import status_console
from gmlst.core import species_id
from gmlst.database.scheme_prefs import (
    SchemePreference,
    resolve_preferred_scheme,
)

_FASTQ_SUFFIXES = (".fastq", ".fq", ".fastq.gz", ".fq.gz")


@dataclass
class GuessRoute:
    """One scheme plus the samples that resolved to it."""

    scheme: str
    provider: str
    samples: list[Path]


@dataclass
class GuessPlan:
    """Resolved routes plus per-sample skip reasons."""

    routes: list[GuessRoute] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def resolve_guess_routes(
    samples: Sequence[Path],
    *,
    type_set: frozenset[str],
    cache: Any,
    fingerprints: dict[str, Any],
    preferences: list[SchemePreference],
    ensure_downloads: bool = True,
) -> GuessPlan:
    """Detect each sample's species and group samples by chosen scheme."""
    plan = GuessPlan()
    payload = fingerprints.get("fingerprints", [])
    pref_type = "mlst" if "mlst" in type_set else "cgmlst"

    by_scheme: dict[tuple[str, str], list[Path]] = {}
    for sample in samples:
        if sample.name.lower().endswith(_FASTQ_SUFFIXES):
            plan.skipped.append(
                (sample, "FASTQ needs an assembly for species detection")
            )
            continue
        try:
            ranked = species_id.detect_species(
                species_id.sketch_fasta_sample(sample), payload
            )
        except OSError as exc:
            plan.skipped.append((sample, f"could not read sample: {exc}"))
            continue
        if not ranked:
            plan.skipped.append(
                (sample, "could not identify the species from fingerprints")
            )
            continue
        organism, score = ranked[0]
        if not species_id.is_unique_detection(ranked):
            status_console.print(
                f"[yellow]guess:[/yellow] {sample.name}: ambiguous species "
                f"(routing to {organism}, confidence {score:.2f})"
            )
        rows = species_id.schemes_for_organism(cache, organism, set(type_set))
        if not rows:
            plan.skipped.append(
                (
                    sample,
                    f"species '{organism}' detected but no scheme of the"
                    " requested type",
                )
            )
            continue

        chosen = _choose_scheme(rows, organism, pref_type, cache, preferences)
        row = next(r for r in rows if str(r["scheme_name"]) == chosen)
        provider = str(row.get("provider", "pubmlst"))
        scheme_type = str(row.get("scheme_type", "mlst")).lower() or "mlst"
        if ensure_downloads and not cache.is_downloaded(chosen, provider):
            try:
                cache.ensure_scheme(chosen, provider=provider, scheme_type=scheme_type)
            except Exception as exc:
                plan.skipped.append((sample, f"download failed for {chosen}: {exc}"))
                continue
        by_scheme.setdefault((chosen, provider), []).append(sample)

    for (scheme, provider), group in sorted(by_scheme.items()):
        plan.routes.append(GuessRoute(scheme=scheme, provider=provider, samples=group))
    return plan


def _choose_scheme(
    rows: list[dict[str, Any]],
    organism: str,
    pref_type: str,
    cache: Any,
    preferences: list[SchemePreference],
) -> str:
    """Curated preference order, then a lone cached candidate, then natural order."""
    candidates = [str(row["scheme_name"]) for row in rows]
    preferred = resolve_preferred_scheme(candidates, organism, pref_type, preferences)
    if preferred is not None:
        return preferred
    downloaded = [
        str(row["scheme_name"])
        for row in rows
        if cache.is_downloaded(
            str(row["scheme_name"]), str(row.get("provider", "pubmlst"))
        )
    ]
    if len(downloaded) == 1:
        return downloaded[0]
    return sorted(candidates, key=_natural_key)[0]


def _natural_key(name: str) -> list[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]
