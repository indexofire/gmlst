from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gmlst.cli import main
from gmlst.database.schema import Scheme


def test_extract_json_then_create_custom_scheme(monkeypatch, tmp_path: Path) -> None:
    typing_json = tmp_path / "typing_results.json"
    typing_json.write_text(
        json.dumps(
            [
                {
                    "sample_id": "sample_A",
                    "scheme": "ecoli_1",
                    "st": None,
                    "allele_calls": {
                        "dnaN": {
                            "allele_id": "101",
                            "call_type": "novel",
                            "novel_sequence": "ATGCATGC",
                        },
                        "gyrB": {
                            "allele_id": "5",
                            "call_type": "exact",
                            "novel_sequence": None,
                        },
                    },
                }
            ]
        )
    )

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    dna_path = source_dir / "dnaN.tfa"
    dna_path.write_text(">dnaN_1\nATGC\n")
    gyr_path = source_dir / "gyrB.tfa"
    gyr_path.write_text(">gyrB_5\nGCGC\n")
    profile_path = source_dir / "ecoli_1.txt"
    profile_path.write_text("ST\tdnaN\tgyrB\n1\t1\t5\n")
    source_scheme = Scheme(
        name="ecoli_1",
        loci=["dnaN", "gyrB"],
        allele_files={"dnaN": dna_path, "gyrB": gyr_path},
        profile_file=profile_path,
    )

    def _fake_load_catalog(self, provider: str):
        if provider == "pubmlst":
            return [{"scheme_name": "ecoli_1", "scheme_type": "mlst"}]
        return []

    def _fake_ensure_scheme(self, name: str, **_kwargs):
        assert name == "ecoli_1"
        return source_scheme

    monkeypatch.setattr(
        "gmlst.commands.scheme.DatabaseCache.load_catalog", _fake_load_catalog
    )
    monkeypatch.setattr(
        "gmlst.commands.scheme.DatabaseCache.ensure_scheme",
        _fake_ensure_scheme,
    )

    cache_dir = tmp_path / "cache"
    novel_dir = tmp_path / "novel"
    runner = CliRunner()

    extract_result = runner.invoke(
        main,
        [
            "utils",
            "extract",
            "-i",
            str(typing_json),
            "--novel-allele",
            "--novel-profile",
            "--data-dir",
            str(novel_dir),
        ],
    )
    assert extract_result.exit_code == 0
    assert (novel_dir / "dnaN_novel.fasta").exists()
    assert (novel_dir / "profiles_novel.txt").exists()

    create_result = runner.invoke(
        main,
        [
            "scheme",
            "create",
            "-t",
            "mlst",
            "-s",
            "ecoli_1",
            "--data-dir",
            str(novel_dir),
            "--cache-dir",
            str(cache_dir),
            "--desc",
            "phase3 test",
        ],
    )
    assert create_result.exit_code == 0

    custom_dir = cache_dir / "local" / "custom_1"
    assert custom_dir.exists()
    assert (custom_dir / "dnaN.tfa").exists()
    assert (custom_dir / "custom_1.txt").exists()
    meta = json.loads((custom_dir / ".meta.json").read_text())
    assert meta["scheme"] == "custom_1"
    assert meta["based_on"] == "ecoli_1"
    assert meta["last_allele_number"] == {"dnaN": 1}
