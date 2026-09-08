"""Re-export shim for gene prediction used by scheme-free typing (see core/)."""

from gmlst.core.gene_predictor import (
    PredictedGene,
    ProdigalPredictor,
    create_pyrodigal_training_file,
)

__all__ = [
    "PredictedGene",
    "ProdigalPredictor",
    "create_pyrodigal_training_file",
]
