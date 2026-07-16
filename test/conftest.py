"""Shared test fixtures and helpers for the gmlst test suite."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from gmlst.aligners.base import AlignmentResult


@dataclass
class DummySTResult:
    sample_id: str
    st: str | None = None
    is_novel: bool = False


class DummyScheme:
    def __init__(
        self,
        name: str = "dummy",
        loci: list[str] | None = None,
        allele_files: dict[str, Path] | None = None,
    ) -> None:
        self.name = name
        self.loci = loci or ["abc", "def"]
        self.allele_files = allele_files or {}


class DummyCache:
    def __init__(
        self,
        scheme: DummyScheme | None = None,
        index_dir: Path | None = None,
    ) -> None:
        self._scheme = scheme
        self._index_dir = index_dir or Path("/tmp/gmlst_test_idx")

    def ensure_scheme(
        self, name: str, provider: str = "pubmlst", scheme_type: str = "mlst"
    ) -> DummyScheme:
        return self._scheme or DummyScheme(name=name)

    def index_dir(
        self, name: str, backend: str = "blastn", provider: str = "pubmlst"
    ) -> Path:
        self._index_dir.mkdir(parents=True, exist_ok=True)
        return self._index_dir


class DummyAligner:
    def __init__(
        self,
        matches: list[Any] | None = None,
        supports_fastq: bool = True,
    ) -> None:
        self._matches = matches or []
        self.supports_fastq = supports_fastq

    def check_dependencies(self) -> None:
        pass

    def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
        return index_dir

    def align(
        self, sample_path: Any, index_path: Any, loci: list[str], input_type: str
    ) -> AlignmentResult:
        return AlignmentResult(
            sample_id="s1",
            matches=self._matches,
            failed_loci=[],
            backend="blastn",
            runtime_seconds=0.1,
        )


class DummySample:
    def __init__(
        self,
        sample_id: str = "s1",
        input_type: str = "fasta",
        path: Path | None = None,
        mate_path: Path | None = None,
    ) -> None:
        self.sample_id = sample_id
        self.input_type = input_type
        self.path = path or Path("/tmp/s1.fna")
        self.mate_path = mate_path


@pytest.fixture
def tmp_sample(tmp_path: Path) -> Path:
    """Create a minimal FASTA sample file."""
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    return sample


@pytest.fixture
def tmp_scheme_files(tmp_path: Path) -> dict[str, Path]:
    """Create minimal allele FASTA files for two loci."""
    abc = tmp_path / "abc.tfa"
    abc.write_text(
        ">abc_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n"
        ">abc_2\nTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT\n"
    )
    def_locus = tmp_path / "def.tfa"
    def_locus.write_text(
        ">def_1\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC\n"
        ">def_2\nGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG\n"
    )
    return {"abc": abc, "def": def_locus}
