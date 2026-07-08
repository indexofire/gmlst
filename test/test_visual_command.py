from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from click.testing import CliRunner

from gmlst.cli import main
from gmlst.visual.app import create_visual_app
from gmlst.visual.mst import build_mst_from_tsv
from gmlst.visual.mst_shared import (
    _MAX_LOCI_COUNT,
    _MAX_SAMPLE_COUNT,
    validate_tsv_scale,
)


def test_root_help_shows_visual_group() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "visual" in result.output


def test_visual_group_shows_web_subcommand() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["visual", "--help"])
    assert result.exit_code == 0
    assert "Launch interactive visualization tools" in result.output
    assert "web" in result.output
    assert "mst" in result.output
    assert "matrix" in result.output
    assert "heatmap" in result.output
    assert "compare" in result.output
    assert "locus-diff" in result.output
    assert "export" in result.output


def test_visual_web_help_options() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["visual", "web", "--help"])
    assert result.exit_code == 0
    assert (
        "Run the local web UI for Grapetree-style MST visualization." in result.output
    )
    assert "--host" in result.output
    assert "--port" in result.output
    assert "--open-browser" in result.output


def test_visual_mst_subcommand_outputs_json_payload() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = "profiles.tsv"
        Path(input_path).write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )

        result = runner.invoke(main, ["visual", "mst", "--input", input_path])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["nodes"]) == 2
    assert len(payload["edges"]) == 1
    assert payload["metadata_fields"] == ["SCHEME", "ST"]
    assert payload["aggregate_profiles"] is True


def test_visual_compare_subcommand_writes_output_file() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        left_path = Path("left.tsv")
        right_path = Path("right.tsv")
        out_path = Path("comparison.json")

        left_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )
        right_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t21\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "compare",
                "--left",
                str(left_path),
                "--right",
                str(right_path),
                "--output",
                str(out_path),
            ],
        )

        payload = json.loads(out_path.read_text())

    assert result.exit_code == 0
    assert "Results written to" in result.output
    assert payload["summary"]["matched_samples"] == 2
    assert payload["summary"]["different_st"] == 1


def test_visual_matrix_subcommand_supports_tsv_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "matrix",
                "--input",
                str(input_path),
                "--format",
                "tsv",
            ],
        )

    assert result.exit_code == 0
    assert result.output.splitlines()[0] == "sample_id\ts1\ts2"
    assert result.output.splitlines()[1] == "s1\t0\t1"
    assert result.output.splitlines()[2] == "s2\t1\t0"


def test_visual_mst_subcommand_supports_tsv_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "mst",
                "--input",
                str(input_path),
                "--format",
                "tsv",
            ],
        )

    assert result.exit_code == 0
    assert (
        result.output.splitlines()[0]
        == "source_label\ttarget_label\tweight\tasymmetric_weight"
    )
    assert result.output.splitlines()[1] == "s1\ts2\t1\t1"


def test_visual_compare_subcommand_supports_table_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        left_path = Path("left.tsv")
        right_path = Path("right.tsv")

        left_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )
        right_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t21\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "compare",
                "--left",
                str(left_path),
                "--right",
                str(right_path),
                "--format",
                "table",
            ],
        )

    assert result.exit_code == 0
    assert "matched_samples: 2" in result.output
    assert "different_st: 1" in result.output
    assert "sample_id" in result.output
    assert "s2" in result.output
    assert "different_st" in result.output


def test_visual_heatmap_subcommand_supports_tsv_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "heatmap",
                "--input",
                str(input_path),
                "--format",
                "tsv",
                "--no-aggregate-profiles",
            ],
        )

    assert result.exit_code == 0
    assert result.output.splitlines()[0] == "sample_id\tL1\tL2"
    assert result.output.splitlines()[1] == "s1\t1\t1"
    assert result.output.splitlines()[2] == "s2\t1\t2"


def test_visual_locus_diff_subcommand_supports_tsv_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2\tL3",
                    "s1\tvpa\t11\t1\t1\t1",
                    "s2\tvpa\t12\t1\t2\t3",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "locus-diff",
                "--input",
                str(input_path),
                "--left-label",
                "s1",
                "--right-label",
                "s2",
                "--format",
                "tsv",
            ],
        )

    assert result.exit_code == 0
    assert result.output.splitlines()[0] == "locus\tleft\tright\ttype"
    assert result.output.splitlines()[1] == "L2\t1\t2\tallele_difference"
    assert result.output.splitlines()[2] == "L3\t1\t3\tallele_difference"


def test_visual_export_subcommand_writes_matrix_json() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        output_path = Path("matrix-export.json")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "export",
                "--kind",
                "matrix",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
        )
        payload = json.loads(output_path.read_text())

    assert result.exit_code == 0
    assert "Results written to" in result.output
    assert payload["schema_version"] == "gmlst-visual-export-v1"
    assert payload["kind"] == "matrix"
    assert payload["payload"]["labels"] == ["s1", "s2"]
    assert payload["payload"]["matrix"] == [[0, 1], [1, 0]]


def test_visual_export_subcommand_supports_matrix_tsv_stdout() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "export",
                "--kind",
                "matrix",
                "--input",
                str(input_path),
                "--format",
                "tsv",
            ],
        )

    assert result.exit_code == 0
    assert result.output.splitlines()[0] == "sample_id\ts1\ts2"
    assert result.output.splitlines()[1] == "s1\t0\t1"
    assert result.output.splitlines()[2] == "s2\t1\t0"


def test_visual_export_subcommand_supports_compare_table_stdout() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        left_path = Path("left.tsv")
        right_path = Path("right.tsv")
        left_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )
        right_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t21\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "export",
                "--kind",
                "compare",
                "--left",
                str(left_path),
                "--right",
                str(right_path),
                "--format",
                "table",
            ],
        )

    assert result.exit_code == 0
    assert "matched_samples: 2" in result.output
    assert "different_st: 1" in result.output
    assert "sample_id" in result.output


def test_visual_export_subcommand_supports_custom_schema_version() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        output_path = Path("matrix-export.json")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "export",
                "--kind",
                "matrix",
                "--input",
                str(input_path),
                "--schema-version",
                "custom-v2",
                "--output",
                str(output_path),
            ],
        )
        payload = json.loads(output_path.read_text())

    assert result.exit_code == 0
    assert payload["schema_version"] == "custom-v2"
    assert payload["kind"] == "matrix"


def test_visual_export_subcommand_supports_include_meta_for_matrix_tsv() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "export",
                "--kind",
                "matrix",
                "--input",
                str(input_path),
                "--format",
                "tsv",
                "--include-meta",
            ],
        )

    assert result.exit_code == 0
    assert result.output.splitlines()[0] == "sample_id\ts1\ts2\tSCHEME\tST"
    assert result.output.splitlines()[1] == "s1\t0\t1\tvpa\t11"


def test_visual_export_subcommand_supports_columns_projection() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1\tL2",
                    "s1\tvpa\t11\t1\t1",
                    "s2\tvpa\t12\t1\t2",
                ]
            )
        )

        result = runner.invoke(
            main,
            [
                "visual",
                "export",
                "--kind",
                "matrix",
                "--input",
                str(input_path),
                "--format",
                "tsv",
                "--columns",
                "sample_id,s2",
            ],
        )

    assert result.exit_code == 0
    assert result.output.splitlines()[0] == "sample_id\ts2"
    assert result.output.splitlines()[1] == "s1\t1"
    assert result.output.splitlines()[2] == "s2\t0"


def test_build_mst_from_tsv_creates_tree_edges() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t-\t1\t1",
            "s2\tvpa\t-\t1\t2",
            "s3\tvpa\t-\t2\t2",
        ]
    )
    nodes, edges, metadata_fields = build_mst_from_tsv(tsv, include_missing=False)
    assert len(nodes) == 3
    assert len(edges) == 2
    assert all(edge["weight"] >= 0 for edge in edges)
    assert metadata_fields == ["SCHEME", "ST"]


def test_build_mst_from_tsv_single_sample_returns_no_edges() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t-\t1\t2",
        ]
    )
    nodes, edges, metadata_fields = build_mst_from_tsv(tsv, include_missing=False)
    assert nodes == [
        {
            "id": 0,
            "label": "s1",
            "meta": {"SCHEME": "vpa", "ST": "-"},
            "meta_breakdown": {"SCHEME": {"vpa": 1}, "ST": {"-": 1}},
            "profile_key": "1|2",
            "member_count": 1,
            "members": ["s1"],
        }
    ]
    assert edges == []
    assert metadata_fields == ["SCHEME", "ST"]


def test_build_mst_from_tsv_missing_penalty_toggle_changes_weights() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t-\t1\t1",
            "s2\tvpa\t-\tLNF\t1",
            "s3\tvpa\t-\t2\t1",
        ]
    )

    _, edges_without_penalty, _ = build_mst_from_tsv(tsv, include_missing=False)
    _, edges_with_penalty, _ = build_mst_from_tsv(tsv, include_missing=True)

    assert max(edge["weight"] for edge in edges_without_penalty) == 0
    assert max(edge["weight"] for edge in edges_with_penalty) == 1


def test_build_mst_grapetree_header_uses_first_column_as_sample() -> None:
    tsv = "\n".join(
        [
            "#Strain\tL1\tL2",
            "A\t1\t1",
            "B\t1\t1",
        ]
    )
    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)
    assert len(edges) == 1
    assert edges[0]["weight"] == 0


def test_build_mst_accepts_csv_profile_input() -> None:
    csv_text = "\n".join(
        [
            "FILE,SCHEME,ST,L1,L2",
            "s1,vpa,-,1,1",
            "s2,vpa,-,1,2",
            "s3,vpa,-,2,2",
        ]
    )

    nodes, edges, metadata_fields = build_mst_from_tsv(csv_text, include_missing=False)

    assert len(nodes) == 3
    assert len(edges) == 2
    assert metadata_fields == ["SCHEME", "ST"]


def test_build_mst_restores_duplicate_profiles_as_zero_length_leaves() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "A\tvpa\t-\t1\t1",
            "B\tvpa\t-\t1\t1",
            "C\tvpa\t-\t1\t2",
        ]
    )

    nodes, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert [node["label"] for node in nodes] == ["A", "B", "C"]
    assert len(edges) == 2
    assert {
        (edge["source_label"], edge["target_label"], edge["weight"]) for edge in edges
    } == {
        ("A", "B", 0),
        ("A", "C", 1),
    }


def test_build_mst_aggregate_profiles_collapses_duplicates_before_tree() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "A\tvpa\t-\t1\t1",
            "B\tvpa\t-\t1\t1",
            "C\tvpa\t-\t1\t2",
        ]
    )

    nodes, edges, _ = build_mst_from_tsv(
        tsv,
        include_missing=False,
        aggregate_profiles=True,
    )

    assert len(nodes) == 2
    assert nodes[0]["member_count"] == 2
    assert nodes[0]["members"] == ["A", "B"]
    assert len(edges) == 1
    assert edges[0]["weight"] == 1


def test_build_mst_edges_include_mismatch_loci_details() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "s1\tvpa\t-\t1\t1\t1",
            "s2\tvpa\t-\t1\t2\t3",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert edges == [
        {
            "source": 0,
            "target": 1,
            "weight": 2,
            "asymmetric_weight": 2,
            "source_label": "s1",
            "target_label": "s2",
            "mismatch_count": 2,
            "mismatch_loci": ["L2", "L3"],
            "asymmetric_mismatch_loci": ["L2", "L3"],
        }
    ]


def test_asymmetric_branching_can_choose_more_central_parent_under_missing_data() -> (
    None
):
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "root\tvpa\t-\t1\t1\t1",
            "a\tvpa\t-\tLNF\t1\t2",
            "b\tvpa\t-\t1\t1\t2",
            "c\tvpa\t-\t1\t2\t2",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert {
        (
            edge["source_label"],
            edge["target_label"],
            edge["weight"],
            edge["asymmetric_weight"],
        )
        for edge in edges
    } == {
        ("b", "root", 1, 1),
        ("b", "a", 0, 0),
        ("b", "c", 1, 1),
    }


def test_asymmetric_edge_fields_capture_branching_direction() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "a\tvpa\t-\tLNF\t1",
            "b\tvpa\t-\t1\t1",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert edges == [
        {
            "source": 1,
            "target": 0,
            "weight": 0,
            "asymmetric_weight": 0,
            "source_label": "b",
            "target_label": "a",
            "mismatch_count": 0,
            "mismatch_loci": [],
            "asymmetric_mismatch_loci": [],
        }
    ]


def test_recrafting_prefers_more_resolved_equal_cost_parent() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "a\tvpa\t-\tLNF\t1\t1",
            "b\tvpa\t-\t1\t1\t1",
            "c\tvpa\t-\tLNF\t1\t2",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert {
        (
            edge["source_label"],
            edge["target_label"],
            edge["weight"],
            edge["asymmetric_weight"],
        )
        for edge in edges
    } == {
        ("b", "a", 0, 0),
        ("b", "c", 1, 1),
    }


def test_recrafting_can_prefer_more_resolved_nearby_parent_with_small_cost_delta() -> (
    None
):
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "a\tvpa\t-\tLNF\t1\t1",
            "b\tvpa\t-\t1\t1\t1",
            "c\tvpa\t-\t2\t1\t2",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert {
        (
            edge["source_label"],
            edge["target_label"],
            edge["weight"],
            edge["asymmetric_weight"],
        )
        for edge in edges
    } == {
        ("b", "a", 0, 0),
        ("a", "c", 1, 2),
    }


def test_subtree_aware_recrafting_prefers_parent_better_for_descendants() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3\tL4",
            "a\tvpa\t-\tLNF\t1\t1\t1",
            "b\tvpa\t-\t1\t1\t1\t1",
            "c\tvpa\t-\tLNF\t1\t2\t2",
            "d\tvpa\t-\tLNF\t1\t2\t3",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert {
        (
            edge["source_label"],
            edge["target_label"],
            edge["weight"],
            edge["asymmetric_weight"],
        )
        for edge in edges
    } == {
        ("b", "a", 0, 0),
        ("b", "c", 2, 2),
        ("c", "d", 1, 1),
    }


def test_multistep_recrafting_revisits_affected_subtree() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3\tL4",
            "a\tvpa\t-\tLNF\t1\t1\t1",
            "b\tvpa\t-\t1\t1\t1\t1",
            "c\tvpa\t-\tLNF\t1\t2\t2",
            "d\tvpa\t-\tLNF\t1\t2\t4",
            "e\tvpa\t-\tLNF\t1\t2\t5",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert {
        (
            edge["source_label"],
            edge["target_label"],
            edge["weight"],
            edge["asymmetric_weight"],
        )
        for edge in edges
    } == {
        ("b", "a", 0, 0),
        ("b", "c", 2, 2),
        ("c", "d", 1, 1),
        ("c", "e", 1, 1),
    }


def test_recrafting_keeps_parent_under_subtree_cost_gate() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3\tL4",
            "a\tvpa\t-\tLNF\t1\t1\t1",
            "b\tvpa\t-\t1\t1\t1\t1",
            "c\tvpa\t-\tLNF\t1\t2\t2",
            "d\tvpa\t-\tLNF\t1\t2\t2",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert {
        (
            edge["source_label"],
            edge["target_label"],
            edge["weight"],
            edge["asymmetric_weight"],
        )
        for edge in edges
    } == {
        ("b", "a", 0, 0),
        ("b", "c", 2, 2),
        ("c", "d", 0, 0),
    }


def test_build_mst_returns_expected_unique_topology() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "s1\tvpa\t-\t1\t1\t1",
            "s2\tvpa\t-\t1\t1\t2",
            "s3\tvpa\t-\t1\t2\t2",
            "s4\tvpa\t-\t2\t2\t2",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert {
        (edge["source_label"], edge["target_label"], edge["weight"]) for edge in edges
    } == {
        ("s1", "s2", 1),
        ("s2", "s3", 1),
        ("s3", "s4", 1),
    }


def test_build_mst_total_weight_matches_expected_minimum() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "a\tvpa\t-\t1\t1\t1",
            "b\tvpa\t-\t1\t1\t2",
            "c\tvpa\t-\t1\t2\t2",
            "d\tvpa\t-\t1\t2\t3",
        ]
    )

    _, edges, _ = build_mst_from_tsv(tsv, include_missing=False)

    assert len(edges) == 3
    assert sum(edge["weight"] for edge in edges) == 3


def test_build_mst_metadata_join_merges_external_metadata() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t-\t1\t1",
            "s2\tvpa\t-\t1\t2",
        ]
    )
    metadata_tsv = "\n".join(
        [
            "ID\tCountry\tYear",
            "s1\tCN\t2024",
            "s2\tJP\t2025",
        ]
    )

    nodes, _, metadata_fields = build_mst_from_tsv(
        tsv,
        include_missing=False,
        metadata_text=metadata_tsv,
    )

    assert metadata_fields == ["SCHEME", "ST", "Country", "Year"]
    assert nodes[0]["meta"]["Country"] == "CN"
    assert nodes[1]["meta"]["Year"] == "2025"


def test_build_mst_aggregate_profiles_merges_member_metadata_values() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "A\tvpa\t-\t1\t1",
            "B\tvpa\t-\t1\t1",
            "C\tvpa\t-\t1\t2",
        ]
    )
    metadata_tsv = "\n".join(
        [
            "ID,Country,Source",
            "A,CN,food",
            "B,JP,clinical",
            "C,US,water",
        ]
    )

    nodes, _, _ = build_mst_from_tsv(
        tsv,
        include_missing=False,
        aggregate_profiles=True,
        metadata_text=metadata_tsv,
    )

    first_meta = cast(dict[str, str], nodes[0]["meta"])
    first_meta_breakdown = cast(dict[str, dict[str, int]], nodes[0]["meta_breakdown"])
    second_meta_breakdown = cast(dict[str, dict[str, int]], nodes[1]["meta_breakdown"])

    assert nodes[0]["member_count"] == 2
    assert first_meta["Country"] == "CN | JP"
    assert first_meta["Source"] == "food | clinical"
    assert first_meta_breakdown == {
        "Country": {"CN": 1, "JP": 1},
        "SCHEME": {"vpa": 2},
        "ST": {"-": 2},
        "Source": {"food": 1, "clinical": 1},
    }
    assert second_meta_breakdown == {
        "Country": {"US": 1},
        "SCHEME": {"vpa": 1},
        "ST": {"-": 1},
        "Source": {"water": 1},
    }


def test_create_visual_app_serves_index_and_health() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    index = client.get("/")
    assert index.status_code == 200
    assert "visual test" in index.get_data(as_text=True)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json() == {"status": "ok"}


def test_create_visual_app_api_mst_works_and_validates_input() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    bad = client.post("/api/mst", json={"tsv": ""})
    assert bad.status_code == 400
    assert "error" in bad.get_json()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t-\t1\t1",
            "s2\tvpa\t-\t1\t2",
        ]
    )
    ok = client.post("/api/mst", json={"tsv": tsv, "include_missing": False})
    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["sample_count"] == 2
    assert payload["node_count"] == 2
    assert payload["edge_count"] == 1
    assert payload["metadata_fields"] == ["SCHEME", "ST"]
    assert payload["aggregate_profiles"] is True
    assert payload["layout"]["root_id"] == 0
    assert payload["layout"]["mode"] == "cluster-aware-tree"
    assert payload["export"]["schema_version"] == "gmlst-visual-v1"
    assert payload["export"]["formats"] == ["graph-json", "session-json"]
    assert payload["default_color_field"] is None
    assert payload["suggested_color_fields"] == []


def test_create_visual_app_api_mst_can_return_sample_graph() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t-\t1\t1",
            "s2\tvpa\t-\t1\t1",
            "s3\tvpa\t-\t1\t2",
        ]
    )
    ok = client.post(
        "/api/mst",
        json={
            "tsv": tsv,
            "include_missing": False,
            "aggregate_profiles": False,
        },
    )

    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["sample_count"] == 3
    assert payload["node_count"] == 3
    assert payload["aggregate_profiles"] is False


def test_create_visual_app_api_mst_chooses_stable_central_root() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "s1\tvpa\t-\t1\t1\t1",
            "s2\tvpa\t-\t1\t1\t2",
            "s3\tvpa\t-\t1\t2\t2",
            "s4\tvpa\t-\t2\t2\t2",
        ]
    )

    ok = client.post("/api/mst", json={"tsv": tsv, "include_missing": False})

    assert ok.status_code == 200
    payload = ok.get_json()
    root_id = payload["layout"]["root_id"]
    assert payload["nodes"][root_id]["label"] == "s2"


def test_create_visual_app_api_mst_accepts_metadata_join() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t-\t1\t1",
            "s2\tvpa\t-\t1\t1",
            "s3\tvpa\t-\t1\t2",
        ]
    )
    metadata_tsv = "\n".join(
        [
            "ID\tCountry",
            "s1\tCN",
            "s2\tJP",
            "s3\tUS",
        ]
    )
    ok = client.post(
        "/api/mst",
        json={
            "tsv": tsv,
            "metadata_tsv": metadata_tsv,
            "include_missing": False,
            "aggregate_profiles": True,
        },
    )

    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["sample_count"] == 3
    assert payload["node_count"] == 2
    assert "Country" in payload["metadata_fields"]
    assert payload["nodes"][0]["meta"]["Country"] == "CN | JP"
    assert payload["layout"]["root_id"] == 0
    assert payload["default_color_field"] == "Country"
    assert payload["suggested_color_fields"][0] == "Country"


def test_create_visual_app_api_mst_returns_table_rows() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t11\t1\t1",
            "s2\tvpa\t12\t1\t2",
        ]
    )
    ok = client.post(
        "/api/mst",
        json={"tsv": tsv, "include_missing": False, "aggregate_profiles": False},
    )

    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["table_rows"] == [
        {
            "cluster_id": 0,
            "id": 0,
            "sample_id": "s1",
            "label": "s1",
            "member_count": 1,
            "members": ["s1"],
            "profile_key": "1|1",
            "meta": {"SCHEME": "vpa", "ST": "11"},
        },
        {
            "cluster_id": 0,
            "id": 1,
            "sample_id": "s2",
            "label": "s2",
            "member_count": 1,
            "members": ["s2"],
            "profile_key": "1|2",
            "meta": {"SCHEME": "vpa", "ST": "12"},
        },
    ]


def test_create_visual_app_api_mst_returns_cluster_assignments_and_summary() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t11\t1\t1",
            "s2\tvpa\t12\t1\t2",
            "s3\tvpa\t13\t5\t5",
        ]
    )
    ok = client.post(
        "/api/mst",
        json={
            "tsv": tsv,
            "include_missing": False,
            "aggregate_profiles": False,
            "cluster_threshold": 1,
        },
    )

    assert ok.status_code == 200
    payload = ok.get_json()
    assert [node["cluster_id"] for node in payload["nodes"]] == [0, 0, 1]
    assert [row["cluster_id"] for row in payload["table_rows"]] == [0, 0, 1]
    assert payload["cluster_summary"] == [
        {
            "cluster_id": 0,
            "node_count": 2,
            "sample_count": 2,
            "members": ["s1", "s2"],
        },
        {
            "cluster_id": 1,
            "node_count": 1,
            "sample_count": 1,
            "members": ["s3"],
        },
    ]


def test_create_visual_app_api_distance_matrix_returns_pairwise_distances() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t11\t1\t1",
            "s2\tvpa\t12\t1\t2",
            "s3\tvpa\t13\t5\t5",
        ]
    )

    ok = client.post(
        "/api/distance-matrix",
        json={
            "tsv": tsv,
            "include_missing": False,
            "aggregate_profiles": False,
            "cluster_threshold": 1,
        },
    )

    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["labels"] == ["s1", "s2", "s3"]
    assert payload["matrix"] == [
        [0, 1, 2],
        [1, 0, 2],
        [2, 2, 0],
    ]
    assert payload["metadata_fields"] == ["SCHEME", "ST"]
    assert [row["sample_id"] for row in payload["table_rows"]] == ["s1", "s2", "s3"]
    assert [row["cluster_id"] for row in payload["table_rows"]] == [0, 0, 1]
    assert payload["cluster_summary"] == [
        {
            "cluster_id": 0,
            "node_count": 2,
            "sample_count": 2,
            "members": ["s1", "s2"],
        },
        {
            "cluster_id": 1,
            "node_count": 1,
            "sample_count": 1,
            "members": ["s3"],
        },
    ]


def test_create_visual_app_api_locus_diff_returns_pairwise_locus_differences() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "s1\tvpa\t11\t1\t1\t1",
            "s2\tvpa\t12\t1\t2\t3",
        ]
    )

    ok = client.post(
        "/api/locus-diff",
        json={
            "tsv": tsv,
            "left_label": "s1",
            "right_label": "s2",
            "include_missing": False,
        },
    )

    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload == {
        "left_label": "s1",
        "right_label": "s2",
        "distance": 2,
        "differences": [
            {"locus": "L2", "left": "1", "right": "2", "type": "allele_difference"},
            {"locus": "L3", "left": "1", "right": "3", "type": "allele_difference"},
        ],
    }


def test_create_visual_app_api_locus_diff_classifies_missing_mismatches() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "s1\tvpa\t11\t1\tLNF\t1",
            "s2\tvpa\t12\t1\t2\tLNF",
        ]
    )

    ok = client.post(
        "/api/locus-diff",
        json={
            "tsv": tsv,
            "left_label": "s1",
            "right_label": "s2",
            "include_missing": True,
        },
    )

    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["distance"] == 2
    assert payload["differences"] == [
        {"locus": "L2", "left": "LNF", "right": "2", "type": "left_missing"},
        {"locus": "L3", "left": "1", "right": "LNF", "type": "right_missing"},
    ]


def test_create_visual_app_api_allele_heatmap_returns_cells() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2\tL3",
            "s1\tvpa\t11\t1\t1\tLNF",
            "s2\tvpa\t12\t1\t2\t3",
        ]
    )

    ok = client.post(
        "/api/allele-heatmap",
        json={"tsv": tsv, "aggregate_profiles": False},
    )

    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["labels"] == ["s1", "s2"]
    assert payload["loci"] == ["L1", "L2", "L3"]
    assert payload["cells"] == [
        [
            {"value": "1", "state": "present_allele"},
            {"value": "1", "state": "present_allele"},
            {"value": "LNF", "state": "missing_token"},
        ],
        [
            {"value": "1", "state": "present_allele"},
            {"value": "2", "state": "present_allele"},
            {"value": "3", "state": "present_allele"},
        ],
    ]
    assert payload["metadata_fields"] == ["SCHEME", "ST"]
    assert [row["sample_id"] for row in payload["table_rows"]] == ["s1", "s2"]


def test_create_visual_app_api_compare_results_returns_st_difference_summary() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    left_tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t11\t1\t1",
            "s2\tvpa\t12\t1\t2",
            "s3\tvpa\t13\t5\t5",
        ]
    )
    right_tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t11\t1\t1",
            "s2\tvpa\t21\t1\t2",
            "s4\tvpa\t14\t7\t7",
        ]
    )

    ok = client.post(
        "/api/compare-results",
        json={"left_tsv": left_tsv, "right_tsv": right_tsv},
    )

    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload == {
        "summary": {
            "matched_samples": 2,
            "same_st": 1,
            "different_st": 1,
            "samples_with_locus_differences": 0,
            "left_only": 1,
            "right_only": 1,
        },
        "rows": [
            {
                "sample_id": "s1",
                "left_st": "11",
                "right_st": "11",
                "status": "same_st",
                "differing_loci_count": 0,
            },
            {
                "sample_id": "s2",
                "left_st": "12",
                "right_st": "21",
                "status": "different_st",
                "differing_loci_count": 0,
            },
            {
                "sample_id": "s3",
                "left_st": "13",
                "right_st": "",
                "status": "left_only",
                "differing_loci_count": 0,
            },
            {
                "sample_id": "s4",
                "left_st": "",
                "right_st": "14",
                "status": "right_only",
                "differing_loci_count": 0,
            },
        ],
    }


def test_create_visual_app_api_rejects_non_object_json_payload() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    bad = client.post("/api/mst", json=["not", "an", "object"])
    assert bad.status_code == 400
    assert bad.get_json() == {"error": "JSON body must be an object"}


def test_create_visual_app_api_mst_parses_string_booleans() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t-\tLNF\t1",
            "s2\tvpa\t-\t1\t1",
        ]
    )

    ok = client.post(
        "/api/mst",
        json={
            "tsv": tsv,
            "include_missing": "false",
            "aggregate_profiles": "false",
        },
    )
    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["aggregate_profiles"] is False
    assert payload["edges"][0]["weight"] == 0


def test_create_visual_app_api_rejects_negative_cluster_threshold() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t-\t1\t1",
            "s2\tvpa\t-\t1\t2",
        ]
    )

    bad = client.post(
        "/api/distance-matrix",
        json={"tsv": tsv, "cluster_threshold": -1},
    )
    assert bad.status_code == 400
    assert bad.get_json() == {"error": "'cluster_threshold' must be >= 0"}


def test_create_visual_app_api_compare_results_requires_st_column() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    left_tsv = "\n".join(
        [
            "FILE\tSCHEME\tL1\tL2",
            "s1\tvpa\t1\t1",
        ]
    )
    right_tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t11\t1\t1",
        ]
    )

    bad = client.post(
        "/api/compare-results",
        json={"left_tsv": left_tsv, "right_tsv": right_tsv},
    )
    assert bad.status_code == 400
    assert bad.get_json() == {"error": "TSV must include an ST column"}


def test_create_visual_app_api_compare_results_rejects_duplicate_sample_ids() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    left_tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t11\t1\t1",
            "s1\tvpa\t12\t1\t2",
        ]
    )
    right_tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t11\t1\t1",
        ]
    )

    bad = client.post(
        "/api/compare-results",
        json={"left_tsv": left_tsv, "right_tsv": right_tsv},
    )
    assert bad.status_code == 400
    assert bad.get_json() == {"error": "Duplicate sample ID in comparison input: s1"}


def test_create_visual_app_api_malformed_json_returns_400() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    bad = client.post(
        "/api/mst",
        data="{invalid json",
        content_type="application/json",
    )
    assert bad.status_code == 400
    assert "Invalid JSON body" in bad.get_json()["error"]


def test_create_visual_app_api_empty_body_returns_400() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    bad = client.post(
        "/api/mst",
        data="",
        content_type="application/json",
    )
    assert bad.status_code == 400
    assert "error" in bad.get_json()


def test_create_visual_app_api_wrong_content_type_returns_400() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    bad = client.post(
        "/api/mst",
        data='{"tsv":""}',
        content_type="text/plain",
    )
    assert bad.status_code == 400
    assert "error" in bad.get_json()


def test_create_visual_app_api_mst_rejects_unknown_method() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    bad = client.post(
        "/api/mst",
        json={"tsv": "FILE\tL1\ns1\t1", "method": "nonexistent"},
    )
    assert bad.status_code == 400
    assert "Unknown MST method" in bad.get_json()["error"]


def test_create_visual_app_api_mst_rejects_duplicate_sample_ids() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tL1\tL2",
            "s1\t1\t1",
            "s1\t1\t2",
        ]
    )

    bad = client.post("/api/mst", json={"tsv": tsv})
    assert bad.status_code == 400
    assert "Duplicate sample ID" in bad.get_json()["error"]


def test_validate_tsv_scale_rejects_too_many_samples() -> None:
    header = "FILE\t" + "\t".join(f"L{i}" for i in range(10))
    lines = [header] + [
        f"s{i}\t" + "\t".join("1" for _ in range(10))
        for i in range(_MAX_SAMPLE_COUNT + 1)
    ]
    with pytest.raises(ValueError, match="Too many samples"):
        validate_tsv_scale("\n".join(lines))


def test_validate_tsv_scale_rejects_too_many_loci() -> None:
    header = "FILE\t" + "\t".join(f"L{i}" for i in range(_MAX_LOCI_COUNT + 1))
    lines = [header, "s1\t" + "\t".join("1" for _ in range(_MAX_LOCI_COUNT + 1))]
    with pytest.raises(ValueError, match="Too many loci"):
        validate_tsv_scale("\n".join(lines))


def test_validate_tsv_scale_allows_within_limits() -> None:
    header = "FILE\tL1\tL2"
    lines = [header, "s1\t1\t1", "s2\t1\t2"]
    validate_tsv_scale("\n".join(lines))


def test_visual_locus_diff_enforces_scale_limit_unless_force_large(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gmlst.visual import mst_shared

    monkeypatch.setattr(mst_shared, "_MAX_SAMPLE_COUNT", 1)
    runner = CliRunner()
    with runner.isolated_filesystem():
        input_path = Path("profiles.tsv")
        input_path.write_text(
            "\n".join(
                [
                    "FILE\tSCHEME\tST\tL1",
                    "s1\tvpa\t11\t1",
                    "s2\tvpa\t12\t2",
                ]
            )
        )

        blocked = runner.invoke(
            main,
            [
                "visual",
                "locus-diff",
                "--input",
                str(input_path),
                "--left-label",
                "s1",
                "--right-label",
                "s2",
            ],
        )
        forced = runner.invoke(
            main,
            [
                "visual",
                "--force-large",
                "locus-diff",
                "--input",
                str(input_path),
                "--left-label",
                "s1",
                "--right-label",
                "s2",
            ],
        )

    assert blocked.exit_code != 0
    assert "Too many samples" in blocked.output
    assert forced.exit_code == 0
    assert "Warning: bypassing TSV scale limits" in forced.output
    assert '"left_label": "s1"' in forced.output


def test_create_visual_app_api_locus_diff_rejects_duplicate_sample_ids() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tL1\tL2",
            "s1\t1\t1",
            "s1\t1\t2",
        ]
    )

    bad = client.post(
        "/api/locus-diff",
        json={"tsv": tsv, "left_label": "s1", "right_label": "s1"},
    )
    assert bad.status_code == 400
    assert "Duplicate sample ID" in bad.get_json()["error"]


def test_create_visual_app_api_allele_heatmap_rejects_duplicate_sample_ids() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tL1\tL2",
            "s1\t1\t1",
            "s1\t1\t2",
        ]
    )

    bad = client.post("/api/allele-heatmap", json={"tsv": tsv})
    assert bad.status_code == 400
    assert "Duplicate sample ID" in bad.get_json()["error"]


def test_create_visual_app_api_distance_matrix_rejects_duplicate_sample_ids() -> None:
    app = create_visual_app(title="visual test")
    client = app.test_client()

    tsv = "\n".join(
        [
            "FILE\tL1\tL2",
            "s1\t1\t1",
            "s1\t1\t2",
        ]
    )

    bad = client.post("/api/distance-matrix", json={"tsv": tsv})
    assert bad.status_code == 400
    assert "Duplicate sample ID" in bad.get_json()["error"]


def test_heatmap_api_response_contains_labels_for_export() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t1\t1\t2",
            "s2\tvpa\t2\t3\t1",
            "s3\tvpa\t1\t1\t1",
        ]
    )

    app = create_visual_app(title="heatmap export test")
    client = app.test_client()
    ok = client.post("/api/allele-heatmap", json={"tsv": tsv})
    assert ok.status_code == 200

    payload = ok.get_json()
    assert "labels" in payload
    assert len(payload["labels"]) == 3
    assert "loci" in payload
    assert "cells" in payload
    assert len(payload["cells"]) == len(payload["labels"])
    for row in payload["cells"]:
        assert len(row) == len(payload["loci"])


def test_heatmap_api_tsv_export_endpoint_returns_valid_tsv() -> None:
    tsv = "\n".join(
        [
            "FILE\tSCHEME\tST\tL1\tL2",
            "s1\tvpa\t1\t1\t2",
            "s2\tvpa\t2\t3\t1",
        ]
    )

    app = create_visual_app(title="heatmap tsv test")
    client = app.test_client()
    ok = client.post("/api/allele-heatmap", json={"tsv": tsv})
    assert ok.status_code == 200

    payload = ok.get_json()
    labels = payload["labels"]
    loci = payload["loci"]
    cells = payload["cells"]
    assert labels
    assert loci
    assert cells
    assert len(cells) == len(labels)
    assert all(len(row) == len(loci) for row in cells)


def test_create_visual_app_sets_secret_key() -> None:
    app = create_visual_app(title="secret test")
    assert app.config["SECRET_KEY"]
    assert len(app.config["SECRET_KEY"]) >= 32


def test_security_headers_present_on_index() -> None:
    app = create_visual_app(title="headers test")
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "same-origin"


def test_security_headers_present_on_error_response() -> None:
    app = create_visual_app(title="headers error test")
    client = app.test_client()
    response = client.post("/api/mst", json={"tsv": ""})
    assert response.status_code == 400
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "same-origin"


def test_cross_origin_post_blocked() -> None:
    app = create_visual_app(title="csrf test")
    client = app.test_client()
    blocked = client.post(
        "/api/mst",
        json={"tsv": ""},
        headers={"Origin": "http://evil.com"},
    )
    assert blocked.status_code == 403
    assert blocked.get_json() == {"error": "Cross-origin requests are not allowed"}


def test_cross_origin_post_blocked_by_referer() -> None:
    app = create_visual_app(title="csrf referer test")
    client = app.test_client()
    blocked = client.post(
        "/api/mst",
        json={"tsv": ""},
        headers={"Referer": "http://evil.com/page"},
    )
    assert blocked.status_code == 403
    assert blocked.get_json() == {"error": "Cross-origin requests are not allowed"}


def test_same_origin_post_allowed() -> None:
    app = create_visual_app(title="same origin test")
    client = app.test_client()
    probe = client.get("/health")
    host_url = probe.request.url.rstrip("/").replace("/health", "")
    response = client.post(
        "/api/mst",
        json={"tsv": ""},
        headers={"Origin": host_url},
    )
    assert response.status_code != 403


def test_no_origin_post_allowed() -> None:
    app = create_visual_app(title="no origin test")
    client = app.test_client()
    response = client.post("/api/mst", json={"tsv": ""})
    assert response.status_code != 403


def test_get_routes_unaffected_by_origin_check() -> None:
    app = create_visual_app(title="get unaffected test")
    client = app.test_client()
    index = client.get("/", headers={"Origin": "http://evil.com"})
    assert index.status_code == 200
    health = client.get("/health", headers={"Origin": "http://evil.com"})
    assert health.status_code == 200
