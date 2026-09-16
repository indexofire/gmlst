from __future__ import annotations

import json
from pathlib import Path

import pytest

from gmlst.schemefree.io_handler import (
    profiles_to_json,
    profiles_to_tsv,
    read_scheme_json,
    write_error_report_json,
    write_scheme_json,
    write_summary_report_json,
)


def test_profiles_to_tsv_with_header() -> None:
    profiles = [
        {"sample_id": "s1", "profile": {"locus_1": "locus_1_1"}},
        {
            "sample_id": "s2",
            "profile": {"locus_1": "locus_1_1", "locus_2": "locus_2_1"},
        },
    ]

    text = profiles_to_tsv(profiles, include_header=True)
    lines = text.splitlines()
    assert lines[0] == "sample\tlocus_1\tlocus_2"
    assert lines[1] == "s1\t1\t0"
    assert lines[2] == "s2\t1\t1"


def test_profiles_to_json() -> None:
    profiles = [{"sample_id": "s1", "profile": {"locus_1": "locus_1_1"}}]
    text = profiles_to_json(profiles)
    assert '"sample_id": "s1"' in text
    assert '"locus_1": "1"' in text


def test_scheme_json_roundtrip(tmp_path: Path) -> None:
    output = tmp_path / "scheme.json"
    write_scheme_json(
        output,
        config={"hash_strategy": "safe"},
        loci={"locus_1": {"locus_1_1": "deadbeef"}},
        profiles={"s1": {"sample_id": "s1", "profile": {"locus_1": "locus_1_1"}}},
        representatives={"locus_1": "ATCG"},
    )

    loaded = read_scheme_json(output)
    assert loaded["config"]["hash_strategy"] == "safe"
    assert loaded["loci"]["locus_1"] == {"locus_1_1": "deadbeef"}
    assert loaded["profiles"]["s1"]["sample_id"] == "s1"
    assert loaded["representatives"]["locus_1"] == "ATCG"


def test_read_scheme_json_accepts_legacy_list_loci(tmp_path: Path) -> None:
    output = tmp_path / "legacy_scheme.json"
    output.write_text(
        json.dumps(
            {
                "config": {"hash_strategy": "safe"},
                "loci": {"locus_1": ["locus_1_1", "locus_1_2"]},
                "profiles": {},
            }
        )
    )

    loaded = read_scheme_json(output)

    assert loaded["loci"]["locus_1"] == {"locus_1_1": "", "locus_1_2": ""}
    assert loaded["representatives"] == {}


def test_read_scheme_json_rejects_non_object(tmp_path: Path) -> None:
    output = tmp_path / "bad.json"
    output.write_text("[1, 2, 3]")

    with pytest.raises(ValueError, match="expected an object"):
        read_scheme_json(output)


def test_read_scheme_json_rejects_bad_loci_shape(tmp_path: Path) -> None:
    output = tmp_path / "bad.json"
    output.write_text(json.dumps({"loci": {"locus_1": 7}}))

    with pytest.raises(ValueError, match="locus 'locus_1'"):
        read_scheme_json(output)


def test_write_error_report_json(tmp_path: Path) -> None:
    out = tmp_path / "errors.json"
    errors = [{"sample_id": "s2", "stage": "prediction", "error": "boom"}]
    write_error_report_json(out, errors)
    loaded = json.loads(out.read_text())
    assert loaded[0]["sample_id"] == "s2"
    assert loaded[0]["stage"] == "prediction"


def test_write_summary_report_json(tmp_path: Path) -> None:
    out = tmp_path / "summary.json"
    summary = {
        "samples_total": 2,
        "samples_succeeded": 1,
        "samples_failed": 1,
        "exit_code": 0,
        "exit_reason": "partial_failed_allowed",
        "failed_by_stage": {"input": 1},
    }
    write_summary_report_json(out, summary)
    loaded = json.loads(out.read_text())
    assert loaded["exit_reason"] == "partial_failed_allowed"
    assert loaded["failed_by_stage"]["input"] == 1
