from __future__ import annotations

from pathlib import Path

from gmlst.novel.writer import NovelProfileWriter


def test_profile_writer_appends_and_continues_numbering(tmp_path: Path) -> None:
    profile_file = tmp_path / "profiles_novel.txt"
    profile_file.write_text("ST\tsample\tdnaN\tgyrB\nN1\tisolate_a\tn1\t5\n")

    writer = NovelProfileWriter(tmp_path, ["dnaN", "gyrB"])

    duplicate_st = writer.add_profile(
        sample="isolate_b",
        allele_calls={"dnaN": "n1", "gyrB": "5"},
    )
    new_st = writer.add_profile(
        sample="isolate_c",
        allele_calls={"dnaN": "n2", "gyrB": "5"},
    )

    written = writer.write()

    assert written == profile_file
    assert duplicate_st == "N1"
    assert new_st == "N2"

    lines = profile_file.read_text().strip().splitlines()
    assert lines[0] == "ST\tsample\tdnaN\tgyrB"
    assert lines[1] == "N1\tisolate_a\tn1\t5"
    assert lines[2] == "N1\tisolate_b\tn1\t5"
    assert lines[3] == "N2\tisolate_c\tn2\t5"
