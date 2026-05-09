"""Alignment backend registry."""

from gmlst.aligners.base import Aligner, AlignmentResult, AlleleMatch
from gmlst.aligners.blastn import BlastnAligner
from gmlst.aligners.kma import KmaAligner
from gmlst.aligners.minimap2 import Minimap2Aligner
from gmlst.aligners.nucmer import NucmerAligner

_REGISTRY: dict[str, type[Aligner]] = {
    "blastn": BlastnAligner,
    "kma": KmaAligner,
    "minimap2": Minimap2Aligner,
    "nucmer": NucmerAligner,
}

AVAILABLE_BACKENDS: list[str] = list(_REGISTRY.keys())


def get_aligner(name: str, **kwargs) -> Aligner:
    """Return an instantiated aligner by backend name.

    Parameters
    ----------
    name:
        Backend name (blastn, kma, minimap2, nucmer).
    **kwargs:
        Additional arguments passed to aligner constructor.
        For blastn: threads (int, default=1)
    """
    name = name.lower()
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown backend '{name}'. Available: {', '.join(AVAILABLE_BACKENDS)}"
        )
    return _REGISTRY[name](**kwargs)


__all__ = [
    "Aligner",
    "AlleleMatch",
    "AlignmentResult",
    "AVAILABLE_BACKENDS",
    "get_aligner",
]
