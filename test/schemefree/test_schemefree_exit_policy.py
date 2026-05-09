from __future__ import annotations

from gmlst.commands.typing import (
    _count_errors_by_stage,
    _primary_failed_stage,
    _schemefree_exit_decision,
    _stage_exit_code,
)


def test_schemefree_exit_code_success() -> None:
    assert _schemefree_exit_decision(3, 0, [], fail_on_error=False) == (
        0,
        "all_succeeded",
        None,
    )


def test_schemefree_exit_code_partial_default() -> None:
    errors = [{"stage": "prediction"}]
    assert _schemefree_exit_decision(2, 1, errors, fail_on_error=False) == (
        0,
        "partial_failed_allowed",
        "prediction",
    )


def test_schemefree_exit_code_partial_strict() -> None:
    errors = [{"stage": "assembly"}]
    assert _schemefree_exit_decision(2, 1, errors, fail_on_error=True) == (
        3,
        "partial_failed_strict_assembly",
        "assembly",
    )


def test_schemefree_exit_code_all_failed() -> None:
    errors = [{"stage": "prediction"}, {"stage": "prediction"}]
    assert _schemefree_exit_decision(0, 2, errors, fail_on_error=False) == (
        4,
        "all_failed_prediction",
        "prediction",
    )


def test_count_errors_by_stage() -> None:
    errors = [
        {"stage": "input"},
        {"stage": "prediction"},
        {"stage": "prediction"},
    ]
    assert _count_errors_by_stage(errors) == {"input": 1, "prediction": 2}


def test_primary_failed_stage_uses_count_then_priority() -> None:
    errors = [
        {"stage": "assembly"},
        {"stage": "prediction"},
        {"stage": "input"},
        {"stage": "input"},
    ]
    assert _primary_failed_stage(errors) == "input"


def test_stage_exit_code_mapping() -> None:
    assert _stage_exit_code("input") == 2
    assert _stage_exit_code("assembly") == 3
    assert _stage_exit_code("prediction") == 4
    assert _stage_exit_code("anything") == 5
