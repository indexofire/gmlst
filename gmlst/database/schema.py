"""Data structures for MLST schemes, alleles, and ST profiles."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from gmlst.fasta_io import iter_fasta_records
from gmlst.utils import open_text

# ---------------------------------------------------------------------------
# Allele
# ---------------------------------------------------------------------------


@dataclass
class Allele:
    """A single allele sequence for one locus."""

    locus: str
    allele_id: str
    sequence: str

    @property
    def full_id(self) -> str:
        """Composite identifier used in FASTA headers, e.g. ``arcC_1``."""
        return f"{self.locus}_{self.allele_id}"

    @property
    def length(self) -> int:
        return len(self.sequence)


# ---------------------------------------------------------------------------
# Scheme
# ---------------------------------------------------------------------------


@dataclass
class Scheme:
    """One MLST scheme as downloaded from PubMLST.

    Attributes
    ----------
    name:
        Scheme name used internally, e.g. ``"saureus"``.
    loci:
        Ordered list of locus names, e.g. ``["arcC", "aroE", ...]``.
    allele_files:
        Mapping from locus name to its ``.tfa`` FASTA file.
    profile_file:
        TSV file defining ST → allele combination mappings.
    """

    name: str
    loci: list[str]
    allele_files: dict[str, Path]
    profile_file: Path | None = None

    # Lazy-loaded caches
    _alleles: dict[str, list[Allele]] = field(default_factory=dict, repr=False)
    _profiles: dict[tuple[str, ...], int] = field(default_factory=dict, repr=False)
    _profiles_loaded: bool = field(default=False, repr=False)

    # ------------------------------------------------------------------
    # Allele loading
    # ------------------------------------------------------------------

    def load_alleles(self, locus: str) -> list[Allele]:
        """Parse allele FASTA for *locus* and return all alleles."""
        if locus in self._alleles:
            return self._alleles[locus]

        path = self.allele_files.get(locus)
        if path is None:
            raise KeyError(f"Locus '{locus}' not found in scheme '{self.name}'")

        alleles = list(_parse_allele_fasta(path, locus))
        self._alleles[locus] = alleles
        return alleles

    def all_alleles_fasta(self) -> Path:
        """Return a merged FASTA path containing all loci.

        The file is written to the same directory as the allele files the
        first time this method is called.
        """
        from gmlst.fasta_io import merge_fasta_files

        merged = next(iter(self.allele_files.values())).parent / "_all_alleles.fasta"
        if merged.exists():
            return merged
        return merge_fasta_files(list(self.allele_files.values()), merged)

    # ------------------------------------------------------------------
    # ST profile lookup
    # ------------------------------------------------------------------

    def _load_profiles(self) -> None:
        if self._profiles_loaded:
            return
        if self.profile_file is None:
            self._profiles_loaded = True
            return

        with open_text(self.profile_file) as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                st_str = row.get("ST") or row.get("st")
                if st_str is None:
                    continue
                try:
                    st = int(st_str)
                except ValueError:
                    continue
                if any(
                    loc not in row or row.get(loc) in (None, "") for loc in self.loci
                ):
                    continue
                key = tuple(str(row[loc]) for loc in self.loci)
                self._profiles[key] = st
        self._profiles_loaded = True

    def lookup_st(self, allele_ids: dict[str, str]) -> int | None:
        """Return ST for the given allele combination, or ``None`` if novel.

        Parameters
        ----------
        allele_ids:
            Mapping from locus name to called allele ID string.
        """
        self._load_profiles()
        key = tuple(allele_ids.get(loc, "-") for loc in self.loci)
        return self._profiles.get(key)


# ---------------------------------------------------------------------------
# FASTA parsing helper
# ---------------------------------------------------------------------------


def _parse_allele_fasta(path: Path, locus: str) -> list[Allele]:
    """Yield :class:`Allele` objects from a locus ``.tfa`` file."""
    alleles: list[Allele] = []
    for header, sequence in iter_fasta_records(path):
        current_id = header
        for sep in ("_", "-"):
            if sep in header:
                current_id = header.split(sep, 1)[1]
                break
        alleles.append(Allele(locus, current_id, sequence))
    return alleles
