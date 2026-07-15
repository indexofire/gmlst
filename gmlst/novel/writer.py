"""Writer for novel alleles and profiles.

Handles generation of:
- {locus}_novel.fasta files
- profiles_novel.txt files
"""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from contextlib import suppress
from pathlib import Path


class NovelAlleleWriter:
    """Write novel alleles to FASTA files.

    Manages per-locus FASTA files with sequential numbering (n1, n2...).
    Handles deduplication based on sequence content.
    """

    def __init__(self, output_dir: Path):
        """Initialize writer.

        Args:
            output_dir: Directory to write {locus}_novel.fasta files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track assigned numbers per locus: {locus: current_max_number}
        self._counters: dict[str, int] = defaultdict(int)

        # Track seen sequences for dedup: {(locus, seq_hash): allele_id}
        self._seen_sequences: dict[tuple[str, str], str] = {}

        # Track samples per allele for header: {allele_id: [samples]}
        self._allele_samples: dict[str, list[str]] = defaultdict(list)

        # Buffer for writing: {locus: [(allele_id, sample, sequence), ...]}
        self._buffer: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

    def add_novel_allele(
        self,
        locus: str,
        sample: str,
        sequence: str,
    ) -> str | None:
        """Add a novel allele.

        Args:
            locus: Locus name (e.g., "dnaN")
            sample: Sample identifier
            sequence: DNA sequence (uppercase, no gaps)

        Returns:
            Assigned allele ID (e.g., "n1", "n2") or None if not novel
        """
        if not sequence:
            return None

        # Normalize sequence
        sequence = sequence.upper().replace("-", "").replace(" ", "")

        # Check for duplicate sequence
        seq_hash = hashlib.md5(sequence.encode()).hexdigest()[:16]
        key = (locus, seq_hash)

        if key in self._seen_sequences:
            # Existing allele, just add sample
            allele_id = self._seen_sequences[key]
            if sample not in self._allele_samples[allele_id]:
                self._allele_samples[allele_id].append(sample)
            return allele_id

        # New allele, assign number
        self._counters[locus] += 1
        allele_id = f"n{self._counters[locus]}"
        full_id = f"{locus}_{allele_id}"

        self._seen_sequences[key] = full_id
        self._allele_samples[full_id].append(sample)
        self._buffer[locus].append((allele_id, sample, sequence))

        return allele_id

    def write(self) -> dict[str, Path]:
        """Write all buffered novel alleles to FASTA files.

        Returns:
            Mapping of locus to written file path
        """
        written_files = {}

        for locus, entries in self._buffer.items():
            if not entries:
                continue

            filepath = self.output_dir / f"{locus}_novel.fasta"

            with open(filepath, "w") as f:
                for allele_id, _sample, sequence in entries:
                    full_id = f"{locus}_{allele_id}"
                    samples = self._allele_samples[full_id]
                    sample_str = " ".join(samples)

                    f.write(f">{full_id} sample={sample_str}\n")
                    # Write sequence in 60-char lines
                    for i in range(0, len(sequence), 60):
                        f.write(sequence[i : i + 60] + "\n")

            written_files[locus] = filepath

        return written_files


class NovelProfileWriter:
    """Write novel ST profiles to TSV file.

    Manages sequential ST numbering (N1, N2...) and ensures
    only complete profiles (all loci resolved) are included.
    """

    def __init__(self, output_dir: Path, loci: list[str]):
        """Initialize writer.

        Args:
            output_dir: Directory to write profiles_novel.txt
            loci: Ordered list of locus names
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.loci = loci

        # Profile counter
        self._st_counter = 0

        # Track seen profiles for dedup: {tuple of allele IDs: ST number}
        self._seen_profiles: dict[tuple[str, ...], str] = {}

        # Buffer: [(st, sample, {locus: allele}), ...]
        self._buffer: list[tuple[str, str, dict[str, str]]] = []

        self._load_existing_profiles()

    def _load_existing_profiles(self) -> None:
        filepath = self.output_dir / "profiles_novel.txt"
        if not filepath.exists():
            return

        with filepath.open() as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                st = str(row.get("ST", "")).strip()
                if st.startswith("N"):
                    # non-numeric novel ST suffix (e.g. "N-") — skip silently
                    with suppress(ValueError):
                        self._st_counter = max(self._st_counter, int(st[1:]))
                profile_key: list[str] = []
                for locus in self.loci:
                    profile_key.append(str(row.get(locus, "-")))
                self._seen_profiles[tuple(profile_key)] = st

    def add_profile(
        self,
        sample: str,
        allele_calls: dict[str, str],
    ) -> str | None:
        """Add a profile.

        Args:
            sample: Sample identifier
            allele_calls: Mapping from locus to allele ID (e.g., "5", "n1")

        Returns:
            Assigned ST (e.g., "N1", "N2") or None if incomplete/invalid
        """
        # Check completeness: all loci must have a value
        profile_key = []
        for locus in self.loci:
            allele = allele_calls.get(locus, "-")
            if allele in ("-", "", None):
                # Missing locus - skip this profile
                return None
            profile_key.append(allele)

        profile_tuple = tuple(profile_key)

        # Check for duplicate profile
        if profile_tuple in self._seen_profiles:
            st = self._seen_profiles[profile_tuple]
            self._buffer.append((st, sample, allele_calls))
            return st

        # New profile, assign ST number
        self._st_counter += 1
        st = f"N{self._st_counter}"
        self._seen_profiles[profile_tuple] = st
        self._buffer.append((st, sample, allele_calls))

        return st

    def write(self) -> Path | None:
        """Write all buffered profiles to TSV file.

        Returns:
            Path to written file or None if no profiles
        """
        if not self._buffer:
            return None

        filepath = self.output_dir / "profiles_novel.txt"

        file_exists = filepath.exists()
        with filepath.open("a") as f:
            if not file_exists:
                header = "ST\tsample\t" + "\t".join(self.loci) + "\n"
                f.write(header)
            for st, sample, allele_calls in self._buffer:
                row = [st, sample]
                for locus in self.loci:
                    row.append(allele_calls.get(locus, "-"))
                f.write("\t".join(row) + "\n")

        return filepath
