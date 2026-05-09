"""ST profile lookup and result assembly."""

from __future__ import annotations

from dataclasses import dataclass, field

from gmlst.calling.allele import LocusCall
from gmlst.database.schema import Scheme


def _sort_allele_ids(allele_ids: list[str]) -> list[str]:
    return sorted(
        set(allele_ids),
        key=lambda value: (
            not value.isdigit(),
            int(value) if value.isdigit() else value,
        ),
    )


@dataclass
class STResult:
    """Final MLST typing result for one sample."""

    sample_id: str
    scheme: str
    st: int | None
    """Called ST number, or ``None`` if novel / incomplete."""

    locus_calls: dict[str, LocusCall] = field(default_factory=dict)
    """Per-locus call details."""

    backend: str = ""
    runtime_seconds: float = 0.0
    scheme_version: str = ""
    """Date or checksum tag from the downloaded scheme."""

    call_policy: str = "default"
    chew_style_calls: dict[str, str] = field(default_factory=dict)

    @property
    def is_novel(self) -> bool:
        """True if any locus has a non-exact call."""
        return any(c.call_type != "exact" for c in self.locus_calls.values())

    @property
    def is_complete(self) -> bool:
        """True if every locus was called (no missing)."""
        return all(
            c.call_type not in ("missing", "partial") for c in self.locus_calls.values()
        )

    @property
    def has_conflicting_multicopy(self) -> bool:
        return any(call.multiple_hits for call in self.locus_calls.values())

    def allele_ids(self) -> dict[str, str]:
        """Return ``{locus: allele_id}`` for all loci.  Missing → ``"-"``."""
        return {
            locus: (call.allele_id or "-") for locus, call in self.locus_calls.items()
        }

    def format_tsv_row(
        self,
        loci: list[str],
        *,
        include_scheme: bool = True,
        count_same_copy: bool = False,
        call_policy: str = "default",
    ) -> str:
        st_str = (
            "-"
            if self.has_conflicting_multicopy or self.is_novel
            else str(self.st)
            if self.st is not None
            else "-"
        )

        allele_parts: list[str] = []
        for locus in loci:
            if call_policy == "chewbbaca":
                chew_value = self.chew_style_calls.get(locus)
                if chew_value is not None:
                    allele_parts.append(chew_value)
                    continue
            call = self.locus_calls.get(locus)
            if call is None or call.allele_id is None:
                allele_parts.append("-")
            elif call.multiple_hits and call.allele_ids:
                allele_parts.append(",".join(_sort_allele_ids(call.allele_ids)))
            elif count_same_copy and call.call_type == "exact" and call.copy_count > 1:
                allele_parts.append(",".join([call.allele_id] * call.copy_count))
            elif call.call_type == "exact":
                allele_parts.append(call.allele_id)
            elif call.call_type == "closest":
                allele_parts.append(f"~{call.allele_id}")
            elif call.call_type == "partial":
                allele_parts.append(f"{call.allele_id}?")
            elif call.call_type == "novel":
                allele_parts.append(f"~{call.allele_id}")
            else:
                allele_parts.append("-")

        cols = [self.sample_id, st_str] + allele_parts
        if include_scheme:
            cols = [self.sample_id, self.scheme, st_str] + allele_parts
        return "\t".join(cols)

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "sample_id": self.sample_id,
            "scheme": self.scheme,
            "st": self.st,
            "allele_calls": {
                locus: {
                    "allele_id": call.allele_id,
                    "call_type": call.call_type,
                    "allele_ids": call.allele_ids,
                    "multiple_hits": call.multiple_hits,
                    "copy_count": call.copy_count,
                    "novel_sequence": call.novel_sequence,
                    "identity": call.best_match.identity if call.best_match else None,
                    "coverage": call.best_match.coverage if call.best_match else None,
                    "strand": call.best_match.strand if call.best_match else None,
                    "query_contig": call.best_match.query_contig
                    if call.best_match
                    else None,
                    "query_contig_length": (
                        call.best_match.query_contig_length if call.best_match else None
                    ),
                    "query_start": call.best_match.query_start
                    if call.best_match
                    else None,
                    "query_end": call.best_match.query_end if call.best_match else None,
                    "allele_length": (
                        call.best_match.allele_length if call.best_match else None
                    ),
                    "allele_start": call.best_match.allele_start
                    if call.best_match
                    else None,
                    "allele_end": call.best_match.allele_end
                    if call.best_match
                    else None,
                }
                for locus, call in self.locus_calls.items()
            },
            "is_novel": self.is_novel,
            "is_complete": self.is_complete,
            "has_conflicting_multicopy": self.has_conflicting_multicopy,
            "backend": self.backend,
            "runtime_seconds": self.runtime_seconds,
            "call_policy": self.call_policy,
            "chew_style_calls": self.chew_style_calls,
        }


def lookup_st(
    sample_id: str,
    scheme: Scheme,
    locus_calls: dict[str, LocusCall],
    *,
    backend: str = "",
    runtime_seconds: float = 0.0,
    call_policy: str = "default",
    chew_style_calls: dict[str, str] | None = None,
) -> STResult:
    """Perform ST lookup and assemble a complete :class:`STResult`.

    Parameters
    ----------
    sample_id:
        Sample identifier.
    scheme:
        Loaded MLST scheme (provides :meth:`~Scheme.lookup_st`).
    locus_calls:
        Per-locus calls from :func:`~gmlst.calling.allele.call_all_loci`.
    backend:
        Name of the aligner backend used.
    runtime_seconds:
        Wall-clock time for the alignment step.
    """
    allele_ids = {locus: (call.allele_id or "-") for locus, call in locus_calls.items()}

    if any(call.multiple_hits for call in locus_calls.values()):
        st = None
    else:
        st = scheme.lookup_st(allele_ids)

    return STResult(
        sample_id=sample_id,
        scheme=scheme.name,
        st=st,
        locus_calls=locus_calls,
        backend=backend,
        runtime_seconds=runtime_seconds,
        call_policy=call_policy,
        chew_style_calls=chew_style_calls or {},
    )
