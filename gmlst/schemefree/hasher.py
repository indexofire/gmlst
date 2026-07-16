"""Hash strategies for allele identification.

This module provides multiple hashing strategies with different trade-offs
between speed and accuracy.
"""

from __future__ import annotations

import hashlib
import random
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class HashStrategy(ABC):
    """Abstract base class for allele hashing strategies."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize strategy with configuration."""
        self.config = config or {}
        self.allele_db: dict[str | int, dict] = {}  # hash -> allele info
        self.total_sequences = 0
        self._locus_allele_numbers: dict[str, dict[str | int, int]] = {}

    @abstractmethod
    def get_allele_id(self, sequence: str, locus_id: str) -> str:
        """Get or create allele ID for a sequence.

        Args:
            sequence: DNA sequence
            locus_id: Locus identifier (e.g., "locus_1")

        Returns:
            Allele ID (e.g., "locus_1_42")
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return strategy name."""
        pass

    def _normalize_sequence(self, sequence: str) -> str:
        """Normalize sequence for hashing.

        - Convert to uppercase
        - Remove gaps and spaces
        - Remove ambiguous bases (optional)
        """
        clean = sequence.upper().replace("-", "").replace(" ", "").replace("\n", "")
        # Optionally remove other characters
        return clean

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about processed sequences."""
        return {
            "total_sequences": self.total_sequences,
            "unique_alleles": len(self.allele_db),
            "strategy": self.get_strategy_name(),
        }

    def _format_locus_allele(self, locus_id: str, sequence_key: str | int) -> str:
        locus_map = self._locus_allele_numbers.setdefault(locus_id, {})
        if sequence_key not in locus_map:
            locus_map[sequence_key] = len(locus_map) + 1
        return f"{locus_id}_{locus_map[sequence_key]}"


class SafeHashStrategy(HashStrategy):
    """Safe strategy: MD5 + 1% verification.

    Recommended default. Good balance of speed and accuracy.
    Collision probability: < 10^-25
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.verification_rate = self.config.get("verification_rate", 0.01)
        self.sample_length = self.config.get("sample_length", 100)
        self.use_length_check = self.config.get("use_length_check", True)
        self.use_prefix_check = self.config.get("use_prefix_check", True)
        self.prefix_length = self.config.get("prefix_length", 50)

    def get_strategy_name(self) -> str:
        return "safe"

    def get_allele_id(self, sequence: str, locus_id: str) -> str:
        """Get allele ID using MD5 + sampling verification."""
        self.total_sequences += 1
        clean_seq = self._normalize_sequence(sequence)

        # Compute MD5 hash
        seq_hash = hashlib.md5(clean_seq.encode()).hexdigest()

        # Check if exists
        if seq_hash in self.allele_db:
            existing = self.allele_db[seq_hash]

            # Sampled verification
            if random.random() < self.verification_rate and not self._verify_match(
                clean_seq, existing
            ):
                # Collision detected, use SHA-256
                seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()
                if seq_hash not in self.allele_db:
                    return self._create_allele(seq_hash, clean_seq, locus_id)

            existing["count"] += 1
            return self._format_locus_allele(locus_id, seq_hash)

        return self._create_allele(seq_hash, clean_seq, locus_id)

    def _create_allele(self, seq_hash: str, sequence: str, locus_id: str) -> str:
        """Create new allele entry."""
        allele_id = len(self.allele_db) + 1
        self.allele_db[seq_hash] = {
            "id": allele_id,
            "sample": sequence[: self.sample_length],
            "length": len(sequence),
            "count": 1,
        }
        return self._format_locus_allele(locus_id, seq_hash)

    def _verify_match(self, seq1: str, existing: dict[str, Any]) -> bool:
        """Quick verification of sequence match."""
        if self.use_length_check and len(seq1) != existing["length"]:
            return False
        return not (
            self.use_prefix_check
            and seq1[: self.prefix_length] != existing["sample"][: self.prefix_length]
        )


class FastHashStrategy(HashStrategy):
    """Fast strategy: xxHash64 + length index.

    10x faster than MD5. Good for large datasets.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        try:
            import xxhash

            self._hasher = xxhash.xxh64
        except ImportError as err:
            raise ImportError(
                "xxhash required for fast strategy. Install: pip install xxhash"
            ) from err

        self.use_length_index = self.config.get("use_length_index", True)
        self.use_prefix_check = self.config.get("use_prefix_check", True)
        self.prefix_length = self.config.get("prefix_length", 30)
        self.length_index: dict[int, set[str]] = {}

    def get_strategy_name(self) -> str:
        return "fast"

    def get_allele_id(self, sequence: str, locus_id: str) -> str:
        """Get allele ID using xxHash64."""
        self.total_sequences += 1
        clean_seq = self._normalize_sequence(sequence)
        seq_len = len(clean_seq)

        # Compute hash
        seq_hash = self._hasher(clean_seq).hexdigest()

        # Length index check
        if self.use_length_index and seq_len in self.length_index:
            for candidate_hash in self.length_index[seq_len]:
                if candidate_hash == seq_hash:
                    existing = self.allele_db[candidate_hash]
                    # Prefix check
                    if self.use_prefix_check:
                        prefix = clean_seq[: self.prefix_length]
                        if prefix == existing["prefix"]:
                            existing["count"] += 1
                            return self._format_locus_allele(locus_id, candidate_hash)
                    else:
                        existing["count"] += 1
                        return self._format_locus_allele(locus_id, candidate_hash)

        # New allele
        return self._create_allele(seq_hash, clean_seq, seq_len, locus_id)

    def _create_allele(
        self, seq_hash: str, sequence: str, seq_len: int, locus_id: str
    ) -> str:
        """Create new allele entry."""
        allele_id = len(self.allele_db) + 1
        self.allele_db[seq_hash] = {
            "id": allele_id,
            "prefix": sequence[: self.prefix_length] if self.use_prefix_check else "",
            "length": seq_len,
            "count": 1,
        }

        if self.use_length_index:
            if seq_len not in self.length_index:
                self.length_index[seq_len] = set()
            self.length_index[seq_len].add(seq_hash)

        return self._format_locus_allele(locus_id, seq_hash)


class UltraHashStrategy(HashStrategy):
    """Ultra-fast strategy: xxHash32 only.

    Fastest possible. Use for preview only.
    Collision probability: 2^-32 (~1/4 billion)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        try:
            import xxhash

            self._hasher = xxhash.xxh32
        except ImportError as err:
            raise ImportError("xxhash required for ultra strategy") from err

    def get_strategy_name(self) -> str:
        return "ultra"

    def get_allele_id(self, sequence: str, locus_id: str) -> str:
        """Get allele ID using xxHash32."""
        self.total_sequences += 1
        clean_seq = self._normalize_sequence(sequence)

        seq_hash = self._hasher(clean_seq).intdigest()

        if seq_hash in self.allele_db:
            self.allele_db[seq_hash]["count"] += 1
            return self._format_locus_allele(locus_id, seq_hash)

        allele_id = len(self.allele_db) + 1
        self.allele_db[seq_hash] = {"id": allele_id, "count": 1}
        return self._format_locus_allele(locus_id, seq_hash)


class StrictHashStrategy(HashStrategy):
    """Strict strategy: SHA-256 + 100% verification.

    Maximum accuracy. Use for publication-quality results.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.store_full_sequences = self.config.get("store_full_sequences", False)

    def get_strategy_name(self) -> str:
        return "strict"

    def get_allele_id(self, sequence: str, locus_id: str) -> str:
        """Get allele ID using SHA-256 with full verification."""
        self.total_sequences += 1
        clean_seq = self._normalize_sequence(sequence)

        seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()

        if seq_hash in self.allele_db:
            existing = self.allele_db[seq_hash]
            # 100% verification
            if existing.get("seq") == clean_seq:
                existing["count"] += 1
                return self._format_locus_allele(locus_id, seq_hash)
            else:
                # SHA-256 collision (extremely rare)
                return self._handle_collision(clean_seq, locus_id)

        return self._create_allele(seq_hash, clean_seq, locus_id)

    def _create_allele(self, seq_hash: str, sequence: str, locus_id: str) -> str:
        """Create new allele entry."""
        allele_id = len(self.allele_db) + 1
        self.allele_db[seq_hash] = {
            "id": allele_id,
            "seq": sequence if self.store_full_sequences else sequence[:100],
            "count": 1,
        }
        return self._format_locus_allele(locus_id, seq_hash)

    def _handle_collision(self, sequence: str, locus_id: str) -> str:
        """Handle hash collision."""
        # Use full sequence hash
        seq_hash = hashlib.sha512(sequence.encode()).hexdigest()
        if seq_hash not in self.allele_db:
            return self._create_allele(seq_hash, sequence, locus_id)
        else:
            # This should never happen
            raise RuntimeError("Multiple SHA-256 collisions detected")


class BlastHashStrategy(HashStrategy):
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.min_identity = float(self.config.get("min_identity", 99.0))
        self.min_coverage = float(self.config.get("min_coverage", 0.95))
        self.blast_bin = str(self.config.get("blast_bin", "blastn"))
        self.makeblastdb_bin = str(self.config.get("makeblastdb", "makeblastdb"))
        self.timeout_sec = float(self.config.get("timeout_sec", 120.0))

        if (
            shutil.which(self.blast_bin) is None
            or shutil.which(self.makeblastdb_bin) is None
        ):
            raise ImportError("blast and makeblastdb are required for blast strategy")

        self._seq_to_allele_id: dict[str, int] = {}
        self._allele_sequences: dict[int, str] = {}

    def get_strategy_name(self) -> str:
        return "blast"

    def get_allele_id(self, sequence: str, locus_id: str) -> str:
        self.total_sequences += 1
        clean_seq = self._normalize_sequence(sequence)

        existing_id = self._seq_to_allele_id.get(clean_seq)
        if existing_id is not None:
            self._increment_count(existing_id)
            return self._format_locus_allele(locus_id, existing_id)

        matched_id = self._find_by_blast(clean_seq)
        if matched_id is not None:
            self._seq_to_allele_id[clean_seq] = matched_id
            self._increment_count(matched_id)
            return self._format_locus_allele(locus_id, matched_id)

        return self._create_allele(clean_seq, locus_id)

    def _find_by_blast(self, sequence: str) -> int | None:
        if not self._allele_sequences:
            return None

        with tempfile.TemporaryDirectory(prefix="gmlst_blast_") as temp_dir:
            temp_path = Path(temp_dir)
            db_fasta = temp_path / "alleles.fasta"
            query_fasta = temp_path / "query.fasta"
            db_prefix = temp_path / "alleles_db"
            out_tsv = temp_path / "hits.tsv"

            db_lines: list[str] = []
            for allele_id, allele_seq in self._allele_sequences.items():
                db_lines.append(f">allele_{allele_id}")
                db_lines.append(allele_seq)
            db_fasta.write_text("\n".join(db_lines) + "\n")

            query_fasta.write_text(f">query\n{sequence}\n")

            subprocess.run(
                [
                    self.makeblastdb_bin,
                    "-in",
                    str(db_fasta),
                    "-dbtype",
                    "nucl",
                    "-out",
                    str(db_prefix),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )

            subprocess.run(
                [
                    self.blast_bin,
                    "-query",
                    str(query_fasta),
                    "-db",
                    str(db_prefix),
                    "-outfmt",
                    "6 sseqid pident length qlen bitscore",
                    "-max_target_seqs",
                    "1",
                    "-out",
                    str(out_tsv),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )

            if not out_tsv.exists() or not out_tsv.read_text().strip():
                return None

            fields = out_tsv.read_text().strip().split("\t")
            if len(fields) < 4:
                return None

            subject_id = fields[0]
            identity = float(fields[1])
            aln_len = int(fields[2])
            qlen = int(fields[3])
            coverage = (aln_len / qlen) if qlen else 0.0

            if identity < self.min_identity or coverage < self.min_coverage:
                return None

            if not subject_id.startswith("allele_"):
                return None

            return int(subject_id.split("_", maxsplit=1)[1])

    def _create_allele(self, sequence: str, locus_id: str) -> str:
        allele_id = len(self._allele_sequences) + 1
        seq_hash = hashlib.sha256(sequence.encode()).hexdigest()

        self._allele_sequences[allele_id] = sequence
        self._seq_to_allele_id[sequence] = allele_id
        self.allele_db[seq_hash] = {
            "id": allele_id,
            "seq": sequence,
            "count": 1,
        }
        return self._format_locus_allele(locus_id, allele_id)

    def _increment_count(self, allele_id: int) -> None:
        for value in self.allele_db.values():
            if value["id"] == allele_id:
                value["count"] += 1
                return


class HashStrategyManager:
    """Manager for hash strategy registration and instantiation."""

    _strategies: dict[str, type[HashStrategy]] = {
        "safe": SafeHashStrategy,
        "fast": FastHashStrategy,
        "ultra": UltraHashStrategy,
        "strict": StrictHashStrategy,
        "blast": BlastHashStrategy,
    }

    @classmethod
    def register_strategy(cls, name: str, strategy_class: type[HashStrategy]) -> None:
        """Register a new hash strategy."""
        cls._strategies[name] = strategy_class

    @classmethod
    def get_strategy(
        cls, name: str, config: dict[str, Any] | None = None
    ) -> HashStrategy:
        """Get a hash strategy instance."""
        if name not in cls._strategies:
            raise ValueError(
                f"Unknown strategy: {name}. Available: {list(cls._strategies.keys())}"
            )

        return cls._strategies[name](config)

    @classmethod
    def list_strategies(cls) -> list[str]:
        """List available strategies."""
        return list(cls._strategies.keys())
