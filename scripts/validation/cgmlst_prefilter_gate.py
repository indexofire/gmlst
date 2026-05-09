from __future__ import annotations

import argparse
import glob
import json
import subprocess
import tempfile
from pathlib import Path


def _run_typing(
    *,
    scheme: str,
    backend: str,
    samples: list[Path],
    prefilter_enabled: bool,
) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="gmlst_gate_") as tmp:
        out = Path(tmp) / (
            "prefilter_on.json" if prefilter_enabled else "prefilter_off.json"
        )
        cmd = [
            "pixi",
            "run",
            "python",
            "-m",
            "gmlst",
            "typing",
            "cgmlst",
            "-s",
            scheme,
            "-b",
            backend,
            "--format",
            "json",
            "-o",
            str(out),
        ]
        if not prefilter_enabled:
            cmd.append("--no-prefilter")
        cmd.extend(str(sample) for sample in samples)
        completed = subprocess.run(cmd, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(
                "typing command failed: "
                f"returncode={completed.returncode}\n"
                f"stdout={completed.stdout}\n"
                f"stderr={completed.stderr}"
            )
        return json.loads(out.read_text())


def _extract_signature(result: dict) -> tuple[str | None, tuple[tuple[str, str], ...]]:
    st = result.get("st")
    locus_calls: dict = result.get("locus_calls", {})
    calls = []
    for locus, call in sorted(locus_calls.items()):
        calls.append((locus, str(call.get("allele_id", ""))))
    return st, tuple(calls)


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", default="vparahaemolyticus_3")
    parser.add_argument("--backend", default="minimap2")
    parser.add_argument(
        "--samples-glob",
        default="/home/mark/data/250124_miseq/assembly/*.fna",
    )
    args = parser.parse_args()

    samples = sorted(Path(path) for path in glob.glob(args.samples_glob))
    if not samples:
        raise SystemExit(f"No samples matched: {args.samples_glob}")

    on_results = _run_typing(
        scheme=args.scheme,
        backend=args.backend,
        samples=samples,
        prefilter_enabled=True,
    )
    off_results = _run_typing(
        scheme=args.scheme,
        backend=args.backend,
        samples=samples,
        prefilter_enabled=False,
    )

    by_sample_on = {result["sample_id"]: result for result in on_results}
    by_sample_off = {result["sample_id"]: result for result in off_results}
    all_samples = sorted(set(by_sample_on) | set(by_sample_off))

    mismatches: list[str] = []
    for sample_id in all_samples:
        result_on = by_sample_on.get(sample_id)
        result_off = by_sample_off.get(sample_id)
        if result_on is None or result_off is None:
            mismatches.append(f"{sample_id}: missing result in one mode")
            continue
        if _extract_signature(result_on) != _extract_signature(result_off):
            mismatches.append(sample_id)

    print(f"samples={len(all_samples)} backend={args.backend} scheme={args.scheme}")
    print(f"mismatches={len(mismatches)}")
    if mismatches:
        for item in mismatches:
            print(f"mismatch: {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
