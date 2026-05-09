"""Database provider registry."""

from __future__ import annotations

import os

from gmlst.database.providers.base import Provider, SchemeInfo
from gmlst.database.providers.bigsdb import BigSdbProvider
from gmlst.database.providers.cgmlst import CgmlstProvider
from gmlst.database.providers.enterobase import EnterobaseProvider

_REGISTRY: dict[str, Provider] = {
    "pubmlst": BigSdbProvider(
        name="pubmlst",
        base_url=os.getenv("GMLST_PUBMLST_BASE_URL", "https://rest.pubmlst.org/db"),
        label="PubMLST",
    ),
    "pasteur": BigSdbProvider(
        name="pasteur",
        base_url=os.getenv(
            "GMLST_PASTEUR_BASE_URL",
            "https://bigsdb.pasteur.fr/api/db",
        ),
        label="Pasteur BIGSdb",
    ),
    "enterobase": EnterobaseProvider(),
    "cgmlst": CgmlstProvider(),
}

private_bigsdb_url = os.getenv("GMLST_PRIVATE_BIGSDB_URL", "").strip()
if private_bigsdb_url:
    private_bigsdb_name = os.getenv("GMLST_PRIVATE_BIGSDB_NAME", "private").strip()
    private_bigsdb_name = (
        private_bigsdb_name.lower() if private_bigsdb_name else "private"
    )
    if private_bigsdb_name in {"all", "local"}:
        private_bigsdb_name = "private"
    if private_bigsdb_name not in _REGISTRY:
        _REGISTRY[private_bigsdb_name] = BigSdbProvider(
            name=private_bigsdb_name,
            base_url=private_bigsdb_url,
            label=os.getenv("GMLST_PRIVATE_BIGSDB_LABEL", "Private BIGSdb"),
        )

AVAILABLE_PROVIDERS: list[str] = list(_REGISTRY.keys())


def get_provider(name: str) -> Provider:
    """Return a provider instance by name."""
    name = name.lower()
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {', '.join(AVAILABLE_PROVIDERS)}"
        )
    return _REGISTRY[name]


__all__ = [
    "Provider",
    "SchemeInfo",
    "AVAILABLE_PROVIDERS",
    "get_provider",
]
