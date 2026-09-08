"""Schemefree exit code decision logic."""

from __future__ import annotations


def schemefree_exit_decision(
    success_count: int,
    failed_count: int,
    errors: list[dict[str, str]],
    fail_on_error: bool,
) -> tuple[int, str, str | None]:
    """Decide the tgMLST process exit code from per-sample outcomes.

    Returns ``(exit_code, reason, primary_stage)``: 0 when everything (or
    partial failures with ``fail_on_error`` disabled) succeeded; otherwise a
    stage-specific exit code derived from the dominant failed stage.
    """
    if failed_count == 0:
        return 0, "all_succeeded", None

    primary_stage = primary_failed_stage(errors)
    stage_exit = stage_exit_code(primary_stage)

    if success_count == 0:
        return stage_exit, f"all_failed_{primary_stage}", primary_stage
    if fail_on_error:
        return (
            stage_exit,
            f"partial_failed_strict_{primary_stage}",
            primary_stage,
        )
    return 0, "partial_failed_allowed", primary_stage


def count_errors_by_stage(errors: list[dict[str, str]]) -> dict[str, int]:
    """Count error records per pipeline stage (defaulting to "unknown")."""
    counts: dict[str, int] = {}
    for error in errors:
        stage = error.get("stage", "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def primary_failed_stage(errors: list[dict[str, str]]) -> str:
    """Pick the dominant failed stage.

    Most errors first; ties break toward the earliest pipeline stage.
    """
    counts = count_errors_by_stage(errors)
    if not counts:
        return "unknown"

    priority = {"input": 0, "assembly": 1, "prediction": 2, "unknown": 3}
    return sorted(
        counts.items(),
        key=lambda kv: (-kv[1], priority.get(kv[0], 99), kv[0]),
    )[0][0]


def stage_exit_code(stage: str) -> int:
    """Map a failed pipeline stage to its distinct exit code (2-5, default 5)."""
    mapping = {
        "input": 2,
        "assembly": 3,
        "prediction": 4,
        "unknown": 5,
    }
    return mapping.get(stage, 5)
