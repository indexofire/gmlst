"""Reader for novel allele and profile data.

Parses {locus}_novel.fasta and profiles_novel.txt files.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from gmlst.utils import open_text


@dataclass
class NovelAllele:
    """A novel allele entry."""

    locus: str
    allele_id: str  # n1, n2, etc.
    sequence: str
    samples: list[str]  # Sample names that have this allele


@dataclass
class NovelProfile:
    """A novel ST profile entry."""

    st: str  # N1, N2, etc.
    sample: str
    allele_calls: dict[str, str]  # locus -> allele (number or nX)


class NovelDataReader:
    """Read novel allele FASTA and profile TSV files."""

    def __init__(self, data_dir: Path):
        """Initialize reader.

        Args:
            data_dir: Directory containing *_novel.fasta and profiles_novel.txt
        """
        self.data_dir = Path(data_dir)

    def read_all(self) -> tuple[dict[str, list[NovelAllele]], list[NovelProfile]]:
        """Read all novel data from directory.

        Returns:
            Tuple of (alleles_by_locus, profiles)
        """
        alleles = self._read_alleles()
        profiles = self._read_profiles()
        return alleles, profiles

    def _read_alleles(self) -> dict[str, list[NovelAllele]]:
        """Read all {locus}_novel.fasta files.

        Returns:
            Mapping from locus to list of NovelAllele
        """
        alleles_by_locus: dict[str, list[NovelAllele]] = defaultdict(list)

        for fasta_file in self.data_dir.glob("*_novel.fasta"):
            # Extract locus name from filename (e.g., "dnaN_novel.fasta" -> "dnaN")
            locus = fasta_file.stem.replace("_novel", "")
            alleles = self._parse_fasta(fasta_file, locus)
            alleles_by_locus[locus].extend(alleles)

        return dict(alleles_by_locus)

    def _parse_fasta(self, fasta_path: Path, locus: str) -> list[NovelAllele]:
        """Parse a single novel FASTA file.

        Args:
            fasta_path: Path to {locus}_novel.fasta
            locus: Locus name

        Returns:
            List of NovelAllele objects
        """
        alleles = []
        current_id = None
        current_samples = []
        current_seq_parts = []

        with open_text(fasta_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(">"):
                    # Save previous entry
                    if current_id is not None:
                        alleles.append(
                            NovelAllele(
                                locus=locus,
                                allele_id=current_id,
                                sequence="".join(current_seq_parts),
                                samples=current_samples,
                            )
                        )

                    # Parse new header: >dnaN_n1 sample=isolate_A isolate_B
                    header = line[1:]
                    full_id, _sep, sample_part = header.partition(" sample=")
                    current_id = full_id.split("_", 1)[1]  # n1

                    # Parse sample info
                    current_samples = sample_part.split() if sample_part else []

                    current_seq_parts = []
                elif line:
                    current_seq_parts.append(line.upper())

            # Save last entry
            if current_id is not None:
                alleles.append(
                    NovelAllele(
                        locus=locus,
                        allele_id=current_id,
                        sequence="".join(current_seq_parts),
                        samples=current_samples,
                    )
                )

        return alleles

    def _read_profiles(self) -> list[NovelProfile]:
        """Read profiles_novel.txt file.

        Returns:
            List of NovelProfile objects
        """
        profiles = []
        profile_file = self.data_dir / "profiles_novel.txt"

        if not profile_file.exists():
            return profiles

        with open(profile_file) as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                st = row.get("ST", "")
                sample = row.get("sample", "")

                # Extract allele calls (all columns except ST and sample)
                allele_calls = {}
                for key, value in row.items():
                    if key not in ("ST", "sample") and value:
                        allele_calls[key] = value

                profiles.append(
                    NovelProfile(
                        st=st,
                        sample=sample,
                        allele_calls=allele_calls,
                    )
                )

        return profiles

    def validate_against_scheme(
        self,
        alleles_by_locus: dict[str, list[NovelAllele]],
        profiles: list[NovelProfile],
        scheme_loci: list[str],
    ) -> list[str]:
        """Validate novel data against a scheme.

        Args:
            alleles_by_locus: Novel alleles by locus
            profiles: Novel profiles
            scheme_loci: Expected loci in the scheme

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check that all profile loci are in scheme
        for profile in profiles:
            for locus in profile.allele_calls:
                if locus not in scheme_loci:
                    errors.append(f"Profile {profile.st} has unknown locus: {locus}")

        # Check that all allele loci are in scheme
        for locus in alleles_by_locus:
            if locus not in scheme_loci:
                errors.append(f"Novel alleles for unknown locus: {locus}")

        return errors
