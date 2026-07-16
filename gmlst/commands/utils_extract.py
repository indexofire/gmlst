from __future__ import annotations

import csv
import json
from pathlib import Path

import click

from gmlst.commands.common import emit_output_text
from gmlst.database.cache import DatabaseCache
from gmlst.novel import NovelAlleleWriter, NovelProfileWriter


def _extract_alleles_from_sample(
    *,
    sample_path: Path,
    scheme_name: str,
    provider: str | None,
    loci: list[str] | None,
    backend: str,
    cache_dir: Path | None,
) -> None:
    cache = DatabaseCache(cache_dir)
    if provider is None:
        provider = "pubmlst"

    scheme_obj = cache.ensure_scheme(scheme_name, provider=provider)
    from gmlst.commands.utils import run_typing

    results = run_typing(
        sample_paths=[sample_path],
        scheme_name=scheme_name,
        backend=backend,
        provider=provider,
        cache_root=cache_dir,
    )
    if not results:
        raise click.UsageError("No typing result produced for input sample")

    result = results[0]
    selected_loci = loci or scheme_obj.loci
    missing_loci = [locus for locus in selected_loci if locus not in scheme_obj.loci]
    if missing_loci:
        raise click.UsageError(
            f"Unknown loci for scheme '{scheme_name}': {missing_loci}"
        )

    lines: list[str] = []
    for locus in selected_loci:
        call = result.locus_calls.get(locus)
        if call is None or call.allele_id is None:
            continue

        sequence: str | None = None
        if call.call_type == "novel" and call.novel_sequence:
            sequence = call.novel_sequence
        else:
            for allele_obj in scheme_obj.load_alleles(locus):
                if allele_obj.allele_id == call.allele_id:
                    sequence = allele_obj.sequence
                    break

        if not sequence:
            continue

        lines.append(f">{result.sample_id}|{locus}_{call.allele_id}")
        for i in range(0, len(sequence), 60):
            lines.append(sequence[i : i + 60])

    if not lines:
        raise click.UsageError("No allele sequences extracted from typing result")
    emit_output_text("\n".join(lines), None)


def _extract_novel_from_result(
    *,
    input_path: Path,
    scheme_name: str | None,
    provider: str | None,
    backend: str,
    novel_allele: bool,
    novel_profile: bool,
    data_dir: Path,
    samples_dir: Path | None,
    cache_dir: Path | None,
) -> None:
    suffix = input_path.suffix.lower()
    if suffix == ".json":
        _extract_novel_from_json(
            input_path=input_path,
            novel_allele=novel_allele,
            novel_profile=novel_profile,
            data_dir=data_dir,
        )
        return
    if suffix in {".tsv", ".txt"}:
        if novel_allele:
            if not scheme_name:
                raise click.UsageError(
                    "TSV novel-allele extraction requires --scheme for re-typing."
                )
            if samples_dir is None:
                raise click.UsageError(
                    "TSV novel-allele extraction requires --samples-dir "
                    "to locate samples."
                )
            _extract_novel_from_tsv_with_retyping(
                input_path=input_path,
                scheme_name=scheme_name,
                provider=provider,
                backend=backend,
                data_dir=data_dir,
                cache_dir=cache_dir,
                samples_dir=samples_dir,
                novel_profile=novel_profile,
            )
            return
        if novel_profile:
            _extract_novel_profile_from_tsv(input_path=input_path, data_dir=data_dir)
            return
    raise click.UsageError(f"Unsupported input format for novel extraction: '{suffix}'")


def _extract_novel_from_json(
    *,
    input_path: Path,
    novel_allele: bool,
    novel_profile: bool,
    data_dir: Path,
) -> None:
    payload = json.loads(input_path.read_text())
    if not isinstance(payload, list):
        raise click.UsageError("Typing JSON result must be a list of sample objects")
    if not payload:
        return

    first = payload[0]
    if not isinstance(first, dict) or not isinstance(first.get("allele_calls"), dict):
        raise click.UsageError("Typing JSON format is invalid: missing allele_calls")

    loci = list(first["allele_calls"].keys())
    allele_writer = NovelAlleleWriter(data_dir) if novel_allele else None
    profile_writer = NovelProfileWriter(data_dir, loci) if novel_profile else None

    for entry in payload:
        if not isinstance(entry, dict):
            continue
        sample_id = str(entry.get("sample_id", ""))
        allele_calls = entry.get("allele_calls", {})
        if not isinstance(allele_calls, dict):
            continue

        profile_map: dict[str, str] = {}
        for locus in loci:
            call_obj = allele_calls.get(locus, {})
            if not isinstance(call_obj, dict):
                profile_map[locus] = "-"
                continue
            call_type = str(call_obj.get("call_type", ""))
            allele_id = call_obj.get("allele_id")
            if call_type == "novel":
                seq = call_obj.get("novel_sequence")
                if allele_writer is not None and isinstance(seq, str) and seq:
                    assigned = allele_writer.add_novel_allele(locus, sample_id, seq)
                    profile_map[locus] = assigned or "-"
                else:
                    profile_map[locus] = "-"
            elif isinstance(allele_id, str) and allele_id:
                profile_map[locus] = allele_id
            else:
                profile_map[locus] = "-"

        if profile_writer is not None:
            profile_writer.add_profile(sample=sample_id, allele_calls=profile_map)

    if allele_writer is not None:
        allele_writer.write()
    if profile_writer is not None:
        profile_writer.write()


def _extract_novel_profile_from_tsv(*, input_path: Path, data_dir: Path) -> None:
    with input_path.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        if not reader.fieldnames:
            raise click.UsageError("TSV has no header")
        fields = list(reader.fieldnames)
        if len(fields) < 3:
            raise click.UsageError(
                "TSV must follow typing format header: FILE, SCHEME, ST, <loci...>"
            )

        sample_field = fields[0]
        if sample_field not in {"sample", "FILE"}:
            raise click.UsageError(
                "TSV must contain either 'sample' or 'FILE' as first column"
            )

        if sample_field == "sample":
            if fields[1] != "ST":
                raise click.UsageError(
                    "TSV must follow typing format header: sample, ST, <loci...>"
                )
            loci = fields[2:]
        else:
            if fields[2] != "ST":
                raise click.UsageError(
                    "TSV must follow typing format header: FILE, SCHEME, ST, <loci...>"
                )
            loci = fields[3:]

        writer = NovelProfileWriter(data_dir, loci)
        for row in reader:
            sample = str(row.get(sample_field, ""))
            allele_calls: dict[str, str] = {}
            for locus in loci:
                value = str(row.get(locus, "")).strip()
                if (
                    not value
                    or value == "-"
                    or "~" in value
                    or "?" in value
                    or "," in value
                ):
                    allele_calls[locus] = "-"
                else:
                    allele_calls[locus] = value
            writer.add_profile(sample=sample, allele_calls=allele_calls)
        writer.write()


def _extract_novel_from_tsv_with_retyping(
    *,
    input_path: Path,
    scheme_name: str,
    provider: str | None,
    backend: str,
    data_dir: Path,
    cache_dir: Path | None,
    samples_dir: Path,
    novel_profile: bool,
) -> None:
    sample_ids: list[str] = []
    with input_path.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        if not reader.fieldnames:
            raise click.UsageError("TSV must contain a header")
        sample_field = (
            "sample"
            if "sample" in reader.fieldnames
            else ("FILE" if "FILE" in reader.fieldnames else None)
        )
        if sample_field is None:
            raise click.UsageError("TSV must contain a 'sample' or 'FILE' column")
        for row in reader:
            sample = str(row.get(sample_field, "")).strip()
            if sample:
                sample_ids.append(sample)

    if not sample_ids:
        return

    sample_paths = _resolve_sample_paths(sample_ids, samples_dir)
    chosen_provider = provider or "pubmlst"
    cache = DatabaseCache(cache_dir)
    scheme_obj = cache.ensure_scheme(scheme_name, provider=chosen_provider)
    from gmlst.commands.utils import run_typing
    from gmlst.readers.sample import SampleInput

    typing_paths: list[Path | SampleInput] = list(sample_paths)
    results = run_typing(
        sample_paths=typing_paths,
        scheme_name=scheme_name,
        backend=backend,
        provider=chosen_provider,
        cache_root=cache_dir,
    )

    loci = scheme_obj.loci
    allele_writer = NovelAlleleWriter(data_dir)
    profile_writer = NovelProfileWriter(data_dir, loci) if novel_profile else None
    for result in results:
        allele_calls: dict[str, str] = {}
        for locus in loci:
            call = result.locus_calls.get(locus)
            if call and call.call_type == "novel" and call.novel_sequence:
                assigned = allele_writer.add_novel_allele(
                    locus=locus,
                    sample=result.sample_id,
                    sequence=call.novel_sequence,
                )
                allele_calls[locus] = assigned or "-"
            elif call and call.allele_id:
                allele_calls[locus] = call.allele_id
            else:
                allele_calls[locus] = "-"
        if profile_writer is not None:
            profile_writer.add_profile(
                sample=result.sample_id, allele_calls=allele_calls
            )

    allele_writer.write()
    if profile_writer is not None:
        profile_writer.write()


def _resolve_sample_paths(sample_ids: list[str], samples_dir: Path) -> list[Path]:
    suffixes = [
        "",
        ".fasta",
        ".fa",
        ".fna",
        ".ffn",
        ".frn",
        ".fastq",
        ".fq",
        ".fasta.gz",
        ".fa.gz",
        ".fna.gz",
        ".fastq.gz",
        ".fq.gz",
    ]
    paths: list[Path] = []
    missing: list[str] = []
    for sample_id in sample_ids:
        found: Path | None = None
        for suffix in suffixes:
            candidate = samples_dir / f"{sample_id}{suffix}"
            if candidate.exists() and candidate.is_file():
                found = candidate
                break
        if found is None:
            missing.append(sample_id)
        else:
            paths.append(found)
    if missing:
        raise click.UsageError(
            f"Could not resolve sample files for IDs under --samples-dir: {missing}"
        )
    return paths
