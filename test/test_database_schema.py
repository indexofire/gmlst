from __future__ import annotations

from pathlib import Path

from gmlst.database.schema import Scheme


def test_load_profiles_skips_rows_with_missing_locus_values(tmp_path: Path) -> None:
    allele_file = tmp_path / "dnaN.tfa"
    allele_file.write_text(">dnaN_1\nATGC\n")
    profile_file = tmp_path / "scheme.txt"
    profile_file.write_text("ST\tdnaN\tgyrB\n1\t1\n2\t1\t5\n")

    scheme = Scheme(
        name="demo",
        loci=["dnaN", "gyrB"],
        allele_files={"dnaN": allele_file},
        profile_file=profile_file,
    )

    assert scheme.lookup_st({"dnaN": "1", "gyrB": "5"}) == 2
    assert scheme._profiles == {("1", "5"): 2}
