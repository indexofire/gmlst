"""Guards for validation/warning helpers extracted from _run_mlst_like_typing."""

from __future__ import annotations

import pytest

import gmlst.commands.typing as typing_cmd


@pytest.mark.parametrize(
    ("policy", "mode", "expected"),
    [
        ("default", "mlst", ("default", "default")),
        (" ChewBBACA ", "cgmlst", ("chewbbaca", "chewbbaca")),
        ("chew-exact", "cgmlst", ("chew-exact", "chewbbaca")),
    ],
)
def test_normalize_call_policy_accepts_known(
    policy: str, mode: str, expected: tuple[str, str]
) -> None:
    assert typing_cmd._normalize_call_policy(policy, mode) == expected


@pytest.mark.parametrize(
    ("policy", "mode"), [("bogus", "cgmlst"), ("chewbbaca", "mlst")]
)
def test_normalize_call_policy_rejects_invalid(policy: str, mode: str) -> None:
    with pytest.raises(SystemExit) as exc:
        typing_cmd._normalize_call_policy(policy, mode)
    assert exc.value.code == 1


@pytest.mark.parametrize(
    ("mode", "backend", "threads", "needle"),
    [
        ("mlst", "nucmer", 4, "nucmer backend may ignore"),
        ("cgmlst", "KMA", 1, "very slow on one thread"),
    ],
)
def test_warn_thread_settings_warns(
    capsys: pytest.CaptureFixture[str],
    mode: str,
    backend: str,
    threads: int,
    needle: str,
) -> None:
    typing_cmd._warn_thread_settings(mode=mode, backend=backend, threads=threads)
    captured = capsys.readouterr()
    assert needle in captured.out + captured.err


def test_warn_thread_settings_silent_for_normal_runs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    typing_cmd._warn_thread_settings(mode="cgmlst", backend="kma", threads=8)
    typing_cmd._warn_thread_settings(mode="mlst", backend="blastn", threads=4)
    captured = capsys.readouterr()
    assert captured.out + captured.err == ""
