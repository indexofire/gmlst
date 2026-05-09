"""Base Protocol and shared types for database providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from gmlst.database.download import DownloadTool, download_files_batch


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

    extra: dict = field(default_factory=dict)
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
) -> None:
    if not url_dest_pairs:
        return

    _, fail = download_files_batch(
        url_dest_pairs,
        max_concurrent=max_connections or 8,
        tool=download_tool,
    )
    if fail > 0:
        raise RuntimeError(f"[{provider_name}] Failed to download {fail} files")

    for _url, dest_file in url_dest_pairs:
        if not dest_file.exists():
            raise RuntimeError(
                f"[{provider_name}] Missing downloaded file: {dest_file}"
            )
