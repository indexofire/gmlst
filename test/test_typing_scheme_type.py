from __future__ import annotations

from pathlib import Path

import pytest

import gmlst.commands.typing as typing_cmd


def test_cgmlst_mode_forwards_scheme_type(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">c1\nATCG\n")

    class DummyScheme:
        loci = ["abc"]

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _name, provider, scheme_type="mlst"):
            return DummyScheme()

        def detect_provider(self, _name):
            return "pubmlst"

        def load_catalog(self, _provider):
            return [{"scheme_name": "vparahaemolyticus_3", "scheme_type": "cgmlst"}]

    captured: dict[str, object] = {}

    def fake_run_typing(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(typing_cmd, "DatabaseCache", DummyCache)
    monkeypatch.setattr(typing_cmd, "run_typing", fake_run_typing)

    typing_cmd._run_mlst_like_typing(
        mode="cgmlst",
        samples=(sample,),
        scheme="vparahaemolyticus_3",
        backend="blastn",
        min_id=95.0,
        min_cov=0.95,
        min_depth=10.0,
        fmt="tsv",
        output=None,
        cache_dir=None,
        force_reindex=False,
        no_header=False,
        threads=1,
        count_same_copy=False,
        provider=None,
        novel_allele=False,
        novel_profile=False,
        output_dir=None,
    )

    assert captured["scheme_type"] == "cgmlst"


def test_mlst_mode_rejects_cgmlst_before_ensure(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">c1\nATCG\n")

    calls = {"ensure": 0}

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _name, provider, scheme_type="mlst"):
            calls["ensure"] += 1
            return object()

        def detect_provider(self, _name):
            return "pubmlst"

        def load_catalog(self, _provider):
            return [{"scheme_name": "vparahaemolyticus_3", "scheme_type": "cgmlst"}]

    monkeypatch.setattr(typing_cmd, "DatabaseCache", DummyCache)

    try:
        typing_cmd._run_mlst_like_typing(
            mode="mlst",
            samples=(sample,),
            scheme="vparahaemolyticus_3",
            backend="blastn",
            min_id=95.0,
            min_cov=0.95,
            min_depth=10.0,
            fmt="tsv",
            output=None,
            cache_dir=None,
            force_reindex=False,
            no_header=False,
            threads=1,
            count_same_copy=False,
            provider=None,
            novel_allele=False,
            novel_profile=False,
            output_dir=None,
        )
        raise AssertionError("Expected SystemExit")
    except SystemExit:
        pass

    assert calls["ensure"] == 0


def test_cgmlst_mode_ensure_scheme_uses_resolved_type(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">c1\nATCG\n")

    captured: dict[str, object] = {}

    class DummyScheme:
        loci = ["abc"]

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _name, provider, scheme_type="mlst"):
            captured["ensure_scheme_type"] = scheme_type
            return DummyScheme()

        def detect_provider(self, _name):
            return "pubmlst"

        def load_catalog(self, _provider):
            return [{"scheme_name": "vparahaemolyticus_3", "scheme_type": "cgmlst"}]

    monkeypatch.setattr(typing_cmd, "DatabaseCache", DummyCache)
    monkeypatch.setattr(typing_cmd, "run_typing", lambda **_: [])

    typing_cmd._run_mlst_like_typing(
        mode="cgmlst",
        samples=(sample,),
        scheme="vparahaemolyticus_3",
        backend="blastn",
        min_id=95.0,
        min_cov=0.95,
        min_depth=10.0,
        fmt="tsv",
        output=None,
        cache_dir=None,
        force_reindex=False,
        no_header=False,
        threads=1,
        count_same_copy=False,
        provider=None,
        novel_allele=False,
        novel_profile=False,
        output_dir=None,
    )

    assert captured["ensure_scheme_type"] == "cgmlst"


def test_cgmlst_mode_preserves_resolved_wgmlst_for_runtime(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">c1\nATCG\n")

    captured: dict[str, object] = {}

    class DummyScheme:
        loci = ["abc"]

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _name, provider, scheme_type="mlst"):
            captured["ensure_scheme_type"] = scheme_type
            return DummyScheme()

        def detect_provider(self, _name):
            return "pubmlst"

        def load_catalog(self, _provider):
            return [{"scheme_name": "vparahaemolyticus_3", "scheme_type": "wgmlst"}]

    def fake_run_typing(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(typing_cmd, "DatabaseCache", DummyCache)
    monkeypatch.setattr(typing_cmd, "run_typing", fake_run_typing)

    typing_cmd._run_mlst_like_typing(
        mode="cgmlst",
        samples=(sample,),
        scheme="vparahaemolyticus_3",
        backend="blastn",
        min_id=95.0,
        min_cov=0.95,
        min_depth=10.0,
        fmt="tsv",
        output=None,
        cache_dir=None,
        force_reindex=False,
        no_header=False,
        threads=1,
        count_same_copy=False,
        provider=None,
        novel_allele=False,
        novel_profile=False,
        output_dir=None,
    )

    assert captured["ensure_scheme_type"] == "wgmlst"
    assert captured["scheme_type"] == "wgmlst"


def test_cgmlst_fastq_auto_switches_minimap2_to_kma(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample_R1.fastq"
    sample.write_text("@r1\nACGT\n+\n####\n")

    class DummyScheme:
        loci = ["abc"]

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _name, provider, scheme_type="mlst"):
            return DummyScheme()

        def detect_provider(self, _name):
            return "pubmlst"

        def load_catalog(self, _provider):
            return [{"scheme_name": "vparahaemolyticus_3", "scheme_type": "cgmlst"}]

    captured: dict[str, object] = {}

    def fake_run_typing(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(typing_cmd, "DatabaseCache", DummyCache)
    monkeypatch.setattr(typing_cmd, "run_typing", fake_run_typing)

    typing_cmd._run_mlst_like_typing(
        mode="cgmlst",
        samples=(sample,),
        scheme="vparahaemolyticus_3",
        backend="minimap2",
        min_id=95.0,
        min_cov=0.95,
        min_depth=10.0,
        fmt="tsv",
        output=None,
        cache_dir=None,
        force_reindex=False,
        no_header=False,
        threads=1,
        count_same_copy=False,
        provider=None,
        novel_allele=False,
        novel_profile=False,
        output_dir=None,
        cgmlst_mode="chew-ultrafast",
    )

    assert captured["backend"] == "kma"
    assert captured["cgmlst_mode"] == "standard"
    assert captured["threads"] >= 1


def test_fastq_kma_auto_threads_uses_env_and_cpu(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS", "16")
    monkeypatch.setattr(typing_cmd.os, "cpu_count", lambda: 6)
    assert typing_cmd._fastq_kma_auto_threads() == 6


def test_fastq_kma_auto_threads_can_disable(monkeypatch) -> None:
    monkeypatch.setenv("GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS", "1")
    monkeypatch.setattr(typing_cmd.os, "cpu_count", lambda: 12)
    assert typing_cmd._fastq_kma_auto_threads() == 1


def test_cgmlst_mode_falls_back_to_redetected_provider(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">c1\nATCG\n")

    captured: dict[str, object] = {"ensure_calls": []}

    class DummyScheme:
        loci = ["abc"]

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _name, provider, scheme_type="mlst"):
            captured["ensure_calls"].append((provider, scheme_type))
            if provider == "pubmlst":
                raise RuntimeError("missing from pubmlst")
            return DummyScheme()

        def detect_provider(self, _name):
            return "pubmlst"

        def load_catalog(self, provider):
            if provider == "cgmlst":
                return [
                    {
                        "scheme_name": "vparahaemolyticus_3",
                        "scheme_type": "cgmlst",
                    }
                ]
            return []

    detect_sequence = iter(["pubmlst", "cgmlst"])

    def fake_detect_provider(cache, scheme):
        _ = cache
        _ = scheme
        return next(detect_sequence)

    def fake_run_typing(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(typing_cmd, "DatabaseCache", DummyCache)
    monkeypatch.setattr(typing_cmd, "detect_provider", fake_detect_provider)
    monkeypatch.setattr(typing_cmd, "run_typing", fake_run_typing)

    typing_cmd._run_mlst_like_typing(
        mode="cgmlst",
        samples=(sample,),
        scheme="vparahaemolyticus_3",
        backend="blastn",
        min_id=95.0,
        min_cov=0.95,
        min_depth=10.0,
        fmt="tsv",
        output=None,
        cache_dir=None,
        force_reindex=False,
        no_header=False,
        threads=1,
        count_same_copy=False,
        provider=None,
        novel_allele=False,
        novel_profile=False,
        output_dir=None,
    )

    assert captured["provider"] == "cgmlst"
    assert captured["scheme_type"] == "cgmlst"
    assert captured["ensure_calls"] == [
        ("pubmlst", "cgmlst"),
        ("cgmlst", "cgmlst"),
    ]


def test_cgmlst_rejects_unsupported_call_policy(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.fna"
    sample.write_text(">c1\nATCG\n")

    class DummyCache:
        def __init__(self, _root):
            pass

        def detect_provider(self, _name):
            return "pubmlst"

        def load_catalog(self, _provider):
            return [{"scheme_name": "vparahaemolyticus_3", "scheme_type": "cgmlst"}]

    monkeypatch.setattr(typing_cmd, "DatabaseCache", DummyCache)

    with pytest.raises(SystemExit):
        typing_cmd._run_mlst_like_typing(
            mode="cgmlst",
            samples=(sample,),
            scheme="vparahaemolyticus_3",
            backend="blastn",
            min_id=95.0,
            min_cov=0.95,
            min_depth=10.0,
            fmt="tsv",
            output=None,
            cache_dir=None,
            force_reindex=False,
            no_header=False,
            threads=1,
            count_same_copy=False,
            provider=None,
            novel_allele=False,
            novel_profile=False,
            output_dir=None,
            call_policy="weird-policy",
        )


def test_cgmlst_fastq_kma_forces_standard_mode_without_bumping_explicit_threads(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample_R1.fastq"
    sample.write_text("@r1\nACGT\n+\n####\n")

    class DummyScheme:
        loci = ["abc"]

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _name, provider, scheme_type="mlst"):
            return DummyScheme()

        def detect_provider(self, _name):
            return "pubmlst"

        def load_catalog(self, _provider):
            return [{"scheme_name": "vparahaemolyticus_3", "scheme_type": "cgmlst"}]

    captured: dict[str, object] = {}

    def fake_run_typing(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(typing_cmd, "DatabaseCache", DummyCache)
    monkeypatch.setattr(typing_cmd, "run_typing", fake_run_typing)

    typing_cmd._run_mlst_like_typing(
        mode="cgmlst",
        samples=(sample,),
        scheme="vparahaemolyticus_3",
        backend="kma",
        min_id=95.0,
        min_cov=0.95,
        min_depth=10.0,
        fmt="tsv",
        output=None,
        cache_dir=None,
        force_reindex=False,
        no_header=False,
        threads=4,
        count_same_copy=False,
        provider=None,
        novel_allele=False,
        novel_profile=False,
        output_dir=None,
        cgmlst_mode="chew-fast",
    )

    assert captured["backend"] == "kma"
    assert captured["cgmlst_mode"] == "standard"
    assert captured["threads"] == 4


def test_cgmlst_fastq_kma_with_max_workers_does_not_auto_bump_threads(
    monkeypatch, tmp_path: Path
) -> None:
    sample = tmp_path / "sample_R1.fastq"
    sample.write_text("@r1\nACGT\n+\n####\n")

    class DummyScheme:
        loci = ["abc"]

    class DummyCache:
        def __init__(self, _root):
            pass

        def ensure_scheme(self, _name, provider, scheme_type="mlst"):
            return DummyScheme()

        def detect_provider(self, _name):
            return "pubmlst"

        def load_catalog(self, _provider):
            return [{"scheme_name": "vparahaemolyticus_3", "scheme_type": "cgmlst"}]

    captured: dict[str, object] = {}

    def fake_run_typing(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(typing_cmd, "DatabaseCache", DummyCache)
    monkeypatch.setattr(typing_cmd, "run_typing", fake_run_typing)

    typing_cmd._run_mlst_like_typing(
        mode="cgmlst",
        samples=(sample,),
        scheme="vparahaemolyticus_3",
        backend="kma",
        min_id=95.0,
        min_cov=0.95,
        min_depth=10.0,
        fmt="tsv",
        output=None,
        cache_dir=None,
        force_reindex=False,
        no_header=False,
        threads=1,
        count_same_copy=False,
        provider=None,
        novel_allele=False,
        novel_profile=False,
        output_dir=None,
        max_workers=2,
    )

    assert captured["backend"] == "kma"
    assert captured["threads"] == 1
