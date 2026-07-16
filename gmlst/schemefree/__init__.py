"""Scheme-free MLST typing module.

This module provides de novo scheme discovery and typing capabilities,
allowing users to perform MLST-like analysis without predefined schemes.
"""

from gmlst.core.gene_predictor import PredictedGene, ProdigalPredictor
from gmlst.schemefree.assembly_engine import MegahitAssembler
from gmlst.schemefree.cluster_engine import MMseqsClusterEngine
from gmlst.schemefree.config import SchemaFreeConfig
from gmlst.schemefree.hasher import (
    BlastHashStrategy,
    FastHashStrategy,
    HashStrategy,
    HashStrategyManager,
    SafeHashStrategy,
    StrictHashStrategy,
    UltraHashStrategy,
)
from gmlst.schemefree.io_handler import (
    profiles_to_json,
    profiles_to_tsv,
    read_scheme_json,
    write_error_report_json,
    write_scheme_json,
    write_summary_report_json,
)
from gmlst.schemefree.typing_engine import SampleProfile, SchemeFreeTyper

__all__ = [
    "BlastHashStrategy",
    "FastHashStrategy",
    "HashStrategy",
    "HashStrategyManager",
    "MegahitAssembler",
    "MMseqsClusterEngine",
    "PredictedGene",
    "ProdigalPredictor",
    "profiles_to_json",
    "profiles_to_tsv",
    "read_scheme_json",
    "SafeHashStrategy",
    "SampleProfile",
    "SchemaFreeConfig",
    "SchemeFreeTyper",
    "StrictHashStrategy",
    "UltraHashStrategy",
    "write_error_report_json",
    "write_summary_report_json",
    "write_scheme_json",
]

__version__ = "0.1.0"
