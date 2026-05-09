from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gmlst.core as core


@dataclass
class _DummyResult:
    sample_id: str


def test_run_typing_forwards_threads_to_get_aligner(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "s1.fna"
    sample.write_text(">c1\nATCG\n")

    allele_file = tmp_path / "abc.tfa"
    allele_file.write_text(">abc_1\nATCG\n")

    class DummyScheme:
        name = "dummy"
        loci = ["abc"]
        allele_files = {"abc": allele_file}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _scheme_name, provider, scheme_type):
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

            return _Aln()

    captured = {"threads": None}

    def fake_get_aligner(_backend, **kwargs):
        captured["threads"] = kwargs.get("threads")
        return DummyAligner()

    class DummySample:
        sample_id = "s1"
        input_type = "fasta"
        path = sample
        mate_path = None

    monkeypatch.setattr(core, "DatabaseCache", DummyCache)
    monkeypatch.setattr(core, "get_aligner", fake_get_aligner)
    monkeypatch.setattr(core, "detect_sample", lambda _p: DummySample())
    monkeypatch.setattr(core, "call_all_loci", lambda *_a, **_k: {})
    monkeypatch.setattr(core, "lookup_st", lambda *args, **kwargs: _DummyResult("s1"))

    results = core.run_typing(
        [sample],
        "dummy",
        "blastn",
        provider="pubmlst",
        threads=16,
    )

    assert len(results) == 1
    assert captured["threads"] == 16
