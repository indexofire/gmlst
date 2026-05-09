from __future__ import annotations

import csv
import json
import logging
import resource
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click

from gmlst.aligners import AVAILABLE_BACKENDS, get_aligner
from gmlst.commands.common import (
    emit_output_table,
    emit_output_text,
    emit_output_tsv,
    render_delimited_rows,
    render_from_format,
)
from gmlst.core import run_typing
from gmlst.database.cache import DatabaseCache
from gmlst.novel import NovelAlleleWriter, NovelProfileWriter
from gmlst.readers.fasta import FastaReader
from gmlst.readers.sample import SampleInput, prepare_sample_inputs

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}
logger = logging.getLogger("gmlst.benchmark")


@click.group(
    "utils",
    context_settings=HELP_SETTINGS,
    no_args_is_help=True,
)
def utils_group() -> None:
    """Utility commands for extraction, concatenation, and benchmarking."""


@utils_group.command("check", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.option(
    "--backend",
    "-b",
    required=True,
    type=click.Choice(AVAILABLE_BACKENDS, case_sensitive=False),
    help="Backend to check dependency installation.",
)
def cmd_check(backend: str) -> None:
    """Check whether backend dependency is installed and available."""
    aligner = get_aligner(backend)
    try:
        aligner.check_dependencies()
    except Exception as exc:
        click.echo(f"[FAIL] backend={backend}: {exc}", err=True)
        sys.exit(1)

    click.echo(f"[OK] backend={backend} is available")


@utils_group.command("extract", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.option(
    "--input",
    "input_path",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Typing result file (.json/.tsv) or sample genome FASTA.",
)
@click.option("--scheme", "-s", help="Scheme name (required for allele extraction).")
@click.option("--provider", "-p", help="Provider (auto-detected if omitted).")
@click.option(
    "--allele",
    help="Comma-separated loci to extract (default: all loci in scheme).",
)
@click.option(
    "--backend",
    "-b",
    default="blastn",
    show_default=True,
    help="Backend used for allele extraction from sample FASTA.",
)
@click.option(
    "--novel-allele",
    is_flag=True,
    help="Extract novel allele sequences to {locus}_novel.fasta.",
)
@click.option(
    "--novel-profile",
    is_flag=True,
    help="Extract/append novel profiles to profiles_novel.txt.",
)
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    help="Directory to write extracted novel data.",
)
@click.option(
    "--samples-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing sample files for TSV novel-allele extraction.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
def cmd_extract(
    input_path: Path,
    scheme: str | None,
    provider: str | None,
    allele: str | None,
    backend: str,
    novel_allele: bool,
    novel_profile: bool,
    data_dir: Path | None,
    samples_dir: Path | None,
    cache_dir: Path | None,
) -> None:
    """Extract allele/novel data from samples or typing results."""
    if novel_allele or novel_profile:
        target_dir = data_dir or Path.cwd()
        _extract_novel_from_result(
            input_path=input_path,
            scheme_name=scheme,
            provider=provider,
            backend=backend,
            novel_allele=novel_allele,
            novel_profile=novel_profile,
            data_dir=target_dir,
            samples_dir=samples_dir,
            cache_dir=cache_dir,
        )
        return

    if not scheme:
        raise click.UsageError("--scheme is required for allele extraction mode")

    loci = None
    if allele:
        loci = [item.strip() for item in allele.split(",") if item.strip()]
        if not loci:
            raise click.UsageError("--allele is empty; provide comma-separated loci")

    _extract_alleles_from_sample(
        sample_path=input_path,
        scheme_name=scheme,
        provider=provider,
        loci=loci,
        backend=backend,
        cache_dir=cache_dir,
    )


@utils_group.command("concat", context_settings=HELP_SETTINGS, no_args_is_help=True)
@click.option(
    "--input",
    "input_path",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="FASTA file containing extracted allele records.",
)
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output FASTA path."
)
def cmd_concat(input_path: Path, output: Path | None) -> None:
    """Concatenate multi-record FASTA into one sequence record."""
    records = list(FastaReader(input_path).records())
    if not records:
        raise click.UsageError(f"No FASTA records found in '{input_path}'")

    sequence = "".join(record.sequence for record in records)
    header = f"{input_path.stem}_concat"
    lines = [f">{header}"]
    for i in range(0, len(sequence), 60):
        lines.append(sequence[i : i + 60])
    text = "\n".join(lines) + "\n"
    emit_output_text(text, output)


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

    results = run_typing(
        sample_paths=sample_paths,
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


@dataclass
class BackendMetrics:
    backend: str
    n_samples: int = 0
    total_wall_time: float = 0.0
    peak_memory_mb: float = 0.0
    n_exact_sts: int = 0
    n_novel_sts: int = 0
    n_failed: int = 0
    n_repeats: int = 1
    n_failed_runs: int = 0
    repeat_wall_times: list[float] = field(default_factory=list)

    @property
    def avg_time_per_sample(self) -> float:
        return self.avg_time_per_run / self.n_samples if self.n_samples else 0.0

    @property
    def avg_time_per_run(self) -> float:
        return self.total_wall_time / self.n_repeats if self.n_repeats else 0.0

    @property
    def std_time_per_run(self) -> float:
        if len(self.repeat_wall_times) <= 1:
            return 0.0
        return statistics.pstdev(self.repeat_wall_times)

    @property
    def success_rate(self) -> float:
        return (
            (self.n_samples - self.n_failed) / self.n_samples if self.n_samples else 0.0
        )


@dataclass
class BenchmarkResult:
    scheme: str
    samples: list[Path | SampleInput]
    metrics: dict[str, BackendMetrics] = field(default_factory=dict)


def run_benchmark(
    scheme_name: str,
    sample_paths: list[Path | SampleInput],
    backends: list[str],
    *,
    provider: str | None = None,
    repeat: int = 1,
    cache_root: Path | None = None,
    force_reindex: bool = False,
) -> BenchmarkResult:
    cache = DatabaseCache(cache_root)
    resolved_provider = provider or cache.detect_provider(scheme_name) or "pubmlst"
    cache.ensure_scheme(scheme_name, provider=resolved_provider)
    result = BenchmarkResult(scheme=scheme_name, samples=sample_paths)

    repeats = max(1, repeat)
    for backend_name in backends:
        logger.info("Benchmarking backend: %s", backend_name)
        metrics = BackendMetrics(
            backend=backend_name,
            n_samples=len(sample_paths),
            n_repeats=repeats,
        )
        for run_index in range(repeats):
            t_wall_start = time.perf_counter()
            try:
                backend_results = run_typing(
                    sample_paths=sample_paths,
                    scheme_name=scheme_name,
                    backend=backend_name,
                    provider=resolved_provider,
                    cache_root=cache_root,
                    force_reindex=force_reindex,
                )
            except Exception as exc:
                logger.error(
                    "Error running benchmark backend %s (run %d/%d): %s",
                    backend_name,
                    run_index + 1,
                    repeats,
                    exc,
                )
                metrics.n_failed_runs += 1
                backend_results = []
            elapsed = time.perf_counter() - t_wall_start
            metrics.repeat_wall_times.append(elapsed)
            metrics.total_wall_time += elapsed

            if metrics.n_exact_sts + metrics.n_novel_sts + metrics.n_failed:
                continue

            for st_result in backend_results:
                if st_result.st is not None and not st_result.is_novel:
                    metrics.n_exact_sts += 1
                elif st_result.st is not None:
                    metrics.n_novel_sts += 1
                else:
                    metrics.n_failed += 1

            if len(backend_results) < len(sample_paths):
                metrics.n_failed += len(sample_paths) - len(backend_results)

        if metrics.n_exact_sts + metrics.n_novel_sts + metrics.n_failed == 0:
            metrics.n_failed = len(sample_paths)

        try:
            ru = resource.getrusage(resource.RUSAGE_SELF)
            metrics.peak_memory_mb = ru.ru_maxrss / 1024
        except AttributeError:
            pass

        result.metrics[backend_name] = metrics

    return result


def print_report(result: BenchmarkResult) -> None:
    print(render_report(result), end="")


def render_report(result: BenchmarkResult) -> str:
    lines = [
        f"\n{'=' * 70}",
        f"Benchmark results — scheme: {result.scheme}",
        f"Samples tested: {len(result.samples)}",
        f"{'=' * 70}",
        (
            f"{'Backend':<12} {'Avg(s)':>8} {'Std(s)':>8} {'ms/sample':>10} "
            f"{'ExactST':>8} {'Novel':>6} {'Failed':>6} {'FailRun':>7} {'Mem(MB)':>8}"
        ),
        "-" * 70,
    ]
    for _backend_name, metrics in sorted(result.metrics.items()):
        ms_per = metrics.avg_time_per_sample * 1000
        lines.append(
            f"{metrics.backend:<12} {metrics.avg_time_per_run:>8.2f} "
            f"{metrics.std_time_per_run:>8.2f} {ms_per:>10.1f} "
            f"{metrics.n_exact_sts:>8} {metrics.n_novel_sts:>6} "
            f"{metrics.n_failed:>6} {metrics.n_failed_runs:>7} "
            f"{metrics.peak_memory_mb:>8.1f}"
        )
    lines.append(f"{'=' * 70}\n")
    return "\n".join(lines)


def to_tsv(result: BenchmarkResult) -> str:
    lines = [
        "\t".join(
            [
                "backend",
                "total_time_s",
                "avg_time_s",
                "std_time_s",
                "ms_per_sample",
                "n_repeats",
                "n_exact_st",
                "n_novel_st",
                "n_failed",
                "n_failed_runs",
                "peak_mem_mb",
                "success_rate",
            ]
        )
    ]
    for _backend_name, metrics in sorted(result.metrics.items()):
        lines.append(
            "\t".join(
                [
                    metrics.backend,
                    f"{metrics.total_wall_time:.3f}",
                    f"{metrics.avg_time_per_run:.3f}",
                    f"{metrics.std_time_per_run:.3f}",
                    f"{metrics.avg_time_per_sample * 1000:.1f}",
                    str(metrics.n_repeats),
                    str(metrics.n_exact_sts),
                    str(metrics.n_novel_sts),
                    str(metrics.n_failed),
                    str(metrics.n_failed_runs),
                    f"{metrics.peak_memory_mb:.1f}",
                    f"{metrics.success_rate:.3f}",
                ]
            )
        )
    return "\n".join(lines)


def to_json(result: BenchmarkResult) -> str:
    payload = {
        "scheme": result.scheme,
        "n_samples": len(result.samples),
        "metrics": {
            backend: {
                "backend": metric.backend,
                "total_time_s": metric.total_wall_time,
                "avg_time_s": metric.avg_time_per_run,
                "std_time_s": metric.std_time_per_run,
                "ms_per_sample": metric.avg_time_per_sample * 1000,
                "n_repeats": metric.n_repeats,
                "n_exact_st": metric.n_exact_sts,
                "n_novel_st": metric.n_novel_sts,
                "n_failed": metric.n_failed,
                "n_failed_runs": metric.n_failed_runs,
                "peak_mem_mb": metric.peak_memory_mb,
                "success_rate": metric.success_rate,
            }
            for backend, metric in sorted(result.metrics.items())
        },
    }
    return json.dumps(payload, indent=2)


def run_cgmlst_gate(
    *,
    scheme_name: str,
    sample_paths: list[Path | SampleInput],
    backend: str,
    cache_root: Path | None = None,
    force_reindex: bool = False,
) -> dict[str, Any]:
    on_results = run_typing(
        sample_paths=sample_paths,
        scheme_name=scheme_name,
        backend=backend,
        scheme_type="cgmlst",
        cache_root=cache_root,
        force_reindex=force_reindex,
        prefilter_enabled=True,
    )
    off_results = run_typing(
        sample_paths=sample_paths,
        scheme_name=scheme_name,
        backend=backend,
        scheme_type="cgmlst",
        cache_root=cache_root,
        force_reindex=force_reindex,
        prefilter_enabled=False,
    )
    by_sample_on = {result.sample_id: result for result in on_results}
    by_sample_off = {result.sample_id: result for result in off_results}
    sample_ids = sorted(set(by_sample_on) | set(by_sample_off))

    mismatches: list[str] = []
    mismatch_details: list[dict[str, Any]] = []
    for sample_id in sample_ids:
        result_on = by_sample_on.get(sample_id)
        result_off = by_sample_off.get(sample_id)
        if result_on is None or result_off is None:
            mismatches.append(sample_id)
            mismatch_details.append(
                {
                    "sample_id": sample_id,
                    "st_on": None if result_on is None else result_on.st,
                    "st_off": None if result_off is None else result_off.st,
                    "differing_loci": [{"locus": "*missing*", "on": "", "off": ""}],
                }
            )
            continue
        differing_loci = _diff_loci(result_on, result_off)
        if result_on.st != result_off.st or differing_loci:
            mismatches.append(sample_id)
            mismatch_details.append(
                {
                    "sample_id": sample_id,
                    "st_on": result_on.st,
                    "st_off": result_off.st,
                    "differing_loci": differing_loci,
                }
            )

    return {
        "mode": "cgmlst-gate",
        "scheme": scheme_name,
        "backend": backend,
        "n_samples": len(sample_ids),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "mismatch_details": mismatch_details,
    }


def _diff_loci(result_on: Any, result_off: Any) -> list[dict[str, str]]:
    by_locus_on = {
        locus: str(getattr(call, "allele_id", "") or "")
        for locus, call in result_on.locus_calls.items()
    }
    by_locus_off = {
        locus: str(getattr(call, "allele_id", "") or "")
        for locus, call in result_off.locus_calls.items()
    }
    diffs: list[dict[str, str]] = []
    for locus in sorted(set(by_locus_on) | set(by_locus_off)):
        on_value = by_locus_on.get(locus, "")
        off_value = by_locus_off.get(locus, "")
        if on_value != off_value:
            diffs.append({"locus": locus, "on": on_value, "off": off_value})
    return diffs


def _render_cgmlst_gate_tsv(gate_result: dict[str, Any]) -> str:
    rows = [
        {
            "mode": "cgmlst-gate",
            "scheme": str(gate_result.get("scheme", "")),
            "backend": str(gate_result.get("backend", "")),
            "n_samples": str(gate_result.get("n_samples", "")),
            "mismatch_count": str(gate_result.get("mismatch_count", "")),
            "mismatches": ",".join(gate_result.get("mismatches", [])),
            "mismatch_details": json.dumps(gate_result.get("mismatch_details", [])),
        }
    ]
    columns = [
        "mode",
        "scheme",
        "backend",
        "n_samples",
        "mismatch_count",
        "mismatches",
        "mismatch_details",
    ]
    return render_delimited_rows(rows, columns, "\t")


@utils_group.command(
    "benchmark",
    context_settings=HELP_SETTINGS,
    no_args_is_help=True,
    help="Benchmark multiple alignment backends on sample inputs.",
)
@click.argument(
    "samples", nargs=-1, type=click.Path(exists=True, path_type=Path), required=True
)
@click.option("--scheme", "-s", required=True, help="MLST scheme name.")
@click.option(
    "--backends",
    "-b",
    default=",".join(AVAILABLE_BACKENDS),
    show_default=True,
    help="Comma-separated list of backends to benchmark.",
)
@click.option(
    "--repeat",
    "-r",
    type=click.IntRange(1, None),
    default=1,
    show_default=True,
    help="Repeat each backend run N times for stable timing.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    default="table",
    show_default=True,
    type=click.Choice(["table", "tsv", "json"], case_sensitive=False),
    help="Benchmark output format.",
)
@click.option(
    "--cgmlst-gate",
    is_flag=True,
    help="Run cgMLST prefilter on/off gate instead of backend benchmark.",
)
@click.option(
    "--gate-max-mismatches",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Maximum allowed mismatch count in --cgmlst-gate mode.",
)
@click.option(
    "--gate-details-output",
    type=click.Path(path_type=Path),
    help="Write cgMLST gate mismatch details to file.",
)
@click.option(
    "--gate-details-format",
    type=click.Choice(["jsonl", "tsv"], case_sensitive=False),
    default="jsonl",
    show_default=True,
    help="Format for --gate-details-output.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write benchmark output to file.",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), help="Override cache directory."
)
@click.option("--force-reindex", is_flag=True, help="Rebuild aligner indexes.")
def cmd_benchmark(
    samples: tuple[Path, ...],
    scheme: str,
    backends: str,
    repeat: int,
    output_format: str,
    cgmlst_gate: bool,
    gate_max_mismatches: int,
    gate_details_output: Path | None,
    gate_details_format: str,
    output: Path | None,
    cache_dir: Path | None,
    force_reindex: bool,
) -> None:
    backend_list = [b.strip().lower() for b in backends.split(",") if b.strip()]
    unknown_backends = sorted(set(backend_list) - set(AVAILABLE_BACKENDS))
    if unknown_backends:
        raise click.UsageError(
            f"Unknown backend(s): {', '.join(unknown_backends)}. "
            f"Available: {', '.join(AVAILABLE_BACKENDS)}"
        )

    if cgmlst_gate:
        if len(backend_list) != 1:
            raise click.UsageError("--cgmlst-gate requires exactly one backend")
        gate_result = run_cgmlst_gate(
            scheme_name=scheme,
            sample_paths=prepare_sample_inputs(list(samples)),
            backend=backend_list[0],
            cache_root=cache_dir,
            force_reindex=force_reindex,
        )
        text = render_from_format(
            output_format,
            {
                "json": lambda: json.dumps(gate_result, indent=2),
                "tsv": lambda: _render_cgmlst_gate_tsv(gate_result),
                "table": lambda: (
                    f"cgmlst-gate scheme={gate_result['scheme']} "
                    f"backend={gate_result['backend']} "
                    f"samples={gate_result['n_samples']} "
                    f"mismatches={gate_result['mismatch_count']}"
                    + (
                        f"\ndetails={json.dumps(gate_result['mismatch_details'])}"
                        if gate_result["mismatch_details"]
                        else ""
                    )
                ),
            },
        )
        emit_output_text(text, output)

        if gate_details_output is not None:
            details = gate_result.get("mismatch_details", [])
            if gate_details_format == "tsv":
                detail_rows = [
                    {
                        "sample_id": str(detail.get("sample_id", "")),
                        "st_on": str(detail.get("st_on", "")),
                        "st_off": str(detail.get("st_off", "")),
                        "differing_loci": json.dumps(
                            detail.get("differing_loci", []), ensure_ascii=False
                        ),
                    }
                    for detail in details
                ]
                emit_output_tsv(
                    detail_rows,
                    ["sample_id", "st_on", "st_off", "differing_loci"],
                    gate_details_output,
                )
            else:
                lines = [json.dumps(detail, ensure_ascii=False) for detail in details]
                if lines:
                    emit_output_text("\n".join(lines), gate_details_output)
                else:
                    gate_details_output.write_text("")

        if gate_result["mismatch_count"] > gate_max_mismatches:
            raise click.ClickException(
                "cgmlst gate failed: mismatch_count "
                f"{gate_result['mismatch_count']} exceeds allowed {gate_max_mismatches}"
            )
        return

    prepared_samples = prepare_sample_inputs(list(samples))
    result = run_benchmark(
        scheme_name=scheme,
        sample_paths=prepared_samples,
        backends=backend_list,
        repeat=repeat,
        cache_root=cache_dir,
        force_reindex=force_reindex,
    )
    if output_format == "table":
        emit_output_table(
            output=output,
            render_text=lambda: render_report(result),
            print_table=lambda: print_report(result),
        )
        return

    output_text = render_from_format(
        output_format,
        {
            "tsv": lambda: to_tsv(result),
            "json": lambda: to_json(result),
        },
    )
    emit_output_text(output_text, output)
