from __future__ import annotations

from pathlib import Path
from typing import TextIO


def open_stream_output(*, fmt: str, output: Path | None) -> TextIO | None:
    if fmt in {"tsv", "pretty"} and output is not None:
        return output.open("w")
    return None


def stream_write(line: str, *, stream_file: TextIO | None) -> None:
    if stream_file is not None:
        print(line, file=stream_file, flush=True)
        return
    print(line, flush=True)


def stream_header_if_needed(
    *,
    fmt: str,
    no_header: bool,
    loci: list[str],
    stream_file: TextIO | None,
) -> None:
    if fmt == "tsv" and not no_header:
        stream_write("FILE\tSCHEME\tST\t" + "\t".join(loci), stream_file=stream_file)


def emit_streamed_result(
    *,
    result,
    fmt: str,
    loci: list[str],
    count_same_copy: bool,
    call_policy: str,
    format_st_for_tsv_fn,
    format_tsv_row_fn,
    stream_file: TextIO | None,
) -> None:
    if fmt == "pretty":
        stream_write(
            f"{result.sample_id}: ST={format_st_for_tsv_fn(result)}",
            stream_file=stream_file,
        )
        return
    if fmt == "tsv":
        stream_write(
            format_tsv_row_fn(
                result,
                loci,
                count_same_copy,
                call_policy=call_policy,
            ),
            stream_file=stream_file,
        )


def emit_final_typing_output(
    *,
    results: list,
    fmt: str,
    output: Path | None,
    emit_output_json_fn,
    console,
) -> bool:
    if fmt != "json":
        return False
    output_data = [result.to_dict() for result in results]
    wrote_file = emit_output_json_fn(output_data, output)
    if wrote_file and output is not None:
        console.print(f"Results written to [cyan]{output}[/cyan]")
    return True


def announce_stream_output_written(*, output: Path | None, console) -> None:
    if output is not None:
        console.print(f"Results written to [cyan]{output}[/cyan]")


def close_stream_output(stream_file: TextIO | None) -> None:
    if stream_file is not None:
        stream_file.close()
