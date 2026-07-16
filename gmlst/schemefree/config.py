"""Configuration management for scheme-free typing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml

    HAS_YAML = True
except ImportError:
    yaml = None
    HAS_YAML = False


@dataclass
class HashConfig:
    """Hash strategy configuration."""

    strategy: str = "safe"
    safe: dict[str, Any] = field(
        default_factory=lambda: {
            "hash_algorithm": "md5",
            "verification_rate": 0.01,
            "sample_length": 100,
            "use_length_check": True,
            "use_prefix_check": True,
            "prefix_length": 50,
        }
    )
    fast: dict[str, Any] = field(
        default_factory=lambda: {
            "hash_algorithm": "xxhash64",
            "use_length_index": True,
            "use_prefix_check": True,
            "prefix_length": 30,
        }
    )
    ultra: dict[str, Any] = field(
        default_factory=lambda: {
            "hash_algorithm": "xxhash32",
            "no_verification": True,
        }
    )
    strict: dict[str, Any] = field(
        default_factory=lambda: {
            "hash_algorithm": "sha256",
            "full_verification": True,
            "store_full_sequences": False,
        }
    )


@dataclass
class ClusteringConfig:
    """MMseqs2 clustering configuration."""

    min_seq_id: float = 0.95
    coverage: float = 0.8
    cov_mode: int = 1
    cluster_mode: int = 0
    threads: str = "auto"
    timeout_sec: float = 300.0


@dataclass
class GenePredictionConfig:
    """Gene prediction configuration."""

    tool: str = "pyrodigal"
    mode: str = "meta"
    training_file: str | None = None
    closed_ends: bool = False
    min_gene_len: int = 100
    max_gene_len: int = 5000
    timeout_sec: float = 300.0


@dataclass
class AssemblyConfig:
    """Assembly configuration for FASTQ input."""

    tool: str = "megahit"
    preset: str = "meta-sensitive"
    min_contig_len: int = 500
    k_min: int = 21
    k_max: int = 141
    k_step: int = 12
    retries: int = 1
    max_parallel_samples: int = 2
    assemble_timeout_sec: float = 600.0


@dataclass
class SchemaFreeConfig:
    """Main configuration class for scheme-free typing."""

    hash: HashConfig = field(default_factory=HashConfig)
    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    gene_prediction: GenePredictionConfig = field(default_factory=GenePredictionConfig)
    assembly: AssemblyConfig = field(default_factory=AssemblyConfig)

    @classmethod
    def from_file(cls, path: Path | str) -> SchemaFreeConfig:
        """Load configuration from YAML file."""
        if not HAS_YAML:
            raise ImportError("PyYAML required. Install: pip install pyyaml")
        yaml_mod = yaml
        if yaml_mod is None:
            raise ImportError("PyYAML required. Install: pip install pyyaml")

        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml_mod.safe_load(f) or {}

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> SchemaFreeConfig:
        """Create config from dictionary."""
        config = cls()

        if "hash" in data:
            config.hash = HashConfig(**data["hash"])
        if "clustering" in data:
            config.clustering = ClusteringConfig(**data["clustering"])
        if "gene_prediction" in data:
            config.gene_prediction = GenePredictionConfig(**data["gene_prediction"])
        if "assembly" in data:
            config.assembly = AssemblyConfig(**data["assembly"])

        return config

    def to_file(self, path: Path | str) -> None:
        """Save configuration to YAML file."""
        if not HAS_YAML:
            raise ImportError("PyYAML required. Install: pip install pyyaml")
        yaml_mod = yaml
        if yaml_mod is None:
            raise ImportError("PyYAML required. Install: pip install pyyaml")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml_mod.dump(self._to_dict(), f, default_flow_style=False)

    def _to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "hash": {
                "strategy": self.hash.strategy,
                "safe": self.hash.safe,
                "fast": self.hash.fast,
                "ultra": self.hash.ultra,
                "strict": self.hash.strict,
            },
            "clustering": {
                "min_seq_id": self.clustering.min_seq_id,
                "coverage": self.clustering.coverage,
                "cov_mode": self.clustering.cov_mode,
                "cluster_mode": self.clustering.cluster_mode,
                "threads": self.clustering.threads,
                "timeout_sec": self.clustering.timeout_sec,
            },
            "gene_prediction": {
                "tool": self.gene_prediction.tool,
                "mode": self.gene_prediction.mode,
                "training_file": self.gene_prediction.training_file,
                "closed_ends": self.gene_prediction.closed_ends,
                "min_gene_len": self.gene_prediction.min_gene_len,
                "max_gene_len": self.gene_prediction.max_gene_len,
                "timeout_sec": self.gene_prediction.timeout_sec,
            },
            "assembly": {
                "tool": self.assembly.tool,
                "preset": self.assembly.preset,
                "min_contig_len": self.assembly.min_contig_len,
                "k_min": self.assembly.k_min,
                "k_max": self.assembly.k_max,
                "k_step": self.assembly.k_step,
                "retries": self.assembly.retries,
                "max_parallel_samples": self.assembly.max_parallel_samples,
                "assemble_timeout_sec": self.assembly.assemble_timeout_sec,
            },
        }

    def get_hash_config(self) -> dict[str, Any]:
        """Get configuration for current hash strategy."""
        strategy = self.hash.strategy
        base_config = getattr(self.hash, strategy, {})
        return {"strategy": strategy, **base_config}
