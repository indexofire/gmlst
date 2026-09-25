"""Species auto-detection and ``-n/--organism`` scheme resolution for typing.

Resolves which scheme a ``typing mlst``/``typing cgmlst`` run should use
when the user did not pass ``-s``: either through an organism/scheme-name
substring (``-n``) or by fingerprinting the first FASTA sample against
the local species fingerprint database.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from gmlst.commands.common import _natural_sort_key, console, status_console
from gmlst.commands.scheme_common import _load_schemes, build_fingerprints_with_progress
from gmlst.commands.scheme_render import _build_scheme_list_table
from gmlst.core import species_id
from gmlst.database.cache import DatabaseCache
from gmlst.database.providers.base import SchemeInfo

# How many top-scoring organisms contribute schemes to the interactive
# selection when detection is ambiguous.
_AMBIGUOUS_ORGANISM_WINDOW = 5

_MLST_TYPES = frozenset({"mlst"})
_CGMLST_TYPES = frozenset({"cgmlst", "wgmlst"})


def _scheme_types_for_mode(mode: str) -> tuple[frozenset[str], str]:
    if mode == "cgmlst":
        return _CGMLST_TYPES, "cgMLST/wgMLST"
    return _MLST_TYPES, "MLST"


def _is_fastq_path(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith((".fastq", ".fq", ".fastq.gz", ".fq.gz"))


def _stdin_is_interactive() -> bool:
    return sys.stdin.isatty()


def resolve_scheme_for_typing(
    *,
    mode: str,
    scheme: str | None,
    organism: str | None,
    samples: tuple[Path, ...],
    cache_dir: Path | None,
) -> str:
    """Resolve the scheme name for a typing command before the run starts.

    ``-s`` passes through unchanged; ``-n`` resolves by catalog substring;
    with neither, the species is detected from the first FASTA sample.
    Raises ``click.UsageError`` (exit 2) for fixable input problems.
    """
    if scheme is not None and organism is not None:
        raise click.UsageError("Use either -s/--scheme or -n/--organism, not both.")
    if scheme is not None:
        return scheme

    type_set, type_label = _scheme_types_for_mode(mode)
    cache = DatabaseCache(cache_dir)

    if organism is not None:
        return _resolve_by_organism(
            organism=organism, type_set=type_set, type_label=type_label, cache=cache
        )

    fasta_samples = [path for path in samples if not _is_fastq_path(path)]
    if not fasta_samples:
        raise click.UsageError(
            "Species auto-detection requires a FASTA assembly; "
            "specify -s <scheme> or -n <organism> for FASTQ input."
        )
    return _resolve_by_detection(
        fasta=fasta_samples[0], type_set=type_set, type_label=type_label, cache=cache
    )


def _sorted_candidates(
    cache: DatabaseCache, rows: list[SchemeInfo]
) -> list[SchemeInfo]:
    """Order candidates like ``scheme list``: downloaded first, natural sort."""
    return sorted(
        rows,
        key=lambda row: (
            not cache.is_downloaded(row.scheme_name, row.provider),
            _natural_sort_key(row.scheme_name),
        ),
    )


def _resolve_by_organism(
    *,
    organism: str,
    type_set: frozenset[str],
    type_label: str,
    cache: DatabaseCache,
) -> str:
    """Resolve a unique scheme from an organism/scheme-name substring."""
    needle = organism.strip().lower()
    matches = [
        info
        for info in _load_schemes(cache, "all", "all")
        if info.scheme_type.lower() in type_set
        and (needle in info.organism.lower() or needle in info.scheme_name.lower())
    ]
    if not matches:
        raise click.UsageError(
            f"No {type_label} schemes match organism '{organism}'. "
            "Browse schemes with: gmlst scheme list -n <pattern>"
        )
    matches = _sorted_candidates(cache, matches)
    if len(matches) == 1:
        chosen = matches[0]
        status_console.print(
            f"\\[auto-selected] {chosen.scheme_name} via -n '{organism}'"
        )
        return chosen.scheme_name
    title = f"Schemes matching '{organism}' ({len(matches)})"
    console.print(_build_scheme_list_table(matches, cache, title, console.size.width))
    status_console.print("\nDownload: [bold]gmlst scheme download <scheme_name>[/bold]")
    raise click.UsageError(
        f"Multiple {type_label} schemes match -n '{organism}'. "
        "Re-run with -s <scheme_name> or a more specific -n value."
    )


def _resolve_by_detection(
    *,
    fasta: Path,
    type_set: frozenset[str],
    type_label: str,
    cache: DatabaseCache,
) -> str:
    """Detect the species from *fasta* and resolve a scheme for it."""
    fingerprints_file = species_id.fingerprints_path(cache)
    if fingerprints_file.exists():
        payload = species_id.load_fingerprints(fingerprints_file)
    else:
        bundled = species_id.bundled_fingerprints_path()
        if bundled is not None:
            payload = species_id.load_fingerprints(bundled)
        elif _stdin_is_interactive() and click.confirm(
            "Species fingerprint database not found. "
            "Download and build it now? (downloads ~one small MLST scheme per organism)"
        ):
            payload, _counts = build_fingerprints_with_progress(cache)
            species_id.save_fingerprints(payload, fingerprints_file)
        else:
            raise click.UsageError(
                "Species fingerprint database not found. "
                "Run: gmlst scheme update-fingerprints"
            )

    try:
        query_hashes = species_id.sketch_fasta_sample(fasta)
    except OSError as exc:
        raise click.UsageError(
            f"Could not read '{fasta}' for species detection: {exc}"
        ) from exc

    ranked = species_id.detect_species(query_hashes, payload.get("fingerprints", []))
    if not ranked:
        raise click.UsageError(
            f"Could not identify the species of '{fasta.name}' "
            "from the fingerprint database. Specify -s <scheme> or -n <organism>."
        )

    if species_id.is_unique_detection(ranked):
        organism, score = ranked[0]
        rows = _organism_scheme_infos(cache, organism, type_set)
        if len(rows) == 1:
            status_console.print(
                f"\\[auto-selected] {rows[0].scheme_name} "
                f"(species {organism}, confidence {score:.2f})"
            )
            return rows[0].scheme_name
        if not rows:
            raise click.UsageError(
                f"Detected species '{organism}' (confidence {score:.2f}) but no "
                f"{type_label} scheme is available for it. Specify -s or -n."
            )
        downloaded = [
            row for row in rows if cache.is_downloaded(row.scheme_name, row.provider)
        ]
        if len(downloaded) == 1:
            status_console.print(
                f"\\[auto-selected] {downloaded[0].scheme_name} "
                f"(species {organism}, confidence {score:.2f}; "
                "only cached candidate)"
            )
            return downloaded[0].scheme_name
        return _prompt_scheme_choice(
            cache, rows, {organism: score}, type_label, via="species detection"
        )

    window = ranked[:_AMBIGUOUS_ORGANISM_WINDOW]
    score_by_organism = dict(window)
    rows: list[SchemeInfo] = []
    for organism, _score in window:
        rows.extend(_organism_scheme_infos(cache, organism, type_set))
    if not rows:
        top = ", ".join(f"{organism} ({score:.2f})" for organism, score in ranked[:3])
        raise click.UsageError(
            f"Species of '{fasta.name}' is ambiguous (top matches: {top}) and no "
            f"{type_label} scheme is available for them. Specify -s or -n."
        )
    return _prompt_scheme_choice(
        cache, rows, score_by_organism, type_label, via="species detection"
    )


def _organism_scheme_infos(
    cache: DatabaseCache,
    organism: str,
    type_set: frozenset[str],
) -> list[SchemeInfo]:
    """Catalog candidates for *organism* as ``scheme list``-style rows."""
    rows = species_id.schemes_for_organism(cache, organism, set(type_set))
    return [SchemeInfo.from_dict(row) for row in rows]


def _prompt_scheme_choice(
    cache: DatabaseCache,
    rows: list[SchemeInfo],
    score_by_organism: dict[str, float],
    type_label: str,
    *,
    via: str,
) -> str:
    """Numbered candidate list plus interactive selection (or exit 2)."""
    rows = _sorted_candidates(cache, rows)
    for index, row in enumerate(rows, 1):
        score = score_by_organism.get(row.organism)
        confidence = f" (species confidence {score:.2f})" if score is not None else ""
        is_cached = cache.is_downloaded(row.scheme_name, row.provider)
        cached = " (cached)" if is_cached else ""
        click.echo(
            f"{index}. {row.scheme_name}{cached} — {row.organism} "
            f"[{row.scheme_type}, {row.n_loci or '?'} loci]{confidence}"
        )
    if not _stdin_is_interactive():
        raise click.UsageError(
            f"Multiple candidate {type_label} schemes; run interactively to select "
            "one, or re-run with -s <scheme_name> / -n <organism>."
        )
    choice = click.prompt("Select scheme", type=click.IntRange(1, len(rows)))
    chosen = rows[choice - 1]
    status_console.print(
        f"\\[auto-selected] {chosen.scheme_name} ({via}, user selection)"
    )
    return chosen.scheme_name
