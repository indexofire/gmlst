"""Tests for cgMLST mode naming (fast/ultrafast/balanced).

Verifies that the v0.1.5 mode renaming is correct:
- New names: fast, ultrafast, balanced
- Old names: standard (removed), chew-fast/-ultrafast/-balanced (rejected)
"""

from __future__ import annotations

import logging

from click.testing import CliRunner

from gmlst.cli import main
from gmlst.core.prefilter import cgmlst_mode_overrides_impl


class TestCgmlstModeChoices:
    """Verify the CLI option choices for --cgmlst-mode."""

    @staticmethod
    def _get_mode_choices() -> list[str]:
        runner = CliRunner()
        result = runner.invoke(main, ["typing", "cgmlst", "--help"])
        for line in result.output.split("\n"):
            if "--cgmlst-mode" in line:
                start = line.find("[") + 1
                end = line.find("]")
                if start > 0 and end > start:
                    return [c.strip() for c in line[start:end].split("|")]
        return []

    def test_fast_is_valid_choice(self) -> None:
        assert "fast" in self._get_mode_choices()

    def test_ultrafast_is_valid_choice(self) -> None:
        assert "ultrafast" in self._get_mode_choices()

    def test_balanced_is_valid_choice(self) -> None:
        assert "balanced" in self._get_mode_choices()

    def test_standard_is_not_a_choice(self) -> None:
        assert "standard" not in self._get_mode_choices()

    def test_chew_fast_is_not_a_choice(self) -> None:
        assert "chew-fast" not in self._get_mode_choices()

    def test_chew_ultrafast_is_not_a_choice(self) -> None:
        assert "chew-ultrafast" not in self._get_mode_choices()

    def test_chew_balanced_is_not_a_choice(self) -> None:
        assert "chew-balanced" not in self._get_mode_choices()

    def test_exactly_three_choices(self) -> None:
        assert len(self._get_mode_choices()) == 3

    def test_default_is_fast(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["typing", "cgmlst", "--help"])
        assert "[default: fast]" in result.output


class TestCgmlstModeOverrides:
    def test_fast_enables_exact_hash(self) -> None:
        logger = logging.getLogger("test")
        ov = cgmlst_mode_overrides_impl(
            cgmlst_mode="fast",
            scheme_type="cgmlst",
            backend="minimap2",
            logger=logger,
        )
        assert ov.exact_hash_prefilter is True
        assert ov.minimap2_hash_prefilter is True
        assert ov.evidence_fallback_backend == "blastn"

    def test_ultrafast_disables_fallback(self) -> None:
        logger = logging.getLogger("test")
        ov = cgmlst_mode_overrides_impl(
            cgmlst_mode="ultrafast",
            scheme_type="cgmlst",
            backend="minimap2",
            logger=logger,
        )
        assert ov.minimap2_fasta_speed_profile == "ultrafast"
        assert ov.minimap2_representative_main_alignment is True
        assert ov.evidence_fallback_backend == "none"

    def test_balanced_has_lower_fallback_cap(self) -> None:
        logger = logging.getLogger("test")
        ov = cgmlst_mode_overrides_impl(
            cgmlst_mode="balanced",
            scheme_type="cgmlst",
            backend="minimap2",
            logger=logger,
        )
        assert ov.evidence_fallback_max_loci == 300

    def test_unknown_mode_falls_back_to_fast(self) -> None:
        logger = logging.getLogger("test")
        ov = cgmlst_mode_overrides_impl(
            cgmlst_mode="nonexistent",
            scheme_type="cgmlst",
            backend="minimap2",
            logger=logger,
        )
        assert ov.exact_hash_prefilter is True
        assert ov.evidence_fallback_backend == "blastn"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
