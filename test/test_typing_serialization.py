"""Behavior-lock tests for the tgmlst JSON serialization path.

``_normalize_profile_dicts`` replaces the former
``json.loads(profiles_to_json(...))`` round-trip; these tests pin the
emitted JSON bytes to the pre-refactor output and pin equivalence with
the schemefree io_handler engine.
"""

from __future__ import annotations

import json

from gmlst.commands.typing import _normalize_profile_dicts
from gmlst.schema_versions import TGMLST_PROFILES_V1
from gmlst.schemefree.io_handler import profiles_to_json

FIXED_PROFILES = [
    {
        "sample_id": "sampleA",
        "loci_count": 2,
        "profile": {"abcZ": 1, "adk": "adk_3", "aroE": None, "gap": "-"},
    },
    {
        "sample_id": "sampleB",
        "loci_count": 1,
        "profile": {"abcZ": "7", "adk": 12, "novel": "abcZ_~5"},
    },
]

GOLDEN_JSON = """{
  "schema_version": "gmlst-tgmlst-profiles-v1",
  "data": [
    {
      "sample_id": "sampleA",
      "loci_count": 2,
      "profile": {
        "abcZ": "1",
        "adk": "3",
        "aroE": "0",
        "gap": "0"
      }
    },
    {
      "sample_id": "sampleB",
      "loci_count": 1,
      "profile": {
        "abcZ": "7",
        "adk": "12",
        "novel": "abcZ_~5"
      }
    }
  ]
}"""


def test_tgmlst_json_payload_matches_golden() -> None:
    output_text = json.dumps(
        {
            "schema_version": TGMLST_PROFILES_V1,
            "data": _normalize_profile_dicts(FIXED_PROFILES),
        },
        indent=2,
    )
    assert output_text == GOLDEN_JSON


def test_normalize_profile_dicts_equivalent_to_io_handler() -> None:
    assert _normalize_profile_dicts(FIXED_PROFILES) == json.loads(
        profiles_to_json(FIXED_PROFILES)
    )


def test_normalize_profile_dicts_does_not_mutate_input() -> None:
    snapshot = json.dumps(FIXED_PROFILES, sort_keys=True)
    _normalize_profile_dicts(FIXED_PROFILES)
    assert json.dumps(FIXED_PROFILES, sort_keys=True) == snapshot
