from __future__ import annotations

import json
import logging
import resource
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gmlst.commands.common import render_delimited_rows
from gmlst.database.cache import DatabaseCache
from gmlst.readers.sample import SampleInput

logger = logging.getLogger("gmlst.benchmark")


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
                from gmlst.commands.utils import run_typing

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
    from gmlst.commands.utils import run_typing

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
