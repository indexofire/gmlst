from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from gmlst.aligners import AVAILABLE_BACKENDS, get_aligner
from gmlst.commands.common import (
    emit_output_table,
    emit_output_text,
    emit_output_tsv,
    render_from_format,
)
from gmlst.commands.utils_benchmark import BackendMetrics as BackendMetrics
from gmlst.commands.utils_benchmark import BenchmarkResult as BenchmarkResult
from gmlst.commands.utils_benchmark import (
    _render_cgmlst_gate_tsv,
    print_report,
    render_report,
    run_benchmark,
    run_cgmlst_gate,
    to_json,
    to_tsv,
)
from gmlst.commands.utils_extract import (
    _extract_alleles_from_sample,
    _extract_novel_from_result,
)
from gmlst.core import run_typing as run_typing
from gmlst.database.cache import DatabaseCache as DatabaseCache
from gmlst.readers.fasta import FastaReader
from gmlst.readers.sample import prepare_sample_inputs

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}


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
    """Benchmark multiple alignment backends on sample inputs."""
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
