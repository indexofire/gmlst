from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path

import click

from gmlst.commands.common import console, emit_output_json, err_console
from gmlst.commands.scheme_common import (
    HELP_SETTINGS,
    _exit_no_novel_data,
    _exit_validation_errors,
    _find_catalog_scheme_matches,
    _locked_local_catalog,
    _write_wrapped_sequence,
)
from gmlst.database.cache import DatabaseCache
from gmlst.fasta_io import utc_now_iso
from gmlst.novel.service import (
    build_custom_scheme_metadata,
    merge_custom_scheme_update_metadata,
)


@click.command("create", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.option(
    "--type",
    "-t",
    "scheme_type",
    required=True,
    type=click.Choice(["mlst"], case_sensitive=False),
    help="Scheme type (only mlst supported currently).",
)
@click.option(
    "--source",
    "-s",
    required=True,
    help="Source scheme to extend (e.g., saureus_1, ecoli_1).",
)
@click.option(
    "--data-dir",
    "--datadir",
    "data_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing *_novel.fasta and profiles_novel.txt.",
)
@click.option(
    "--desc",
    default="",
    help="Description for the custom scheme.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_create(
    scheme_type: str,
    source: str,
    data_dir: Path,
    desc: str,
    cache_dir: Path | None,
) -> None:
    """Create a custom scheme by merging public scheme with novel data.

    The custom scheme will be named automatically (custom_1, custom_2, ...).
    """
    from gmlst.novel import NovelDataReader

    cache = DatabaseCache(cache_dir)

    source_matches = _find_catalog_scheme_matches(
        cache,
        source,
        ignore_catalog_errors=True,
    )
    source_provider = source_matches[0][0] if source_matches else None

    if not source_provider:
        err_console.print(f"[red]Error:[/red] Source scheme '{source}' not found.")
        err_console.print("Run 'gmlst scheme list' to see available schemes.")
        sys.exit(1)

    # Ensure source scheme is cached
    try:
        source_scheme = cache.ensure_scheme(source, provider=source_provider)
    except Exception as exc:
        err_console.print(f"[red]Error:[/red] Could not load source scheme: {exc}")
        sys.exit(1)

    # Read novel data
    reader = NovelDataReader(data_dir)
    novel_alleles, novel_profiles = reader.read_all()

    if not novel_alleles and not novel_profiles:
        _exit_no_novel_data(show_expected_hint=True)

    # Validate novel data against source scheme
    errors = reader.validate_against_scheme(
        novel_alleles, novel_profiles, source_scheme.loci
    )
    _exit_validation_errors(errors)

    with _locked_local_catalog(cache):
        # Get next custom scheme number
        custom_id = _get_next_custom_id(cache)
        custom_name = f"custom_{custom_id}"

        console.print(
            f"Creating [cyan]{custom_name}[/cyan] based on [cyan]{source}[/cyan]..."
        )

        # Create custom scheme directory
        custom_dir = cache.scheme_dir(custom_name, provider="local")
        custom_dir.mkdir(parents=True, exist_ok=True)

        # Merge allele files
        for locus in source_scheme.loci:
            source_file = source_scheme.allele_files.get(locus)
            if not source_file:
                continue

            target_file = custom_dir / f"{locus}.tfa"

            # Copy original alleles
            with open(target_file, "w") as out:
                # Write original alleles
                if source_file.exists():
                    with open(source_file) as f:
                        out.write(f.read())

                # Append novel alleles for this locus
                if locus in novel_alleles:
                    for allele in novel_alleles[locus]:
                        samples_str = " ".join(allele.samples)
                        out.write(f">{locus}_{allele.allele_id} sample={samples_str}\n")
                        _write_wrapped_sequence(out, allele.sequence)

        # Merge profiles
        source_profile = source_scheme.profile_file
        target_profile = custom_dir / f"{custom_name}.txt"

        with open(target_profile, "w") as out:
            # Write header
            header = "ST\t" + "\t".join(source_scheme.loci) + "\n"
            out.write(header)

            # Copy original profiles
            if source_profile and source_profile.exists():
                with open(source_profile) as f:
                    reader_csv = csv.DictReader(f, delimiter="\t")
                    for row in reader_csv:
                        st = row.get("ST", "")
                        parts = [st]
                        for locus in source_scheme.loci:
                            parts.append(row.get(locus, "-"))
                        out.write("\t".join(parts) + "\n")

            # Append novel profiles
            for profile in novel_profiles:
                parts = [profile.st]
                for locus in source_scheme.loci:
                    parts.append(profile.allele_calls.get(locus, "-"))
                out.write("\t".join(parts) + "\n")

        # Write metadata
        meta = build_custom_scheme_metadata(
            custom_name=custom_name,
            scheme_type=scheme_type,
            source=source,
            source_provider=source_provider,
            description=desc,
            created_at=utc_now_iso(),
            loci=source_scheme.loci,
            novel_alleles=novel_alleles,
            novel_profiles=novel_profiles,
        )

        meta_file = custom_dir / ".meta.json"
        emit_output_json(meta, meta_file)

        # Update local catalog
        _update_local_catalog(cache, custom_name, source, desc, len(source_scheme.loci))

    console.print(f"[green]Created custom scheme:[/green] {custom_name}")
    console.print(f"  Location: {custom_dir}")
    console.print(f"  Based on: {source} ({source_provider})")
    console.print(f"  Novel alleles: {sum(len(a) for a in novel_alleles.values())}")
    console.print(f"  Novel profiles: {len(novel_profiles)}")


def _get_next_custom_id(cache: DatabaseCache) -> int:
    """Get the next available custom scheme ID."""
    catalog_path = cache._catalog_path("local")

    if not catalog_path.exists():
        return 1

    try:
        data = json.loads(catalog_path.read_text())
        schemes = data.get("schemes", [])

        max_id = 0
        for scheme in schemes:
            name = scheme.get("scheme_name", "")
            if name.startswith("custom_"):
                try:
                    num = int(name.split("_")[1])
                    max_id = max(max_id, num)
                except (IndexError, ValueError):
                    continue

        return max_id + 1
    except (OSError, json.JSONDecodeError) as exc:
        logging.getLogger(__name__).warning(
            "Failed to read local catalog for custom ID: %s", exc
        )
        return 1


def _update_local_catalog(
    cache: DatabaseCache,
    scheme_name: str,
    based_on: str,
    description: str,
    n_loci: int,
) -> None:
    """Add custom scheme to local catalog."""
    catalog_path = cache._catalog_path("local")

    schemes: list[dict[str, object]] = []
    if catalog_path.exists():
        try:
            data = json.loads(catalog_path.read_text())
            schemes = data.get("schemes", [])
        except (OSError, json.JSONDecodeError) as exc:
            logging.getLogger(__name__).warning(
                "Failed to read local catalog for update: %s", exc
            )

    # Check if scheme already exists
    existing = next((s for s in schemes if s.get("scheme_name") == scheme_name), None)

    scheme_info = {
        "scheme_name": scheme_name,
        "display_name": description or scheme_name,
        "organism": f"Custom ({based_on})",
        "scheme_type": "mlst",
        "n_loci": n_loci,
        "provider": "local",
        "extra": {"based_on": based_on, "custom": True},
    }

    if existing:
        # Update existing
        existing.update(scheme_info)
    else:
        schemes.append(scheme_info)

    payload = {
        "provider": "local",
        "scheme_type": "mlst",
        "updated_at": utc_now_iso(),
        "count": len(schemes),
        "schemes": schemes,
    }

    emit_output_json(payload, catalog_path)


@click.command(
    "update-custom",
    context_settings=HELP_SETTINGS,
    no_args_is_help=True,
)
@click.argument("scheme", required=False)
@click.option(
    "--scheme",
    "-s",
    "scheme_opt",
    hidden=True,
    help="[deprecated] Use positional argument instead.",
)
@click.option(
    "--data-dir",
    "--datadir",
    "data_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing new *_novel.fasta and profiles_novel.txt.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_update_custom(
    scheme: str | None,
    scheme_opt: str | None,
    data_dir: Path,
    cache_dir: Path | None,
) -> None:
    """Update a custom scheme with additional novel data.

    SCHEME is the custom scheme name (e.g., custom_1).
    Only works with local (custom) schemes. The novel data will be merged
    with the existing scheme, continuing the numbering from where it left off.
    """
    scheme = scheme or scheme_opt
    if not scheme:
        raise click.UsageError("Scheme name is required.")
    from gmlst.novel import NovelDataReader

    cache = DatabaseCache(cache_dir)

    # Verify this is a local scheme
    if not scheme.startswith("custom_"):
        err_console.print(
            f"[red]Error:[/red] Scheme '{scheme}' is not a custom scheme. "
            "Only custom schemes (custom_*) can be updated."
        )
        sys.exit(1)

    scheme_dir = cache.scheme_dir(scheme, provider="local")
    if not scheme_dir.exists():
        err_console.print(f"[red]Error:[/red] Custom scheme '{scheme}' not found.")
        sys.exit(1)

    # Load existing metadata
    meta_file = scheme_dir / ".meta.json"
    if not meta_file.exists():
        err_console.print(
            f"[red]Error:[/red] Scheme metadata not found for '{scheme}'."
        )
        sys.exit(1)

    meta = json.loads(meta_file.read_text())
    loci = meta.get("loci", [])

    # Read new novel data
    reader = NovelDataReader(data_dir)
    novel_alleles, novel_profiles = reader.read_all()

    if not novel_alleles and not novel_profiles:
        _exit_no_novel_data(show_expected_hint=False)

    # Validate against scheme
    errors = reader.validate_against_scheme(novel_alleles, novel_profiles, loci)
    _exit_validation_errors(errors)

    # Get current allele numbers for each locus
    last_allele_nums = meta.get("last_allele_number", {})
    current_st_num = 0
    for st_str in meta.get("novel_profiles", []):
        try:
            num = int(st_str.replace("N", ""))
            current_st_num = max(current_st_num, num)
        except ValueError:
            pass

    console.print(f"Updating [cyan]{scheme}[/cyan]...")

    # Renumber new alleles and append to .tfa files
    allele_mapping = {}  # Maps old allele IDs to new ones

    for locus in loci:
        if locus not in novel_alleles:
            continue

        last_num = last_allele_nums.get(locus, 0)

        # Renumber new alleles
        for allele in novel_alleles[locus]:
            last_num += 1
            new_id = f"n{last_num}"
            old_id = allele.allele_id
            allele_mapping[f"{locus}_{old_id}"] = f"{locus}_{new_id}"
            allele.allele_id = new_id

        last_allele_nums[locus] = last_num

        # Append to .tfa file
        tfa_file = scheme_dir / f"{locus}.tfa"
        with open(tfa_file, "a") as f:
            for allele in novel_alleles[locus]:
                samples_str = " ".join(allele.samples)
                f.write(f">{locus}_{allele.allele_id} sample={samples_str}\n")
                _write_wrapped_sequence(f, allele.sequence)

    # Renumber new profiles and append
    profile_file = scheme_dir / f"{scheme}.txt"

    with open(profile_file, "a") as f:
        for profile in novel_profiles:
            current_st_num += 1
            st = f"N{current_st_num}"

            # Replace allele IDs using mapping
            parts = [st]
            for locus in loci:
                allele = profile.allele_calls.get(locus, "-")
                # Check if this allele needs remapping
                mapped_key = f"{locus}_{allele}"
                if mapped_key in allele_mapping:
                    # Extract just the nX part
                    allele = allele_mapping[mapped_key].split("_")[1]
                parts.append(allele)

            f.write("\t".join(parts) + "\n")

    # Update metadata
    meta = merge_custom_scheme_update_metadata(
        meta,
        last_allele_numbers=last_allele_nums,
        current_st_num=current_st_num,
        novel_alleles=novel_alleles,
        updated_at=utc_now_iso(),
    )
    emit_output_json(meta, meta_file)

    console.print(f"[green]Updated custom scheme:[/green] {scheme}")
    console.print(f"  New alleles added: {sum(len(a) for a in novel_alleles.values())}")
    console.print(f"  New profiles added: {len(novel_profiles)}")
