"""Typing settings shared by every scheme route of one ``--guess`` run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gmlst.calling.st_lookup import STResult


@dataclass(frozen=True)
class TypingOptions:
    """Engine and output settings that stay fixed across scheme routes.

    Per-route values (samples, scheme, provider) are passed to
    :meth:`run_scheme`; novel-data writing and file output are disabled
    there because ``--guess`` merges results itself.
    """

    mode: str
    backend: str
    cgmlst_mode: str
    min_id: float
    min_cov: float
    min_depth: float
    min_join_overlap: int
    minscore: float
    fmt: str
    cache_dir: Path | None
    force_reindex: bool
    no_header: bool
    threads: int
    max_workers: int
    count_same_copy: bool
    quiet: bool
    detail: bool

    def run_scheme(
        self,
        *,
        samples: tuple[Path, ...],
        scheme: str,
        provider: str | None,
        result_sink: list[STResult],
    ) -> None:
        """Type *samples* against one scheme, appending results to the sink."""
        # Resolved at call time: gmlst.commands.typing imports the guess
        # runner (and so this module), and tests patch the runner there.
        from gmlst.commands import typing as typing_cmd

        typing_cmd._run_mlst_like_typing(
            mode=self.mode,
            backend=self.backend,
            cgmlst_mode=self.cgmlst_mode,
            min_id=self.min_id,
            min_cov=self.min_cov,
            min_depth=self.min_depth,
            min_join_overlap=self.min_join_overlap,
            minscore=self.minscore,
            fmt=self.fmt,
            cache_dir=self.cache_dir,
            force_reindex=self.force_reindex,
            no_header=self.no_header,
            threads=self.threads,
            max_workers=self.max_workers,
            count_same_copy=self.count_same_copy,
            quiet=self.quiet,
            detail=self.detail,
            samples=samples,
            scheme=scheme,
            provider=provider,
            result_sink=result_sink,
            output=None,
            novel_allele=False,
            novel_profile=False,
            output_dir=None,
            suppress_output=True,
        )
