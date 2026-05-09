from __future__ import annotations

from pathlib import Path


def test_commands_doc_matches_typing_option_surface() -> None:
    doc = Path("docs/commands.md").read_text()
    marker = "`mlst` and `cgmlst` common options:"
    assert marker in doc
    typing_options = doc.split(marker, maxsplit=1)[1].split(
        "`tgmlst` options", maxsplit=1
    )[0]

    assert "`-p, --provider TEXT`" not in typing_options
    assert "--prefilter-k" in typing_options
    assert "--prefilter-top-n" in typing_options
    assert "--prefilter-min-loci-fraction" in typing_options
