"""Base Protocol and shared types for database providers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from gmlst.database.download import DownloadTool, download_files_batch

logger = logging.getLogger("gmlst.database.providers.base")


@dataclass
class SchemeInfo:
    """Metadata for one downloadable scheme.

    Displayed in ``gmlst scheme list`` and used to resolve ``--scheme``.
    """

    scheme_name: str
    """Short name the user passes to ``--scheme``, e.g. ``"saureus"``."""

    display_name: str
    """Human-readable scheme title, e.g. ``"Staphylococcus aureus MLST"``."""

    organism: str
    """Organism description, e.g. ``"Staphylococcus aureus"``."""

    scheme_type: str
    """``"mlst"``, ``"cgmlst"``, ``"wgmlst"``, etc."""

    n_loci: int = 0
    """Number of loci (0 = unknown)."""

    provider: str = ""
    """Provider identifier, e.g. ``"pubmlst"``."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Provider-specific metadata (internal URLs, IDs, etc.)."""


@runtime_checkable
class Provider(Protocol):
    """Interface every database provider must satisfy."""

    @property
    def name(self) -> str:
        """Short identifier, e.g. ``"pubmlst"``."""
        ...

    @property
    def label(self) -> str:
        """Human-readable provider name, e.g. ``"PubMLST"``."""
        ...

    def list_schemes(self, scheme_type: str = "mlst") -> list[SchemeInfo]:
        """Return available schemes filtered by *scheme_type*.

        Parameters
        ----------
        scheme_type:
            One of ``"mlst"``, ``"cgmlst"``, ``"wgmlst"``, ``"all"``.
        """
        ...

    def download_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "mlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Download allele FASTAs and ST profile to *dest_dir*.

        Parameters
        ----------
        scheme_name:
            As returned by :attr:`SchemeInfo.scheme_name`.
        dest_dir:
            Destination directory (created if absent).
        scheme_type:
            ``"mlst"``, ``"cgmlst"``, etc.
        """
        ...

    def update_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "mlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
    ) -> bool:
        """Update *scheme_name* in place if remote data changed.

        Returns
        -------
        bool
            True if local cache content changed, False if already up to date.
        """
        ...


def download_required_files(
    url_dest_pairs: list[tuple[str, Path]],
    *,
    provider_name: str,
    download_tool: DownloadTool = "auto",
    max_connections: int | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    if not url_dest_pairs:
        return

    total = len(url_dest_pairs)
    success, fail = download_files_batch(
        url_dest_pairs,
        max_concurrent=max_connections or 4,
        tool=download_tool,
        headers=headers,
    )

    if fail > 0:
        failed_files = [
            dest
            for _url, dest in url_dest_pairs
            if not dest.exists() or dest.stat().st_size == 0
        ]
        for f in failed_files:
            f.unlink(missing_ok=True)
        successfully_downloaded = total - fail
        if successfully_downloaded > 0:
            logger.warning(
                "[%s] %d/%d files downloaded, %d failed. "
                "Successful downloads are preserved.",
                provider_name,
                successfully_downloaded,
                total,
                fail,
            )
        raise RuntimeError(
            f"[{provider_name}] Failed to download {fail}/{total} files. "
            "Re-run the command to retry failed downloads "
            "(successfully downloaded files will be skipped)."
        )

    for _url, dest_file in url_dest_pairs:
        if not dest_file.exists() or dest_file.stat().st_size == 0:
            dest_file.unlink(missing_ok=True)
            raise RuntimeError(
                f"[{provider_name}] Missing or empty downloaded file: {dest_file}"
            )


def generate_scheme_base_name(organism_name: str) -> str:
    """Generate short scheme base name from full organism name.

    Rules:
    1. For species (e.g., 'Listeria monocytogenes'):
       first letter of genus + species = 'lmonocytogenes'
    2. For genus only (e.g., 'Neisseria spp.'):
       full genus name only = 'neisseria'
    3. For multi-species labels containing '/' in species token
       (e.g., 'Campylobacter jejuni/coli'):
       use genus only = 'campylobacter'

    Examples:
        'Listeria monocytogenes' -> 'lmonocytogenes'
        'Staphylococcus aureus' -> 'saureus'
        'Neisseria spp.' -> 'neisseria'
        'Campylobacter jejuni/coli' -> 'campylobacter'
        'Klebsiella pneumoniae' -> 'kpneumoniae'
    """
    if not organism_name:
        return "unknown"

    # Normalize: lowercase and remove extra spaces
    name = organism_name.lower().strip()

    # Handle 'spp.' or 'sp.' cases (genus only)
    if (
        " spp." in name
        or name.endswith(" spp")
        or " sp." in name
        or name.endswith(" sp")
    ):
        # Extract genus name only
        genus = name.split()[0]
        return genus

    # Handle full species name (genus + species)
    parts = name.split()
    if len(parts) >= 2:
        genus = parts[0]
        species = parts[1]
        if "/" in species:
            return genus
        # Return first letter of genus + full species name
        return f"{genus[0]}{species}"

    # Fallback: just return the name as-is (single word)
    return name
