from __future__ import annotations

from pathlib import Path


def last_allele_numbers(novel_alleles: dict[str, list]) -> dict[str, int]:
    last_numbers: dict[str, int] = {}
    for locus, alleles in novel_alleles.items():
        max_number = 0
        for allele in alleles:
            allele_id = getattr(allele, "allele_id", "")
            if allele_id.startswith("n"):
                try:
                    max_number = max(max_number, int(allele_id[1:]))
                except ValueError:
                    continue
        if max_number > 0:
            last_numbers[locus] = max_number
    return last_numbers


def build_custom_scheme_metadata(
    *,
    custom_name: str,
    scheme_type: str,
    source: str,
    source_provider: str | None,
    description: str,
    created_at: str,
    loci: list[str],
    novel_alleles: dict[str, list],
    novel_profiles: list,
) -> dict:
    return {
        "scheme": custom_name,
        "provider": "local",
        "scheme_type": scheme_type,
        "based_on": source,
        "based_on_provider": source_provider,
        "description": description,
        "created_at": created_at,
        "loci": loci,
        "novel_alleles": {
            locus: [a.allele_id for a in alleles]
            for locus, alleles in novel_alleles.items()
        },
        "novel_profiles": [p.st for p in novel_profiles],
        "last_allele_number": last_allele_numbers(novel_alleles),
    }


def merge_custom_scheme_update_metadata(
    meta: dict,
    *,
    last_allele_numbers: dict[str, int],
    current_st_num: int,
    novel_alleles: dict[str, list],
    updated_at: str,
) -> dict:
    updated = dict(meta)
    updated["last_allele_number"] = last_allele_numbers

    existing_novel_profiles = list(updated.get("novel_profiles", []))
    for index in range(len(existing_novel_profiles) + 1, current_st_num + 1):
        existing_novel_profiles.append(f"N{index}")
    updated["novel_profiles"] = existing_novel_profiles

    existing_novel_alleles = dict(updated.get("novel_alleles", {}))
    for locus, alleles in novel_alleles.items():
        existing_novel_alleles.setdefault(locus, [])
        for allele in alleles:
            existing_novel_alleles[locus].append(allele.allele_id)
    updated["novel_alleles"] = existing_novel_alleles
    updated["updated_at"] = updated_at
    return updated


def collect_novel_typing_results(
    *,
    results: list,
    allele_writer,
    profile_writer,
    logger,
) -> None:
    for result in results:
        sample_name = result.sample_id

        if allele_writer:
            for locus, call in result.locus_calls.items():
                if call.call_type == "novel" and call.novel_sequence:
                    allele_id = allele_writer.add_novel_allele(
                        locus=locus,
                        sample=sample_name,
                        sequence=call.novel_sequence,
                    )
                    if allele_id:
                        logger.debug(
                            "Assigned %s_%s to sample %s",
                            locus,
                            allele_id,
                            sample_name,
                        )

        if profile_writer:
            allele_calls = {
                locus: (call.allele_id or "-")
                for locus, call in result.locus_calls.items()
            }
            st = profile_writer.add_profile(
                sample=sample_name,
                allele_calls=allele_calls,
            )
            if st:
                logger.info("Assigned ST %s to sample %s", st, sample_name)


def create_novel_writers(
    *,
    novel_allele: bool,
    novel_profile: bool,
    output_dir: Path | None,
    loci: list[str],
    allele_writer_cls,
    profile_writer_cls,
) -> tuple[object | None, object | None]:
    if not novel_allele:
        return None, None
    novel_dir = output_dir or Path.cwd()
    allele_writer = allele_writer_cls(novel_dir)
    profile_writer = profile_writer_cls(novel_dir, loci) if novel_profile else None
    return allele_writer, profile_writer


def write_novel_outputs(*, allele_writer, profile_writer, console) -> None:
    if allele_writer:
        written = allele_writer.write()
        if written:
            console.print("[green]Novel alleles written:[/green]")
            for locus, path in written.items():
                console.print(f"  {locus}: {path}")
        else:
            console.print("[yellow]No novel alleles detected.[/yellow]")

    if profile_writer:
        profile_path = profile_writer.write()
        if profile_path:
            console.print(f"[green]Novel profiles written:[/green] {profile_path}")
        else:
            console.print("[yellow]No novel profiles detected.[/yellow]")


def finalize_novel_typing_outputs(
    *,
    results: list,
    allele_writer,
    profile_writer,
    logger,
    console,
) -> None:
    collect_novel_typing_results(
        results=results,
        allele_writer=allele_writer,
        profile_writer=profile_writer,
        logger=logger,
    )
    write_novel_outputs(
        allele_writer=allele_writer,
        profile_writer=profile_writer,
        console=console,
    )
