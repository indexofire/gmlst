from __future__ import annotations

from pathlib import Path

from gmlst.commands.common import (
    emit_output_csv,
    emit_output_json,
    emit_output_table,
    emit_output_text,
    emit_output_tsv,
    render_delimited_rows,
    render_from_format,
)


def test_render_from_format_selects_renderer() -> None:
    rendered = render_from_format("json", {"json": lambda: "ok", "tsv": lambda: "no"})
    assert rendered == "ok"


def test_render_from_format_rejects_unknown() -> None:
    try:
        render_from_format("pretty", {"json": lambda: "ok"})
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "Unsupported output format 'pretty'" in str(exc)


def test_emit_output_text_writes_with_newline(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    wrote_file = emit_output_text("hello", out)
    assert wrote_file is True
    assert out.read_text() == "hello\n"


def test_emit_output_json_writes_pretty_json(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    wrote_file = emit_output_json({"a": 1}, out)
    assert wrote_file is True
    assert out.read_text() == '{\n  "a": 1\n}\n'


def test_emit_output_text_prints_when_no_output(capsys) -> None:
    wrote_file = emit_output_text("hello", None)
    assert wrote_file is False
    captured = capsys.readouterr()
    assert captured.out == "hello\n"


def test_emit_output_json_prints_when_no_output(capsys) -> None:
    wrote_file = emit_output_json({"a": 1}, None)
    assert wrote_file is False
    captured = capsys.readouterr()
    assert captured.out == '{\n  "a": 1\n}\n'


def test_emit_output_table_prints_when_no_output() -> None:
    calls = {"printed": 0}

    def print_table() -> None:
        calls["printed"] += 1

    wrote_file = emit_output_table(
        output=None,
        render_text=lambda: "unused",
        print_table=print_table,
    )

    assert wrote_file is False
    assert calls["printed"] == 1


def test_emit_output_table_writes_rendered_text(tmp_path: Path) -> None:
    out = tmp_path / "table.txt"
    calls = {"printed": 0}

    def print_table() -> None:
        calls["printed"] += 1

    wrote_file = emit_output_table(
        output=out,
        render_text=lambda: "table-body\n",
        print_table=print_table,
    )

    assert wrote_file is True
    assert calls["printed"] == 0
    assert out.read_text() == "table-body\n"


def test_render_delimited_rows_encodes_bool_as_01() -> None:
    rendered = render_delimited_rows(
        rows=[{"downloaded": True, "scheme_name": "ecoli_1"}],
        columns=["downloaded", "scheme_name"],
        delimiter="\t",
    )
    assert rendered == "downloaded\tscheme_name\n1\tecoli_1"


def test_emit_output_tsv_writes_delimited_text(tmp_path: Path) -> None:
    out = tmp_path / "out.tsv"
    wrote_file = emit_output_tsv(
        [{"sample_id": "s1", "st": "10"}],
        ["sample_id", "st"],
        out,
    )
    assert wrote_file is True
    assert out.read_text() == "sample_id\tst\ns1\t10\n"


def test_emit_output_csv_prints_when_no_output(capsys) -> None:
    wrote_file = emit_output_csv(
        [{"sample_id": "s1", "st": "10"}],
        ["sample_id", "st"],
        None,
    )
    assert wrote_file is False
    captured = capsys.readouterr()
    assert captured.out == "sample_id,st\ns1,10\n"
