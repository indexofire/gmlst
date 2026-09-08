"""FASTQ sample preparation utilities for typing commands."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console

from gmlst.readers.sample import SampleInput, prepare_sample_inputs

_DEFAULT_GENOME_SIZE = 5_000_000
_FASTQ_BYTES_PER_READ = 250


def prepare_sample_paths_for_pairing(
    samples: tuple[Path, ...],
) -> list[Path | SampleInput]:
    """Normalize raw CLI paths into plain paths or paired ``SampleInput`` entries.

    Common mate naming patterns (``_R1/_R2``, ``_1/_2``, ``.1/.2``) are merged
    into a single paired sample so each pair is typed once.
    """
    return prepare_sample_inputs(list(samples))


def contains_fastq_samples(samples: list[Path | SampleInput]) -> bool:
    """Return True if any sample is FASTQ input (by type or file extension)."""
    for sample in samples:
        if isinstance(sample, SampleInput):
            if sample.input_type == "fastq":
                return True
            continue

        name = sample.name.lower()
        if name.endswith(".fastq") or name.endswith(".fq"):
            return True
        if name.endswith(".fastq.gz") or name.endswith(".fq.gz"):
            return True
    return False


def fastq_kma_auto_threads() -> int:
    """Resolve the KMA thread count for FASTQ typing.

    Reads ``GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS`` (default 8; invalid values
    fall back to 8). Values <= 1 disable threading (return 1); larger values
    are clamped to the CPU count with a floor of 2.
    """
    raw = os.getenv("GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS", "8").strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = 8
    if configured <= 1:
        return 1
    cpu_total = os.cpu_count() or configured
    return max(2, min(configured, cpu_total))


@contextmanager
def temp_root_from_output(output: Path | None) -> Generator[None, None, None]:
    """Point ``GMLST_TMPDIR`` at the output file's parent for the duration.

    Keeps intermediate artifacts next to the final output. No-op when
    *output* is None; the previous environment value is restored (or
    removed) on exit.
    """
    if output is None:
        yield
        return

    output_parent = output.resolve().parent
    previous = os.environ.get("GMLST_TMPDIR")
    os.environ["GMLST_TMPDIR"] = str(output_parent)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("GMLST_TMPDIR", None)
        else:
            os.environ["GMLST_TMPDIR"] = previous


def maybe_subsample_fastq(
    samples: list[Path | SampleInput],
    max_depth: float,
    console: Console,
) -> list[Path | SampleInput]:
    """Subsample FASTQ samples whose estimated depth exceeds *max_depth*.

    Depth is estimated from file size: ``reads ~ bytes / 250`` and
    ``depth ~ reads * 150 / 5 Mb`` (assumed 150 bp reads, 5 Mb genome).
    Over-depth samples are truncated (first ``max_depth * 5 Mb / 150`` reads
    per pair) into gzipped copies in a temp dir; other samples pass through
    unchanged.
    """
    result: list[Path | SampleInput] = []
    for sample in samples:
        is_fastq = False
        paths: list[Path] = []
        if isinstance(sample, SampleInput):
            if sample.input_type == "fastq":
                is_fastq = True
                paths = [sample.path]
                if sample.mate_path:
                    paths.append(sample.mate_path)
        elif Path(str(sample)).suffix in (".fastq", ".fq", ".fastq.gz", ".fq.gz"):
            is_fastq = True
            paths = [Path(str(sample))]

        if not is_fastq:
            result.append(sample)
            continue

        total_reads = sum(
            max(p.stat().st_size // _FASTQ_BYTES_PER_READ, 1) for p in paths
        )
        est_depth = total_reads * 150 / _DEFAULT_GENOME_SIZE
        if est_depth <= max_depth:
            result.append(sample)
            continue

        target_reads = int(max_depth * _DEFAULT_GENOME_SIZE / 150)
        console.print(
            f"[yellow]Subsample:[/yellow] "
            f"{sample if isinstance(sample, Path) else sample.sample_id} "
            f"~{est_depth:.0f}x depth → {max_depth:.0f}x "
            f"(target {target_reads} reads)"
        )

        from gmlst.utils import temp_dir

        with temp_dir("gmlst_sub_") as tmp:
            new_paths: list[Path] = []
            for i, p in enumerate(paths):
                out = tmp / f"sub_{i}.fastq.gz"
                _subsample_fastq_file(p, out, target_reads)
                new_paths.append(out)

            if isinstance(sample, SampleInput):
                result.append(
                    SampleInput(
                        path=new_paths[0],
                        mate_path=new_paths[1] if len(new_paths) > 1 else None,
                        sample_id=sample.sample_id,
                        input_type=sample.input_type,
                    )
                )
            else:
                result.append(new_paths[0])

    return result


def _subsample_fastq_file(
    input_path: Path, output_path: Path, target_reads: int
) -> None:
    import gzip as _gzip

    opener = _gzip.open if input_path.suffix == ".gz" else open
    lines_needed = target_reads * 4
    with opener(input_path, "rb") as fin, _gzip.open(output_path, "wb") as fout:
        for _ in range(lines_needed):
            line = fin.readline()
            if not line:
                break
            fout.write(line)
