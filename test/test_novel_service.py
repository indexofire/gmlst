from __future__ import annotations

from types import SimpleNamespace

from gmlst.novel.service import (
    build_custom_scheme_metadata,
    collect_novel_typing_results,
    create_novel_writers,
    finalize_novel_typing_outputs,
    merge_custom_scheme_update_metadata,
    write_novel_outputs,
)


def test_build_custom_scheme_metadata_tracks_last_allele_numbers() -> None:
    novel_alleles = {
        "dnaN": [SimpleNamespace(allele_id="n1"), SimpleNamespace(allele_id="n2")],
        "gyrB": [SimpleNamespace(allele_id="n1")],
    }
    novel_profiles = [SimpleNamespace(st="N1"), SimpleNamespace(st="N2")]

    meta = build_custom_scheme_metadata(
        custom_name="custom_1",
        scheme_type="mlst",
        source="ecoli_1",
        source_provider="pubmlst",
        description="demo",
        created_at="2026-01-01T00:00:00Z",
        loci=["dnaN", "gyrB"],
        novel_alleles=novel_alleles,
        novel_profiles=novel_profiles,
    )

    assert meta["last_allele_number"] == {"dnaN": 2, "gyrB": 1}
    assert meta["novel_profiles"] == ["N1", "N2"]


def test_merge_custom_scheme_update_metadata_appends_novel_state() -> None:
    meta = {
        "novel_profiles": ["N1"],
        "novel_alleles": {"dnaN": ["n1"]},
        "last_allele_number": {"dnaN": 1},
    }
    updated = merge_custom_scheme_update_metadata(
        meta,
        last_allele_numbers={"dnaN": 2, "gyrB": 1},
        current_st_num=3,
        novel_alleles={
            "dnaN": [SimpleNamespace(allele_id="n2")],
            "gyrB": [SimpleNamespace(allele_id="n1")],
        },
        updated_at="2026-01-02T00:00:00Z",
    )

    assert updated["last_allele_number"] == {"dnaN": 2, "gyrB": 1}
    assert updated["novel_profiles"] == ["N1", "N2", "N3"]
    assert updated["novel_alleles"] == {"dnaN": ["n1", "n2"], "gyrB": ["n1"]}
    assert updated["updated_at"] == "2026-01-02T00:00:00Z"


def test_collect_novel_typing_results_routes_calls_to_writers() -> None:
    allele_writer = SimpleNamespace(calls=[])
    profile_writer = SimpleNamespace(calls=[])
    logger = SimpleNamespace(
        debug=lambda *args, **kwargs: None, info=lambda *args, **kwargs: None
    )

    def _add_novel_allele(**kwargs):
        allele_writer.calls.append(kwargs)
        return "n1"

    def _add_profile(**kwargs):
        profile_writer.calls.append(kwargs)
        return "N1"

    allele_writer.add_novel_allele = _add_novel_allele
    profile_writer.add_profile = _add_profile

    result = SimpleNamespace(
        sample_id="sample1",
        locus_calls={
            "dnaN": SimpleNamespace(
                call_type="novel", novel_sequence="ATGC", allele_id="n1"
            ),
            "gyrB": SimpleNamespace(
                call_type="exact", novel_sequence=None, allele_id="5"
            ),
        },
    )

    collect_novel_typing_results(
        results=[result],
        allele_writer=allele_writer,
        profile_writer=profile_writer,
        logger=logger,
    )

    assert allele_writer.calls == [
        {"locus": "dnaN", "sample": "sample1", "sequence": "ATGC"}
    ]
    assert profile_writer.calls == [
        {"sample": "sample1", "allele_calls": {"dnaN": "n1", "gyrB": "5"}}
    ]


def test_write_novel_outputs_announces_written_and_empty_states() -> None:
    printed: list[str] = []
    console = SimpleNamespace(print=lambda msg: printed.append(msg))

    allele_writer = SimpleNamespace(write=lambda: {"dnaN": "/tmp/dnaN_novel.fasta"})
    profile_writer = SimpleNamespace(write=lambda: None)

    write_novel_outputs(
        allele_writer=allele_writer,
        profile_writer=profile_writer,
        console=console,
    )

    assert printed == [
        "[green]Novel alleles written:[/green]",
        "  dnaN: /tmp/dnaN_novel.fasta",
        "[yellow]No novel profiles detected.[/yellow]",
    ]


def test_create_novel_writers_returns_none_when_disabled() -> None:
    allele_writer, profile_writer = create_novel_writers(
        novel_allele=False,
        novel_profile=False,
        output_dir=None,
        loci=["dnaN"],
        allele_writer_cls=object,
        profile_writer_cls=object,
    )

    assert allele_writer is None
    assert profile_writer is None


def test_finalize_novel_typing_outputs_collects_then_writes() -> None:
    calls: list[str] = []
    logger = SimpleNamespace(
        debug=lambda *args, **kwargs: None, info=lambda *args, **kwargs: None
    )
    console = SimpleNamespace(print=lambda *_args, **_kwargs: None)

    class DummyAlleleWriter:
        def add_novel_allele(self, **kwargs):
            calls.append(f"collect:{kwargs['locus']}")
            return "n1"

        def write(self):
            calls.append("write_alleles")
            return {}

    class DummyProfileWriter:
        def add_profile(self, **kwargs):
            calls.append(f"profile:{kwargs['sample']}")
            return None

        def write(self):
            calls.append("write_profiles")
            return None

    result = SimpleNamespace(
        sample_id="sample1",
        locus_calls={
            "dnaN": SimpleNamespace(
                call_type="novel", novel_sequence="ATGC", allele_id="n1"
            )
        },
    )

    finalize_novel_typing_outputs(
        results=[result],
        allele_writer=DummyAlleleWriter(),
        profile_writer=DummyProfileWriter(),
        logger=logger,
        console=console,
    )

    assert calls == [
        "collect:dnaN",
        "profile:sample1",
        "write_alleles",
        "write_profiles",
    ]
