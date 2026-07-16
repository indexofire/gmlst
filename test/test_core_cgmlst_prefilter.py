from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import gmlst.core as core
from gmlst.aligners.base import AlignmentResult, AlleleMatch
from gmlst.calling.allele import LocusCall
from gmlst.core.gene_predictor import PredictedGene
from gmlst.readers.sample import SampleInput


@dataclass
class _DummyResult:
    sample_id: str


def test_run_typing_cgmlst_fasta_uses_prefiltered_alleles(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    abc = tmp_path / "abc.tfa"
    abc.write_text(
        ">abc_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n>abc_2\nTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT\n"
    )
    def_locus = tmp_path / "def.tfa"
    def_locus.write_text(
        ">def_1\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC\n>def_2\nGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG\n"
    )

    class DummyScheme:
        name = "dummy"
        loci = ["abc", "def"]
        allele_files = {"abc": abc, "def": def_locus}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, object] = {}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, allele_fastas, index_dir):
            merged = "\n".join(path.read_text() for path in allele_fastas)
            captured["merged"] = merged
            return index_dir

        def align(self, _sample_path, _index_path, _loci, _input_type):
            class _Aln:
                runtime_seconds = 0.1

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))
    monkeypatch.setattr(
        core,
        "prefilter_assembly_candidates",
        lambda **_: {"abc": [("1", 10.0)], "def": [("2", 7.0)]},
    )

    results = core.run_typing(
        [sample],
        "dummy",
        "blastn",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=1,
    )

    assert len(results) == 1
    merged = str(captured["merged"])
    assert ">abc_1" in merged
    assert ">def_2" in merged
    assert ">abc_2" not in merged
    assert ">def_1" not in merged


def test_run_typing_cgmlst_minimap2_uses_prefilter_and_candidate_fasta(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    abc = tmp_path / "abc.tfa"
    abc.write_text(
        ">abc_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n"
        ">abc_2\nTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT\n"
    )

    class DummyScheme:
        name = "dummy"
        loci = ["abc"]
        allele_files = {"abc": abc}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, object] = {"prefilter_called": False}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, _allele_fastas, index_dir):
            return index_dir

        def align(self, _sample_path, index_path, _loci, _input_type):
            merged = index_path / "alleles.fasta"
            captured["merged"] = merged.read_text()

            class _Aln:
                runtime_seconds = 0.1

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setenv("GMLST_CGMLST_MINIMAP2_HASH_PREFILTER", "1")
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))

    def fake_prefilter(**_kwargs):
        captured["prefilter_called"] = True
        return {"abc": [("1", 8.0)]}, None

    monkeypatch.setattr(
        core,
        "_minimap2_representative_prefilter_candidates",
        lambda **kwargs: fake_prefilter(**kwargs),
    )

    results = core.run_typing(
        [sample],
        "dummy",
        "minimap2",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=16,
    )

    assert len(results) == 1
    assert captured["prefilter_called"] is True
    merged_text = str(captured["merged"])
    assert ">abc_1" in merged_text
    assert ">abc_2" in merged_text


def test_run_typing_cgmlst_prefilter_forwards_k_and_top_n(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    abc = tmp_path / "abc.tfa"
    abc.write_text(">abc_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    class DummyScheme:
        name = "dummy"
        loci = ["abc"]
        allele_files = {"abc": abc}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, object] = {}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, _allele_fastas, index_dir):
            return index_dir

        def align(self, _sample_path, _index_path, _loci, _input_type):
            class _Aln:
                runtime_seconds = 0.1

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))

    def fake_prefilter(**kwargs):
        captured["k"] = kwargs["k"]
        captured["top_n"] = kwargs["top_n"]
        return {"abc": [("1", 4.0)]}

    monkeypatch.setattr(core, "prefilter_assembly_candidates", fake_prefilter)

    core.run_typing(
        [sample],
        "dummy",
        "blastn",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=1,
        prefilter_k=25,
        prefilter_top_n=5,
    )

    assert captured["k"] == 25
    assert captured["top_n"] == 5


def test_run_typing_cgmlst_minimap2_prefilter_uses_fast_settings(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    abc = tmp_path / "abc.tfa"
    abc.write_text(">abc_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    class DummyScheme:
        name = "dummy"
        loci = ["abc"]
        allele_files = {"abc": abc}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, object] = {}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, _allele_fastas, index_dir):
            return index_dir

        def align(self, _sample_path, _index_path, _loci, _input_type):
            class _Aln:
                runtime_seconds = 0.1

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setenv("GMLST_CGMLST_MINIMAP2_HASH_PREFILTER", "1")
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))

    def fake_prefilter(**kwargs):
        captured["min_identity"] = kwargs["min_identity"]
        captured["min_coverage"] = kwargs["min_coverage"]
        return {}, None

    monkeypatch.setattr(
        core,
        "_minimap2_representative_prefilter_candidates",
        lambda **kwargs: fake_prefilter(**kwargs),
    )

    core.run_typing(
        [sample],
        "dummy",
        "minimap2",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=1,
        prefilter_top_n=5,
    )

    assert captured["min_identity"] == 95.0
    assert captured["min_coverage"] == 0.8


def test_run_typing_chew_ultrafast_uses_representative_main_alignment(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    a = tmp_path / "a.tfa"
    a.write_text(">a_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    b = tmp_path / "b.tfa"
    b.write_text(">b_1\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC\n")

    class DummyScheme:
        name = "dummy"
        loci = ["a", "b"]
        allele_files = {"a": a, "b": b}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, object] = {"align_calls": 0, "call_matches": 0}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, _allele_fastas, index_dir):
            (index_dir / "alleles.fasta").write_text("")
            (index_dir / "alleles.asm20.mmi").write_text("mmi")
            return index_dir

        def align(self, _sample_path, _index_path, _loci, _input_type):
            captured["align_calls"] = int(captured["align_calls"]) + 1
            return AlignmentResult(
                sample_id="s1",
                matches=[],
                failed_loci=[],
                backend="minimap2",
                runtime_seconds=0.0,
            )

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    rep_aln = AlignmentResult(
        sample_id="s1",
        matches=[
            AlleleMatch(locus="a", allele_id="1", identity=100.0, coverage=1.0),
            AlleleMatch(locus="b", allele_id="1", identity=100.0, coverage=1.0),
        ],
        failed_loci=[],
        backend="minimap2",
        runtime_seconds=1.2,
    )

    def fake_call_all_loci(aln, *_args, **_kwargs):
        captured["call_matches"] = len(aln.matches)
        return {}

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", fake_call_all_loci)
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))
    monkeypatch.setattr(
        core,
        "_minimap2_representative_prefilter_candidates",
        lambda **_: ({"a": [("1", 9.0)], "b": [("1", 9.0)]}, rep_aln),
    )

    results = core.run_typing(
        [sample],
        "dummy",
        "minimap2",
        provider="pubmlst",
        scheme_type="cgmlst",
        cgmlst_mode="chew-ultrafast",
        threads=1,
        prefilter_min_loci_fraction=0.1,
    )

    assert len(results) == 1
    assert captured["align_calls"] == 0
    assert captured["call_matches"] == 2


def test_run_typing_cgmlst_prefilter_low_coverage_falls_back_to_full_alleles(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    a = tmp_path / "a.tfa"
    a.write_text(">a_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    b = tmp_path / "b.tfa"
    b.write_text(">b_1\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC\n")
    c = tmp_path / "c.tfa"
    c.write_text(">c_1\nGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG\n")
    d = tmp_path / "d.tfa"
    d.write_text(">d_1\nTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT\n")

    class DummyScheme:
        name = "dummy"
        loci = ["a", "b", "c", "d"]
        allele_files = {"a": a, "b": b, "c": c, "d": d}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, str] = {}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, allele_fastas, index_dir):
            captured["merged"] = "\n".join(path.read_text() for path in allele_fastas)
            return index_dir

        def align(self, _sample_path, _index_path, _loci, _input_type):
            class _Aln:
                runtime_seconds = 0.1

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))
    monkeypatch.setattr(
        core,
        "prefilter_assembly_candidates",
        lambda **_: {"a": [("1", 5.0)]},
    )

    core.run_typing(
        [sample],
        "dummy",
        "blastn",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=1,
        prefilter_min_loci_fraction=0.75,
    )

    merged = captured["merged"]
    assert ">a_1" in merged
    assert ">b_1" in merged
    assert ">c_1" in merged
    assert ">d_1" in merged


def test_run_typing_cgmlst_prefilter_can_be_disabled(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    abc = tmp_path / "abc.tfa"
    abc.write_text(">abc_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    class DummyScheme:
        name = "dummy"
        loci = ["abc"]
        allele_files = {"abc": abc}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, _allele_fastas, index_dir):
            return index_dir

        def align(self, _sample_path, _index_path, _loci, _input_type):
            class _Aln:
                runtime_seconds = 0.1

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))

    def fail_prefilter(**_kwargs):
        raise AssertionError("prefilter should not be called")

    monkeypatch.setattr(core, "prefilter_assembly_candidates", fail_prefilter)

    results = core.run_typing(
        [sample],
        "dummy",
        "blastn",
        provider="pubmlst",
        scheme_type="cgmlst",
        prefilter_enabled=False,
        threads=1,
    )

    assert len(results) == 1


def test_run_typing_cgmlst_prefilter_auto_disables_for_large_scheme(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    a = tmp_path / "a.tfa"
    a.write_text(">a_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    b = tmp_path / "b.tfa"
    b.write_text(">b_1\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC\n")

    class DummyScheme:
        name = "dummy"
        loci = ["a", "b"]
        allele_files = {"a": a, "b": b}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, object] = {}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, allele_fastas, index_dir):
            captured["indexed_paths"] = [str(path) for path in allele_fastas]
            return index_dir

        def align(self, _sample_path, _index_path, _loci, _input_type):
            class _Aln:
                runtime_seconds = 0.1

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setenv("GMLST_CGMLST_PREFILTER_MAX_LOCI", "1")
    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))

    def fail_prefilter(**_kwargs):
        raise AssertionError("prefilter should be skipped for oversized schemes")

    monkeypatch.setattr(core, "prefilter_assembly_candidates", fail_prefilter)

    results = core.run_typing(
        [sample],
        "dummy",
        "blastn",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=1,
    )

    assert len(results) == 1
    indexed_paths = captured.get("indexed_paths")
    assert isinstance(indexed_paths, list)
    assert len(indexed_paths) == 2


def test_cgmlst_prefilter_max_loci_default(monkeypatch) -> None:
    monkeypatch.delenv("GMLST_CGMLST_PREFILTER_MAX_LOCI", raising=False)
    assert core._cgmlst_prefilter_max_loci() == 3000


def test_cgmlst_prefilter_max_loci_invalid_env_falls_back_default(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GMLST_CGMLST_PREFILTER_MAX_LOCI", "invalid")
    assert core._cgmlst_prefilter_max_loci() == 3000


def test_minimap2_hash_prefilter_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("GMLST_CGMLST_MINIMAP2_HASH_PREFILTER", raising=False)
    assert core._minimap2_hash_prefilter_enabled() is False


def test_minimap2_hash_prefilter_enabled_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_MINIMAP2_HASH_PREFILTER", "1")
    assert core._minimap2_hash_prefilter_enabled() is True


def test_minimap2_hash_locus_top_n_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("GMLST_CGMLST_MINIMAP2_HASH_LOCI_TOP_N", raising=False)
    assert core._minimap2_hash_locus_top_n() == 0


def test_minimap2_hash_locus_top_n_enabled_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_MINIMAP2_HASH_LOCI_TOP_N", "42")
    assert core._minimap2_hash_locus_top_n() == 42


def test_minimap2_bsr_confirm_max_loci_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("GMLST_CGMLST_MINIMAP2_BSR_CONFIRM_MAX_LOCI", raising=False)
    assert core._minimap2_bsr_confirm_max_loci() == 0


def test_minimap2_bsr_confirm_max_loci_enabled_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_MINIMAP2_BSR_CONFIRM_MAX_LOCI", "120")
    assert core._minimap2_bsr_confirm_max_loci() == 120


def test_minimap2_ultra_second_pass_budget_defaults_to_adaptive(monkeypatch) -> None:
    monkeypatch.delenv(
        "GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI", raising=False
    )
    assert core._minimap2_ultrafast_second_pass_max_loci() is None


def test_minimap2_ultra_second_pass_budget_accepts_numeric(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI", "50")
    assert core._minimap2_ultrafast_second_pass_max_loci() == 50


def test_kma_fastq_mem_mode_enabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("GMLST_CGMLST_KMA_FASTQ_MEM_MODE", raising=False)
    assert core._kma_fastq_mem_mode_enabled() is True


def test_kma_fastq_mem_mode_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_KMA_FASTQ_MEM_MODE", "0")
    assert core._kma_fastq_mem_mode_enabled() is False


def test_kma_fastq_mem_confirm_max_loci_defaults(monkeypatch) -> None:
    monkeypatch.delenv("GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI", raising=False)
    assert core._kma_fastq_mem_confirm_max_loci() == 64


def test_kma_fastq_mem_confirm_max_loci_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI", "12")
    assert core._kma_fastq_mem_confirm_max_loci() == 12


def test_resolve_cgmlst_cds_training_file_autocreates_in_single_mode(
    monkeypatch, tmp_path: Path
) -> None:
    allele_file = tmp_path / "abc.tfa"
    allele_file.write_text(">abc_1\nATGAAATAG\n")
    sample = tmp_path / "sample.fna"
    sample.write_text(">contig\nATGAAATTTCCCGGGATGAAATTTCCCGGGATGAAATTT\n")

    created: dict[str, Path] = {}

    def _fake_create(sample_path: Path, output_path: Path) -> Path:
        created["sample"] = sample_path
        created["output"] = output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"training")
        return output_path

    monkeypatch.delenv("GMLST_CGMLST_CDS_TRAINING_FILE", raising=False)
    monkeypatch.setattr(
        "gmlst.core.gene_predictor.create_pyrodigal_training_file",
        _fake_create,
    )

    resolved = core._resolve_cgmlst_cds_training_file(
        allele_files={"abc": allele_file},
        sample_paths=[sample],
        mode="single",
    )

    assert resolved is not None
    assert resolved.exists()
    assert created["sample"] == sample
    assert created["output"] == resolved


def test_resolve_cgmlst_cds_training_file_skips_autocreate_in_meta_mode(
    monkeypatch, tmp_path: Path
) -> None:
    allele_file = tmp_path / "abc.tfa"
    allele_file.write_text(">abc_1\nATGAAATAG\n")
    sample = tmp_path / "sample.fna"
    sample.write_text(">contig\nATGAAATTTCCCGGGATGAAATTTCCCGGGATGAAATTT\n")

    def _unexpected(_sample_path: Path, _output_path: Path) -> Path:
        raise AssertionError("training creation should not run in meta mode")

    monkeypatch.delenv("GMLST_CGMLST_CDS_TRAINING_FILE", raising=False)
    monkeypatch.setattr(
        "gmlst.core.gene_predictor.create_pyrodigal_training_file",
        _unexpected,
    )

    resolved = core._resolve_cgmlst_cds_training_file(
        allele_files={"abc": allele_file},
        sample_paths=[sample],
        mode="meta",
    )
    assert resolved is None


def test_write_cds_coordinates_outputs_tsv(monkeypatch, tmp_path: Path) -> None:
    sample_path = tmp_path / "sample.fna"
    sample_path.write_text(">contig1\nATGAAATTTCCCGGG\n")
    output_path = tmp_path / "cds.tsv"

    def _fake_predict(
        _sample_path: Path,
        *,
        cds_prediction_mode: str,
        cds_training_file: Path | None,
        cds_closed_ends: bool,
    ) -> list[PredictedGene]:
        assert cds_prediction_mode == "single"
        assert cds_training_file is None
        assert cds_closed_ends is False
        return [
            PredictedGene(
                sample_id="sample",
                gene_id="gene_1",
                sequence="ATGAAATTT",
                contig_id="contig1",
                start=1,
                end=9,
                strand="+",
                partial_begin=False,
                partial_end=False,
            )
        ]

    monkeypatch.setattr(core, "_predict_cds_genes", _fake_predict)
    core._write_cds_coordinates(
        samples=[SampleInput.from_path(sample_path)],
        output_path=output_path,
        prediction_mode="single",
        training_file=None,
        closed_ends=False,
    )

    lines = output_path.read_text().strip().splitlines()
    assert lines[0].startswith("sample_id\tgene_id\tcontig_id\tstart\tend\tstrand")
    assert "sample\tgene_1\tcontig1\t1\t9\t+\t9\t0\t0\tsingle" in lines[1]


def test_minimap2_fasta_speed_profile_defaults_to_default(monkeypatch) -> None:
    monkeypatch.delenv("GMLST_MINIMAP2_FASTA_SPEED_PROFILE", raising=False)
    assert core._minimap2_fasta_speed_profile() == "default"


def test_minimap2_fasta_speed_profile_accepts_fast(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_MINIMAP2_FASTA_SPEED_PROFILE", "fast")
    assert core._minimap2_fasta_speed_profile() == "fast"


def test_minimap2_fasta_speed_profile_accepts_ultrafast(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_MINIMAP2_FASTA_SPEED_PROFILE", "ultrafast")
    assert core._minimap2_fasta_speed_profile() == "ultrafast"


def test_minimap2_representative_main_alignment_disabled_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "GMLST_CGMLST_MINIMAP2_REPRESENTATIVE_MAIN_ALIGNMENT", raising=False
    )
    assert core._minimap2_representative_main_alignment() is False


def test_minimap2_representative_main_alignment_enabled_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_MINIMAP2_REPRESENTATIVE_MAIN_ALIGNMENT", "1")
    assert core._minimap2_representative_main_alignment() is True


def test_exact_hash_prefilter_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("GMLST_CGMLST_EXACT_HASH_PREFILTER", raising=False)
    assert core._exact_hash_prefilter_enabled() is False


def test_exact_hash_prefilter_enabled_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_EXACT_HASH_PREFILTER", "1")
    assert core._exact_hash_prefilter_enabled() is True


def test_cgmlst_mode_overrides_standard_for_minimap2() -> None:
    ov = core._cgmlst_mode_overrides(
        cgmlst_mode="standard",
        scheme_type="cgmlst",
        backend="minimap2",
    )
    assert ov.protein_exact_hash_prefilter is False
    assert ov.exact_hash_prefilter is False
    assert ov.minimap2_hash_prefilter is False
    assert ov.minimap2_hash_locus_top_n is None
    assert ov.minimap2_hash_refine_max_loci is None
    assert ov.minimap2_fasta_emit_cigar is None
    assert ov.minimap2_fasta_speed_profile is None
    assert ov.minimap2_representative_main_alignment is None
    assert ov.minimap2_bsr_confirm_max_loci is None
    assert ov.minimap2_ultrafast_second_pass_max_loci is None
    assert ov.evidence_fallback_backend is None


def test_cgmlst_mode_overrides_chew_fast_for_minimap2() -> None:
    ov = core._cgmlst_mode_overrides(
        cgmlst_mode="chew-fast",
        scheme_type="cgmlst",
        backend="minimap2",
    )
    assert ov.protein_exact_hash_prefilter is False
    assert ov.exact_hash_prefilter is True
    assert ov.minimap2_hash_prefilter is True
    assert ov.minimap2_hash_locus_top_n is None
    assert ov.minimap2_hash_refine_max_loci == 500
    assert ov.minimap2_fasta_emit_cigar is True
    assert ov.minimap2_fasta_speed_profile == "default"
    assert ov.minimap2_representative_main_alignment is False
    assert ov.minimap2_bsr_confirm_max_loci is None
    assert ov.minimap2_ultrafast_second_pass_max_loci is None
    assert ov.evidence_fallback_backend == "blastn"
    assert ov.evidence_fallback_max_loci == 500


def test_cgmlst_mode_overrides_chew_balanced_for_minimap2() -> None:
    ov = core._cgmlst_mode_overrides(
        cgmlst_mode="chew-balanced",
        scheme_type="cgmlst",
        backend="minimap2",
    )
    assert ov.protein_exact_hash_prefilter is False
    assert ov.exact_hash_prefilter is True
    assert ov.minimap2_hash_prefilter is True
    assert ov.minimap2_hash_locus_top_n is None
    assert ov.minimap2_hash_refine_max_loci == 500
    assert ov.minimap2_fasta_emit_cigar is True
    assert ov.minimap2_fasta_speed_profile == "default"
    assert ov.minimap2_representative_main_alignment is False
    assert ov.minimap2_bsr_confirm_max_loci is None
    assert ov.minimap2_ultrafast_second_pass_max_loci is None
    assert ov.evidence_fallback_backend == "blastn"
    assert ov.evidence_fallback_max_loci == 300


def test_cgmlst_mode_overrides_chew_ultrafast_for_minimap2() -> None:
    ov = core._cgmlst_mode_overrides(
        cgmlst_mode="chew-ultrafast",
        scheme_type="cgmlst",
        backend="minimap2",
    )
    assert ov.protein_exact_hash_prefilter is False
    assert ov.exact_hash_prefilter is True
    assert ov.minimap2_hash_prefilter is True
    assert ov.minimap2_hash_locus_top_n is None
    assert ov.minimap2_hash_refine_max_loci == 0
    assert ov.minimap2_fasta_emit_cigar is False
    assert ov.minimap2_fasta_speed_profile == "ultrafast"
    assert ov.minimap2_representative_main_alignment is True
    assert ov.minimap2_bsr_confirm_max_loci == 120
    assert ov.minimap2_ultrafast_second_pass_max_loci is None
    assert ov.evidence_fallback_backend == "none"
    assert ov.evidence_fallback_max_loci == 0


def test_cgmlst_mode_overrides_chew_bsr_for_minimap2() -> None:
    ov = core._cgmlst_mode_overrides(
        cgmlst_mode="chew-bsr",
        scheme_type="cgmlst",
        backend="minimap2",
    )
    assert ov.protein_exact_hash_prefilter is True
    assert ov.exact_hash_prefilter is True
    assert ov.minimap2_hash_prefilter is True
    assert ov.minimap2_hash_locus_top_n is None
    assert ov.minimap2_hash_refine_max_loci == 500
    assert ov.minimap2_fasta_emit_cigar is True
    assert ov.minimap2_fasta_speed_profile == "default"
    assert ov.minimap2_representative_main_alignment is False
    assert ov.minimap2_bsr_confirm_max_loci == 0
    assert ov.minimap2_ultrafast_second_pass_max_loci is None
    assert ov.evidence_fallback_backend == "blastn"
    assert ov.evidence_fallback_max_loci == 500


def test_build_allele_hash_index_groups_duplicate_sequences() -> None:
    index = core._build_allele_hash_index(
        {
            "a": {"1": "ATGC", "2": "ATGC"},
            "b": {"1": "CCCC"},
        }
    )
    values = list(index.values())
    assert any(set(entries) == {("a", "1"), ("a", "2")} for entries in values)


def test_build_allele_protein_hash_index_groups_synonymous_sequences() -> None:
    index = core._build_allele_protein_hash_index(
        {
            "a": {
                "1": "ATGGCC",
                "2": "ATGGCT",
            }
        }
    )
    values = list(index.values())
    assert any(set(entries) == {("a", "1"), ("a", "2")} for entries in values)


def test_translate_cds_to_protein_stops_at_stop_codon() -> None:
    assert core._translate_cds_to_protein("ATGAAATAATTT") == "MK"


def test_representatives_from_nested_alleles_selects_lowest_id() -> None:
    reps = core._representatives_from_nested_alleles(
        {
            "a": {"2": "AAAA", "1": "AAAT"},
            "b": {"x": "CCCC", "10": "CCCT"},
        }
    )

    assert reps == {("a", "1"): "AAAT", ("b", "10"): "CCCT"}


def test_load_or_build_minimap2_representative_index_reuses_cache(
    tmp_path: Path,
) -> None:
    class DummyAligner:
        def __init__(self) -> None:
            self.calls = 0

        def index(self, allele_fastas: list[Path], index_dir: Path) -> Path:
            self.calls += 1
            source = allele_fastas[0]
            merged = index_dir / "alleles.fasta"
            merged.write_text(source.read_text())
            (index_dir / "alleles.asm20.mmi").write_text("index")
            return index_dir

    aligner = DummyAligner()
    index_dir = tmp_path / "idx"
    reps = {
        ("a", "1"): "ATGGCC",
        ("b", "1"): "ATGAAA",
    }

    core._load_or_build_minimap2_representative_index(
        aligner=aligner,
        index_dir=index_dir,
        representatives=reps,
        force_reindex=False,
    )
    core._load_or_build_minimap2_representative_index(
        aligner=aligner,
        index_dir=index_dir,
        representatives=reps,
        force_reindex=False,
    )

    assert aligner.calls == 1
    assert (index_dir / "representative_meta.json").exists()
    assert (index_dir / "representatives.fasta").exists()


def test_load_or_build_exact_hash_indexes_writes_precomputed_files(
    tmp_path: Path,
) -> None:
    locus_a = tmp_path / "a.tfa"
    locus_a.write_text(">a_1\nATGGCC\n")
    locus_b = tmp_path / "b.tfa"
    locus_b.write_text(">b_1\nATGAAA\n")
    allele_files = {"a": locus_a, "b": locus_b}
    allele_sequences = {
        "a": {"1": "ATGGCC"},
        "b": {"1": "ATGAAA"},
    }

    dna, protein = core._load_or_build_exact_hash_indexes(
        allele_files=allele_files,
        allele_sequences=allele_sequences,
        include_protein=True,
    )

    precomputed = tmp_path / "pre_computed"
    assert (precomputed / "exact_hash_meta.json").exists()
    assert (precomputed / "dna_hash_index.json").exists()
    assert (precomputed / "protein_hash_index.json").exists()
    assert dna
    assert protein


def test_load_or_build_exact_hash_indexes_rebuilds_on_corrupt_cache(
    tmp_path: Path,
) -> None:
    locus_a = tmp_path / "a.tfa"
    locus_a.write_text(">a_1\nATGGCC\n")
    allele_files = {"a": locus_a}
    allele_sequences = {"a": {"1": "ATGGCC"}}

    precomputed = tmp_path / "pre_computed"
    precomputed.mkdir()
    (precomputed / "dna_hash_index.json").write_text("NOT VALID JSON{{{")

    import json as json_mod

    (precomputed / "exact_hash_meta.json").write_text(
        json_mod.dumps({"fingerprint": "anything"})
    )

    dna, protein = core._load_or_build_exact_hash_indexes(
        allele_files=allele_files,
        allele_sequences=allele_sequences,
        include_protein=False,
    )

    assert dna
    assert protein is None
    assert (precomputed / "dna_hash_index.json").exists()
    rebuilt = json_mod.loads((precomputed / "dna_hash_index.json").read_text())
    assert isinstance(rebuilt, dict)


def test_load_or_build_exact_hash_indexes_reuses_precomputed_cache(
    monkeypatch, tmp_path: Path
) -> None:
    locus_a = tmp_path / "a.tfa"
    locus_a.write_text(">a_1\nATGGCC\n")
    allele_files = {"a": locus_a}
    allele_sequences = {"a": {"1": "ATGGCC"}}

    first_dna, first_protein = core._load_or_build_exact_hash_indexes(
        allele_files=allele_files,
        allele_sequences=allele_sequences,
        include_protein=True,
    )

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("hash builders should not run on cache hit")

    monkeypatch.setattr(core, "_build_allele_hash_index", _unexpected)
    monkeypatch.setattr(core, "_build_allele_protein_hash_index", _unexpected)

    second_dna, second_protein = core._load_or_build_exact_hash_indexes(
        allele_files=allele_files,
        allele_sequences=allele_sequences,
        include_protein=True,
    )

    assert second_dna == first_dna
    assert second_protein == first_protein


def test_load_or_build_sample_cds_hashes_reuses_cache(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">contig\nATGAAATTTCCCGGGATGAAATTTCCCGGG\n")

    monkeypatch.setattr(
        core,
        "_predict_cds_sequences",
        lambda _sample_path, **_kwargs: ["ATGAAATTT", "ATGGGGTAA"],
    )
    first = core._load_or_build_sample_cds_hashes(
        sample,
        cache_root=tmp_path,
        cds_prediction_mode="single",
        cds_training_file=None,
        cds_closed_ends=False,
    )

    def _unexpected(_sample_path: Path, **_kwargs):
        raise AssertionError("predictor should not run on cache hit")

    monkeypatch.setattr(core, "_predict_cds_sequences", _unexpected)
    second = core._load_or_build_sample_cds_hashes(
        sample,
        cache_root=tmp_path,
        cds_prediction_mode="single",
        cds_training_file=None,
        cds_closed_ends=False,
    )

    assert first == second
    cache_dir = tmp_path / "_sample_cds_hashes"
    assert any(cache_dir.glob("*.json"))


def test_low_confidence_loci_uses_evidence_not_missing_threshold() -> None:
    calls = {
        "a": core.LocusCall(
            locus="a",
            allele_id="1",
            call_type="exact",
            confidence=1.0,
            best_match=AlleleMatch(
                locus="a",
                allele_id="1",
                identity=100.0,
                coverage=1.0,
                score=100.0,
            ),
        ),
        "b": core.LocusCall(
            locus="b",
            allele_id="2",
            call_type="closest",
            confidence=0.96,
            best_match=AlleleMatch(
                locus="b",
                allele_id="2",
                identity=97.0,
                coverage=0.99,
                score=96.03,
            ),
        ),
        "c": core.LocusCall(
            locus="c",
            allele_id=None,
            call_type="missing",
            confidence=0.0,
        ),
    }

    low_conf = core._low_confidence_loci(calls)
    assert low_conf == {"b", "c"}


def test_merge_fallback_calls_prefers_better_call_rank() -> None:
    base = {
        "a": core.LocusCall(
            locus="a",
            allele_id="2",
            call_type="closest",
            confidence=0.96,
            best_match=AlleleMatch(
                locus="a",
                allele_id="2",
                identity=97.0,
                coverage=0.99,
                score=96.03,
            ),
        )
    }
    fallback = {
        "a": core.LocusCall(
            locus="a",
            allele_id="1",
            call_type="exact",
            confidence=1.0,
            best_match=AlleleMatch(
                locus="a",
                allele_id="1",
                identity=100.0,
                coverage=1.0,
                score=100.0,
            ),
        )
    }

    core._merge_fallback_calls(base, fallback)
    assert base["a"].allele_id == "1"
    assert base["a"].call_type == "exact"


def test_ultrafast_confirmation_rank_prioritizes_partial_calls() -> None:
    partial_call = core.LocusCall(
        locus="a",
        allele_id="1",
        call_type="partial",
        confidence=0.8,
        best_match=AlleleMatch(
            locus="a",
            allele_id="1",
            identity=99.0,
            coverage=0.92,
            score=91.08,
        ),
    )
    missing_call = core.LocusCall(
        locus="b",
        allele_id=None,
        call_type="missing",
        confidence=0.0,
    )

    assert core._ultrafast_confirmation_rank(
        partial_call
    ) < core._ultrafast_confirmation_rank(missing_call)


def test_ultrafast_second_pass_rank_prioritizes_high_identity_partial() -> None:
    better_partial = core.LocusCall(
        locus="a",
        allele_id="1",
        call_type="partial",
        confidence=0.7,
        best_match=AlleleMatch(
            locus="a",
            allele_id="1",
            identity=99.5,
            coverage=0.94,
            score=93.53,
        ),
    )
    weaker_partial = core.LocusCall(
        locus="b",
        allele_id="2",
        call_type="partial",
        confidence=0.8,
        best_match=AlleleMatch(
            locus="b",
            allele_id="2",
            identity=97.0,
            coverage=0.96,
            score=93.12,
        ),
    )

    assert core._ultrafast_second_pass_rank(
        better_partial
    ) < core._ultrafast_second_pass_rank(weaker_partial)


def test_adaptive_ultrafast_second_pass_budget_scales_with_candidates() -> None:
    calls = {
        f"locus_{i}": core.LocusCall(
            locus=f"locus_{i}",
            allele_id="1",
            call_type="partial",
            confidence=0.8,
        )
        for i in range(150)
    }
    assert core._adaptive_ultrafast_second_pass_budget(calls) == 60


def test_representative_alleles_selects_one_per_locus() -> None:
    alleles = {
        ("a", "2"): "AAAA",
        ("a", "1"): "AAAT",
        ("b", "x"): "CCCC",
        ("b", "10"): "CCCT",
    }
    reps = core._representative_alleles(alleles)

    assert set(reps) == {("a", "1"), ("b", "10")}


def test_select_candidate_locus_fastas_filters_by_locus(tmp_path: Path) -> None:
    a = tmp_path / "a.tfa"
    b = tmp_path / "b.tfa"
    a.write_text(">a_1\nAAAA\n")
    b.write_text(">b_1\nCCCC\n")

    selected = core._select_candidate_locus_fastas(
        {"a": a, "b": b},
        {"b"},
    )

    assert selected == [b]


def test_load_representative_allele_sequences_selects_lowest_allele_id(
    tmp_path: Path,
) -> None:
    a = tmp_path / "a.tfa"
    a.write_text(">a_10\nAAAA\n>a_2\nAAAT\n>a_1\nAAAC\n")
    b = tmp_path / "b.tfa"
    b.write_text(">b_z\nCCCC\n>b_a\nCCCT\n")

    reps = core._load_representative_allele_sequences({"a": a, "b": b})

    assert reps[("a", "1")] == "AAAC"
    assert reps[("b", "a")] == "CCCT"
    assert len(reps) == 2


def test_run_typing_minimap2_hash_refinement_uses_missing_loci_only(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    a = tmp_path / "a.tfa"
    a.write_text(">a_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    b = tmp_path / "b.tfa"
    b.write_text(">b_1\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC\n")

    class DummyScheme:
        name = "dummy"
        loci = ["a", "b"]
        allele_files = {"a": a, "b": b}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, list[str]] = {"merged": []}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, _allele_fastas, index_dir):
            return index_dir

        def align(self, _sample_path, index_path, _loci, _input_type):
            merged = (index_path / "alleles.fasta").read_text()
            captured["merged"].append(merged)

            class _Aln:
                runtime_seconds = 0.1
                matches = []
                sample_id = "s1"
                backend = "minimap2"

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    class _Call:
        def __init__(self, call_type: str):
            self.call_type = call_type

    call_count = {"value": 0}

    def fake_call_all_loci(*_args, **_kwargs):
        call_count["value"] += 1
        if call_count["value"] == 1:
            return {"a": _Call("exact"), "b": _Call("missing")}
        return {"a": _Call("exact"), "b": _Call("exact")}

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", fake_call_all_loci)
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))
    monkeypatch.setenv("GMLST_CGMLST_MINIMAP2_HASH_PREFILTER", "1")
    monkeypatch.setenv("GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI", "10")
    monkeypatch.setattr(
        core,
        "_minimap2_representative_prefilter_candidates",
        lambda **_: ({"a": [("1", 9.0)]}, None),
    )

    results = core.run_typing(
        [sample],
        "dummy",
        "minimap2",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=1,
        prefilter_min_loci_fraction=0.1,
    )

    assert len(results) == 1
    merged = captured["merged"]
    assert len(merged) == 2
    assert ">a_1" in merged[0]
    assert ">b_1" not in merged[0]
    assert ">b_1" in merged[1]
    assert ">a_1" not in merged[1]


def test_run_typing_exact_hash_prefilter_skips_resolved_loci(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    a = tmp_path / "a.tfa"
    a.write_text(">a_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")
    b = tmp_path / "b.tfa"
    b.write_text(">b_1\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC\n")

    class DummyScheme:
        name = "dummy"
        loci = ["a", "b"]
        allele_files = {"a": a, "b": b}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, object] = {}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, _allele_fastas, index_dir):
            return index_dir

        def align(self, _sample_path, _index_path, loci, _input_type):
            captured["loci"] = list(loci)

            class _Aln:
                runtime_seconds = 0.1
                matches = []
                sample_id = "s1"
                backend = "minimap2"

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(
        core,
        "_resolve_exact_cds_matches",
        lambda *_a, **_k: {
            "a": AlleleMatch(
                locus="a", allele_id="1", identity=100.0, coverage=1.0, score=100.0
            )
        },
    )
    monkeypatch.setenv("GMLST_CGMLST_EXACT_HASH_PREFILTER", "1")

    results = core.run_typing(
        [sample],
        "dummy",
        "minimap2",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=1,
        prefilter_enabled=False,
    )

    assert len(results) == 1
    assert captured["loci"] == ["b"]


def test_run_typing_cgmlst_prefilter_fallback_reuses_full_index(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    a = tmp_path / "a.tfa"
    a.write_text(">a_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    class DummyScheme:
        name = "dummy"
        loci = ["a"]
        allele_files = {"a": a}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, object] = {"index_dirs": []}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, _allele_fastas, index_dir):
            index_dirs = captured["index_dirs"]
            assert isinstance(index_dirs, list)
            index_dirs.append(str(index_dir))
            return index_dir

        def align(self, _sample_path, _index_path, _loci, _input_type):
            class _Aln:
                runtime_seconds = 0.1

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))
    monkeypatch.setattr(core, "prefilter_assembly_candidates", lambda **_: {})

    results = core.run_typing(
        [sample],
        "dummy",
        "blastn",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=1,
    )

    assert len(results) == 1
    index_dirs = captured["index_dirs"]
    assert isinstance(index_dirs, list)
    assert index_dirs == [str(tmp_path / "idx")]


def test_run_typing_cgmlst_kma_skips_prefilter_and_uses_full_index(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">contig1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    a = tmp_path / "a.tfa"
    a.write_text(">a_1\nATGCGTACGTTAGCTAGCTAATGCGTACGTTAGCTA\n")

    class DummyScheme:
        name = "dummy"
        loci = ["a"]
        allele_files = {"a": a}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
            assert scheme_type == "cgmlst"
            return DummyScheme()

        def index_dir(self, _scheme_name, _backend, provider):
            out = tmp_path / "idx"
            out.mkdir(exist_ok=True)
            return out

    captured: dict[str, object] = {"index_dirs": []}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            return None

        def index(self, _allele_fastas, index_dir):
            index_dirs = captured["index_dirs"]
            assert isinstance(index_dirs, list)
            index_dirs.append(str(index_dir))
            return index_dir

        def align(self, _sample_path, _index_path, _loci, _input_type):
            class _Aln:
                runtime_seconds = 0.1

                @staticmethod
                def matches_for(_locus):
                    return []

            return _Aln()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", lambda *_a, **_k: DummyAligner())
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))

    def fail_prefilter(**_kwargs):
        raise AssertionError("prefilter should be skipped for kma backend")

    monkeypatch.setattr(core, "prefilter_assembly_candidates", fail_prefilter)

    results = core.run_typing(
        [sample],
        "dummy",
        "kma",
        provider="pubmlst",
        scheme_type="cgmlst",
        threads=1,
    )

    assert len(results) == 1
    index_dirs = captured["index_dirs"]
    assert isinstance(index_dirs, list)
    assert index_dirs == [str(tmp_path / "idx")]


def test_is_index_stale_true_when_alleles_newer(tmp_path: Path) -> None:
    allele = tmp_path / "a.tfa"
    allele.write_text(">a_1\nATGC\n")

    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    index_file = index_dir / "alleles.fasta"
    index_file.write_text(">a_1\nATGC\n")
    mmi = index_dir / "alleles.asm20.mmi"
    mmi.write_text("dummy")

    old = time.time() - 100
    index_file.touch()
    mmi.touch()
    index_file_mtime = old
    mmi_mtime = old
    index_file.touch()
    mmi.touch()
    import os

    os.utime(index_file, (index_file_mtime, index_file_mtime))
    os.utime(mmi, (mmi_mtime, mmi_mtime))

    assert core._is_index_stale(
        backend="minimap2",
        index_dir=index_dir,
        allele_fastas=[allele],
    )


def test_ensure_full_index_rebuilds_when_stale(tmp_path: Path) -> None:
    allele = tmp_path / "a.tfa"
    allele.write_text(">a_1\nATGC\n")

    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    stale_mmi = index_dir / "alleles.asm20.mmi"
    stale_mmi.write_text("dummy")

    old = time.time() - 100
    import os

    os.utime(stale_mmi, (old, old))

    calls = {"count": 0}

    class DummyAligner:
        def index(self, allele_fastas, out_dir):
            calls["count"] += 1
            (out_dir / "alleles.fasta").write_text("merged")
            (out_dir / "alleles.asm20.mmi").write_text("mmi")
            return out_dir

    out = core._ensure_full_index(
        aligner=DummyAligner(),
        backend="minimap2",
        scheme_name="dummy",
        allele_fastas=[allele],
        index_dir=index_dir,
        force_reindex=False,
    )

    assert out == index_dir
    assert calls["count"] == 1


def test_ensure_full_index_purges_stale_minimap2_artifacts_before_rebuild(
    tmp_path: Path,
) -> None:
    allele = tmp_path / "a.tfa"
    allele.write_text(">a_1\nATGC\n")

    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    stale_merged = index_dir / "alleles.fasta"
    stale_merged.write_text("stale")
    stale_mmi = index_dir / "alleles.asm20.mmi"
    stale_mmi.write_text("stale")

    old = time.time() - 100
    import os

    os.utime(stale_merged, (old, old))
    os.utime(stale_mmi, (old, old))

    calls = {"count": 0}

    class DummyAligner:
        def index(self, _allele_fastas, out_dir):
            calls["count"] += 1
            assert not (out_dir / "alleles.asm20.mmi").exists()
            assert not (out_dir / "alleles.fasta").exists()
            (out_dir / "alleles.fasta").write_text("merged")
            (out_dir / "alleles.asm20.mmi").write_text("mmi")
            return out_dir

    out = core._ensure_full_index(
        aligner=DummyAligner(),
        backend="minimap2",
        scheme_name="dummy",
        allele_fastas=[allele],
        index_dir=index_dir,
        force_reindex=False,
    )

    assert out == index_dir
    assert calls["count"] == 1


def test_is_index_stale_true_when_merged_fasta_size_mismatch(tmp_path: Path) -> None:
    allele = tmp_path / "a.tfa"
    allele.write_text(">a_1\nATGC\n")

    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    merged = index_dir / "alleles.fasta"
    merged.write_text(">a_1\nATG\n")
    mmi = index_dir / "alleles.asm20.mmi"
    mmi.write_text("dummy")

    assert core._is_index_stale(
        backend="minimap2",
        index_dir=index_dir,
        allele_fastas=[allele],
    )


def test_is_index_stale_true_when_kma_index_artifact_is_empty(tmp_path: Path) -> None:
    allele = tmp_path / "a.tfa"
    allele.write_text(">a_1\nATGC\n")

    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "alleles.fasta").write_text("merged")
    (index_dir / "kma_db.name").write_text("names")
    (index_dir / "kma_db.seq.b").write_text("seq")
    (index_dir / "kma_db.comp.b").write_text("comp")
    (index_dir / "kma_db.length.b").write_text("")

    assert core._is_index_stale(
        backend="kma",
        index_dir=index_dir,
        allele_fastas=[allele],
    )


def test_apply_post_alignment_refinements_noop_keeps_calls(monkeypatch) -> None:
    locus_calls = {
        "abc": LocusCall(
            locus="abc",
            allele_id="1",
            call_type="exact",
            confidence=1.0,
        )
    }
    sample = SampleInput(sample_id="s1", path=Path("/tmp/s1.fna"), input_type="fasta")

    class DummyScheme:
        loci = ["abc"]
        allele_files = {"abc": Path("/tmp/abc.tfa")}

    class DummyCache:
        def index_dir(self, _scheme_name, _backend, provider):
            return Path("/tmp")

    def fail_align_targeted(**_kwargs):
        raise AssertionError("_align_targeted_loci should not be called")

    monkeypatch.setattr(core, "_align_targeted_loci", fail_align_targeted)

    result = core._apply_post_alignment_refinements(
        locus_calls=locus_calls,
        aln=AlignmentResult(sample_id="s1", backend="blastn"),
        aligner=object(),
        sample=sample,
        sample_source=sample.path,
        scheme=DummyScheme(),
        mode_overrides=core.CgmlstModeOverrides(
            protein_exact_hash_prefilter=False,
            exact_hash_prefilter=False,
            minimap2_hash_prefilter=False,
            minimap2_hash_locus_top_n=None,
            minimap2_hash_refine_max_loci=None,
            minimap2_fasta_emit_cigar=None,
            minimap2_fasta_speed_profile=None,
            minimap2_representative_main_alignment=None,
            minimap2_bsr_confirm_max_loci=None,
            minimap2_ultrafast_second_pass_max_loci=None,
            evidence_fallback_backend=None,
            evidence_fallback_max_loci=None,
        ),
        use_minimap2_hash_prefilter=False,
        scheme_type="mlst",
        backend="blastn",
        kma_fastq_mem_mode=False,
        threads=1,
        count_same_copy=False,
        min_identity=95.0,
        min_coverage=0.95,
        effective_min_depth=10.0,
        minimap2_representative_main_alignment=False,
        ultrafast_second_pass_max_loci=0,
        cache=DummyCache(),
        scheme_name="dummy",
        provider="pubmlst",
        allele_fastas=[Path("/tmp/abc.tfa")],
        force_reindex=False,
    )

    assert result is locus_calls
    assert result["abc"].call_type == "exact"


def test_apply_post_alignment_refinements_minimap2_refine_path(monkeypatch) -> None:
    locus_calls = {
        "abc": LocusCall(
            locus="abc",
            allele_id=None,
            call_type="missing",
            confidence=0.0,
        )
    }
    sample = SampleInput(sample_id="s1", path=Path("/tmp/s1.fna"), input_type="fasta")

    class DummyScheme:
        loci = ["abc"]
        allele_files = {"abc": Path("/tmp/abc.tfa")}

    class DummyCache:
        def index_dir(self, _scheme_name, _backend, provider):
            return Path("/tmp")

    captured: dict[str, object] = {}

    def fake_align_targeted(**kwargs):
        captured["temp_prefix"] = kwargs["temp_prefix"]
        return AlignmentResult(sample_id="s1", backend="minimap2", matches=[]), 0.01

    def fake_call_all_loci(_aln, _loci, **_thresholds):
        return {
            "abc": LocusCall(
                locus="abc",
                allele_id="2",
                call_type="closest",
                confidence=0.9,
            )
        }

    monkeypatch.setattr(core, "_align_targeted_loci", fake_align_targeted)
    monkeypatch.setattr(core, "call_all_loci", fake_call_all_loci)

    result = core._apply_post_alignment_refinements(
        locus_calls=locus_calls,
        aln=AlignmentResult(sample_id="s1", backend="minimap2"),
        aligner=object(),
        sample=sample,
        sample_source=sample.path,
        scheme=DummyScheme(),
        mode_overrides=core.CgmlstModeOverrides(
            protein_exact_hash_prefilter=False,
            exact_hash_prefilter=False,
            minimap2_hash_prefilter=True,
            minimap2_hash_locus_top_n=None,
            minimap2_hash_refine_max_loci=5,
            minimap2_fasta_emit_cigar=None,
            minimap2_fasta_speed_profile=None,
            minimap2_representative_main_alignment=None,
            minimap2_bsr_confirm_max_loci=None,
            minimap2_ultrafast_second_pass_max_loci=None,
            evidence_fallback_backend="none",
            evidence_fallback_max_loci=0,
        ),
        use_minimap2_hash_prefilter=True,
        scheme_type="cgmlst",
        backend="minimap2",
        kma_fastq_mem_mode=False,
        threads=1,
        count_same_copy=False,
        min_identity=95.0,
        min_coverage=0.95,
        effective_min_depth=0.0,
        minimap2_representative_main_alignment=False,
        ultrafast_second_pass_max_loci=0,
        cache=DummyCache(),
        scheme_name="dummy",
        provider="pubmlst",
        allele_fastas=[Path("/tmp/abc.tfa")],
        force_reindex=False,
    )

    assert captured["temp_prefix"] == "gmlst_refine_"
    assert result["abc"].call_type == "closest"
    assert result["abc"].allele_id == "2"


def test_merge_calls_from_alignment_updates_base_calls(monkeypatch) -> None:
    base_calls = {
        "abc": LocusCall(
            locus="abc",
            allele_id=None,
            call_type="missing",
            confidence=0.0,
        )
    }

    def fake_call_all_loci(_aln, _loci, **_thresholds):
        return {
            "abc": LocusCall(
                locus="abc",
                allele_id="3",
                call_type="closest",
                confidence=0.95,
            )
        }

    monkeypatch.setattr(core, "call_all_loci", fake_call_all_loci)

    core._merge_calls_from_alignment(
        base_calls=base_calls,
        alignment=AlignmentResult(sample_id="s1", backend="minimap2"),
        loci=["abc"],
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=0.0,
    )

    assert base_calls["abc"].allele_id == "3"
    assert base_calls["abc"].call_type == "closest"


def test_recompute_all_loci_with_additional_alignment(monkeypatch) -> None:
    calls = {
        "abc": LocusCall(
            locus="abc",
            allele_id="7",
            call_type="closest",
            confidence=0.9,
        )
    }

    def fake_call_all_loci(_aln, _loci, **_thresholds):
        return calls

    monkeypatch.setattr(core, "call_all_loci", fake_call_all_loci)

    result = core._recompute_all_loci_with_additional_alignment(
        base_alignment=AlignmentResult(
            sample_id="s1",
            backend="minimap2",
            matches=[],
        ),
        additional_alignment=AlignmentResult(
            sample_id="s1",
            backend="minimap2",
            matches=[],
        ),
        all_loci=["abc"],
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=0.0,
    )

    assert result["abc"].allele_id == "7"
    assert result["abc"].call_type == "closest"


def test_confirm_loci_with_tuned_aligner_merges_calls(monkeypatch) -> None:
    sample = SampleInput(sample_id="s1", path=Path("/tmp/s1.fna"), input_type="fasta")
    base_calls = {
        "abc": LocusCall(
            locus="abc",
            allele_id=None,
            call_type="missing",
            confidence=0.0,
        )
    }
    captured: dict[str, object] = {}

    class DummyAligner:
        supports_fastq = True

        def check_dependencies(self):
            captured["checked"] = True

    def fake_get_aligner(backend: str, **kwargs):
        captured["backend"] = backend
        captured["kwargs"] = kwargs
        return DummyAligner()

    def fake_align_targeted(**kwargs):
        captured["temp_prefix"] = kwargs["temp_prefix"]
        captured["loci"] = kwargs["loci"]
        return AlignmentResult(sample_id="s1", backend="minimap2", matches=[]), 0.03

    def fake_merge_calls(**kwargs):
        captured["merge_loci"] = kwargs["loci"]
        captured["min_depth"] = kwargs["min_depth"]

    monkeypatch.setattr(core, "get_aligner", fake_get_aligner)
    monkeypatch.setattr(core, "_align_targeted_loci", fake_align_targeted)
    monkeypatch.setattr(core, "_merge_calls_from_alignment", fake_merge_calls)

    core._confirm_loci_with_tuned_aligner(
        base_calls=base_calls,
        backend="minimap2",
        aligner_kwargs={
            "threads": 4,
            "count_same_copy": True,
            "fasta_emit_cigar": True,
        },
        sample=sample,
        sample_source=sample.path,
        candidate_loci=["abc"],
        allele_files={"abc": Path("/tmp/abc.tfa")},
        temp_prefix="gmlst_confirm_",
        log_template="Confirmation in %.3fs for %s (%d loci)",
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=0.0,
    )

    assert captured["backend"] == "minimap2"
    assert captured["kwargs"] == {
        "threads": 4,
        "count_same_copy": True,
        "fasta_emit_cigar": True,
    }
    assert captured["checked"] is True
    assert captured["temp_prefix"] == "gmlst_confirm_"
    assert captured["loci"] == ["abc"]
    assert captured["merge_loci"] == ["abc"]
    assert captured["min_depth"] == 0.0


def test_confirm_loci_with_tuned_aligner_skips_when_no_targeted_fastas(
    monkeypatch,
) -> None:
    sample = SampleInput(sample_id="s1", path=Path("/tmp/s1.fna"), input_type="fasta")
    base_calls = {
        "abc": LocusCall(
            locus="abc",
            allele_id=None,
            call_type="missing",
            confidence=0.0,
        )
    }

    def fail_get_aligner(*_args, **_kwargs):
        raise AssertionError("get_aligner should not be called")

    monkeypatch.setattr(core, "get_aligner", fail_get_aligner)

    core._confirm_loci_with_tuned_aligner(
        base_calls=base_calls,
        backend="minimap2",
        aligner_kwargs={
            "threads": 1,
            "count_same_copy": False,
        },
        sample=sample,
        sample_source=sample.path,
        candidate_loci=["abc"],
        allele_files={},
        temp_prefix="gmlst_confirm_",
        log_template="Confirmation in %.3fs for %s (%d loci)",
        min_identity=95.0,
        min_coverage=0.95,
        min_depth=0.0,
    )


def test_align_evidence_fallback_loci_blastn_uses_targeted_alignment(
    monkeypatch,
) -> None:
    sample = SampleInput(sample_id="s1", path=Path("/tmp/s1.fna"), input_type="fasta")
    captured: dict[str, object] = {}

    class DummyCache:
        def index_dir(self, _scheme_name, _backend, provider):
            return Path("/tmp")

    def fake_align_targeted(**kwargs):
        captured["temp_prefix"] = kwargs["temp_prefix"]
        captured["force_build_index"] = kwargs["force_build_index"]
        captured["loci"] = kwargs["loci"]
        return AlignmentResult(sample_id="s1", backend="blastn", matches=[]), 0.02

    monkeypatch.setattr(core, "_align_targeted_loci", fake_align_targeted)

    result = core._align_evidence_fallback_loci(
        fallback_aligner=object(),
        fallback_backend="blastn",
        sample=sample,
        sample_source=sample.path,
        loci=["abc"],
        scheme_allele_files={"abc": Path("/tmp/abc.tfa")},
        cache=DummyCache(),
        scheme_name="dummy",
        provider="pubmlst",
        allele_fastas=[Path("/tmp/abc.tfa")],
        force_reindex=False,
    )

    assert result is not None
    assert captured["temp_prefix"] == "gmlst_fallback_blastn_"
    assert captured["force_build_index"] is True
    assert captured["loci"] == ["abc"]


def test_align_evidence_fallback_loci_non_blastn_uses_full_index(monkeypatch) -> None:
    sample = SampleInput(sample_id="s1", path=Path("/tmp/s1.fna"), input_type="fasta")
    captured: dict[str, object] = {}

    class DummyCache:
        def index_dir(self, _scheme_name, _backend, provider):
            return Path("/tmp/fallback_idx")

    class DummyAligner:
        def align(self, sample_source, index_path, loci, sample_input_type):
            captured["sample_source"] = sample_source
            captured["index_path"] = index_path
            captured["loci"] = loci
            captured["sample_input_type"] = sample_input_type
            return AlignmentResult(sample_id="s1", backend="kma", matches=[])

    def fake_ensure_full_index(**kwargs):
        captured["ensure_backend"] = kwargs["backend"]
        captured["force_reindex"] = kwargs["force_reindex"]
        return Path("/tmp/fallback_idx")

    monkeypatch.setattr(core, "_ensure_full_index", fake_ensure_full_index)

    result = core._align_evidence_fallback_loci(
        fallback_aligner=DummyAligner(),
        fallback_backend="kma",
        sample=sample,
        sample_source=sample.path,
        loci=["def", "abc"],
        scheme_allele_files={"abc": Path("/tmp/abc.tfa")},
        cache=DummyCache(),
        scheme_name="dummy",
        provider="pubmlst",
        allele_fastas=[Path("/tmp/abc.tfa")],
        force_reindex=True,
    )

    assert result is not None
    assert captured["ensure_backend"] == "kma"
    assert captured["force_reindex"] is True
    assert captured["loci"] == ["abc", "def"]
    assert captured["sample_input_type"] == "fasta"
