"""Local database cache management.

Schemes are stored under the cache root at ``<provider>/<scheme_name>/``.
Each scheme directory contains:
  - ``<locus>.tfa``   allele FASTA files
  - ``<scheme>.txt``  ST profile TSV
  - ``.meta.json``    download metadata (provider, scheme_type, loci list, …)

Catalogs are stored under ``<cache_root>/_catalog/<provider>.json``.

Cache root resolution order (first match wins):
  1. Explicit ``root`` parameter passed to :class:`DatabaseCache`
  2. ``GMLST_CACHE_DIR`` environment variable
  3. ``$CONDA_PREFIX/share/gmlst`` when running inside a conda environment
  4. ``$VIRTUAL_ENV/.cache/gmlst`` when running inside a Python virtualenv
  5. ``~/.cache/gmlst`` (default)
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from gmlst.database.atomic import atomic_write_text
from gmlst.database.download import DownloadTool
from gmlst.database.schema import Scheme
from gmlst.fasta_io import utc_now_iso

logger = logging.getLogger(__name__)


def _load_blocked_schemes() -> dict[str, set[str]]:
    """Load blocked scheme names per provider from data/blocked_schemes.json."""
    try:
        import importlib.resources as pkg_resources

        blocked_path = Path(
            str(pkg_resources.files("gmlst") / "data" / "blocked_schemes.json")
        )
        if blocked_path.is_file():
            with blocked_path.open() as f:
                data = json.load(f)
                return {
                    k: set(v)
                    for k, v in data.items()
                    if not k.startswith("_") and isinstance(v, list)
                }
    except (OSError, json.JSONDecodeError):
        # blocked_schemes.json is optional; treat missing/corrupt as empty
        pass
    return {}


def _resolve_cache_root() -> Path:
    """Resolve the default cache root using environment-aware fallbacks."""
    env_dir = os.environ.get("GMLST_CACHE_DIR")
    if env_dir:
        return Path(env_dir)

    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        return Path(conda_prefix) / "share" / "gmlst"

    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        return Path(venv) / ".cache" / "gmlst"

    return Path.home() / ".cache" / "gmlst"


# Strict whitelist for path-component identifiers (scheme names, providers,
# aligner backends). The first character must be a letter, digit, or
# underscore; subsequent characters may also include ``.`` and ``-``. This
# implicitly rejects path separators, leading dots, absolute paths, drive
# letters, and most shell metacharacters.
_SCHEME_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def _validate_scheme_identifier(value: str, label: str) -> str:
    """Validate that *value* is safe as a single path component.

    Scheme names, providers, and backends are joined directly into filesystem
    paths under the cache root, so a value like ``"../etc"`` could escape it.
    Enforces layered checks: empty, null bytes, separators, ``..`` substrings,
    and a strict whitelist regex (defends-in-depth even though each later
    check is mostly redundant with the regex).

    Raises ``ValueError`` on any violation; returns *value* unchanged on success.
    """
    if not value:
        raise ValueError(f"Invalid {label}: {value!r} (must be non-empty)")
    if "\x00" in value:
        raise ValueError(f"Invalid {label}: {value!r} (contains null byte)")
    # Path separators are never allowed in a single path component.
    if "/" in value or "\\" in value:
        raise ValueError(
            f"Invalid {label}: {value!r} (path separators are not allowed)"
        )
    # Reject any parent-directory reference, even as a substring (e.g. ``a..b``)
    # so that future relaxation of the whitelist cannot reintroduce traversal.
    if ".." in value:
        raise ValueError(f"Invalid {label}: {value!r} ('..' sequences are not allowed)")
    # Strict whitelist. Implicitly rejects leading dots (hidden files),
    # absolute paths, drive letters, and any other shell metacharacters.
    if not _SCHEME_IDENTIFIER_RE.match(value):
        raise ValueError(
            f"Invalid {label}: {value!r} "
            "(allowed: letters, digits, '_', '-', '.'; "
            "must start with a letter, digit, or '_')"
        )
    return value


class DatabaseCache:
    """Manage locally cached MLST schemes from any provider.

    Parameters
    ----------
    root:
        Root cache directory.  When *None*, the cache root is resolved
        from environment variables (``GMLST_CACHE_DIR``, ``CONDA_PREFIX``,
        ``VIRTUAL_ENV``) with a final fallback to ``~/.cache/gmlst``.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _resolve_cache_root()
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def scheme_dir(self, name: str, provider: str = "pubmlst") -> Path:
        """Return the directory for a cached scheme."""
        _validate_scheme_identifier(name, "scheme name")
        _validate_scheme_identifier(provider, "provider")
        return self.root / provider / name

    def is_downloaded(self, name: str, provider: str = "pubmlst") -> bool:
        """Return True when the scheme has a ``.meta.json`` in the cache."""
        return (self.scheme_dir(name, provider) / ".meta.json").exists()

    def detect_provider(self, name: str) -> str | None:
        """Guess which provider owns *name*: downloaded cache first, then catalogs.

        Scans available providers for a downloaded copy, then falls back to
        cached catalogs listing the scheme name. Returns ``None`` when no
        provider claims it.
        """
        from gmlst.database.providers import AVAILABLE_PROVIDERS

        for provider in AVAILABLE_PROVIDERS:
            if self.is_downloaded(name, provider):
                return provider

        for provider in AVAILABLE_PROVIDERS:
            catalog = self.load_catalog(provider)
            if catalog and any(item.get("scheme_name") == name for item in catalog):
                return provider

        return None

    # ------------------------------------------------------------------
    # Ensure / load
    # ------------------------------------------------------------------

    def ensure_scheme(
        self,
        name: str,
        *,
        provider: str = "pubmlst",
        scheme_type: str = "mlst",
        force: bool = False,
        token: str | None = None,
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
    ) -> Scheme:
        """Return a :class:`Scheme`, downloading it first if necessary."""
        if force:
            scheme_dir = self.scheme_dir(name, provider)
            if scheme_dir.exists():
                # Defense in depth: even though scheme_dir() now validates
                # name/provider, verify the resolved path stays inside the
                # cache root before the destructive rmtree.
                resolved = scheme_dir.resolve()
                try:
                    resolved.relative_to(self.root.resolve())
                except ValueError as exc:
                    raise ValueError(
                        f"Refusing to delete path outside cache root: {resolved}"
                    ) from exc
                shutil.rmtree(scheme_dir)
        if force or not self.is_downloaded(name, provider):
            self._download(
                name,
                provider=provider,
                scheme_type=scheme_type,
                token=token,
                download_tool=download_tool,
                max_connections=max_connections,
            )
        return self.load_scheme(name, provider=provider)

    def update_scheme(
        self,
        name: str,
        *,
        provider: str = "pubmlst",
        scheme_type: str = "mlst",
        token: str | None = None,
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
    ) -> tuple[Scheme, bool]:
        """Update a cached scheme in place, returning ``(scheme, changed)``.

        When the scheme is not cached yet, downloads it and reports
        ``changed=True``. Otherwise delegates change detection to the
        provider's ``update_scheme`` (providers without one are fully
        re-downloaded and always count as changed), records
        ``updated_at`` while preserving the original ``downloaded_at``,
        and returns the freshly loaded scheme plus whether any local
        content actually changed.
        """
        from gmlst.database.providers import get_provider

        resolved_scheme_type = scheme_type
        meta_file = self.scheme_dir(name, provider) / ".meta.json"
        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                loaded_meta = json.loads(meta_file.read_text())
                meta = loaded_meta if isinstance(loaded_meta, dict) else {}
                meta_scheme_type = str(meta.get("scheme_type", "")).strip().lower()
                if scheme_type == "mlst" and meta_scheme_type:
                    resolved_scheme_type = meta_scheme_type
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    "Failed to read scheme metadata %s: %s",
                    meta_file,
                    exc,
                )
        original_downloaded_at = str(meta.get("downloaded_at", "")) if meta else ""

        if not self.is_downloaded(name, provider):
            self._download(
                name,
                provider=provider,
                scheme_type=resolved_scheme_type,
                token=token,
                download_tool=download_tool,
                max_connections=max_connections,
            )
            return (self.load_scheme(name, provider=provider), True)

        p = get_provider(provider)
        if provider == "enterobase" and token and hasattr(p, "_token"):
            provider_obj: Any = p
            provider_obj._token = token

        extra: dict[str, Any] = {}
        try:
            catalog = self.load_catalog(provider)
            if catalog:
                for entry in catalog:
                    if entry.get("scheme_name") == name:
                        extra = entry.get("extra", {})
                        break
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("Failed to load catalog for update: %s", exc)

        changed = False
        updater = getattr(p, "update_scheme", None)
        if callable(updater):
            changed = bool(
                updater(
                    name,
                    self.scheme_dir(name, provider),
                    resolved_scheme_type,
                    download_tool=download_tool,
                    max_connections=max_connections,
                    extra=extra,
                )
            )
        else:
            self._download(
                name,
                provider=provider,
                scheme_type=resolved_scheme_type,
                token=token,
                download_tool=download_tool,
                max_connections=max_connections,
            )
            changed = True

        self._record_update_metadata(
            name,
            provider=provider,
            original_downloaded_at=original_downloaded_at,
        )
        return (self.load_scheme(name, provider=provider), changed)

    def load_scheme(self, name: str, provider: str = "pubmlst") -> Scheme:
        """Load a scheme from local cache.

        Raises
        ------
        FileNotFoundError
            If the scheme has not been downloaded yet.
        """
        scheme_dir = self.scheme_dir(name, provider)
        if not scheme_dir.exists():
            raise FileNotFoundError(
                f"Scheme '{name}' (provider: {provider}) not found in cache. "
                f"Run: gmlst scheme download -s {name}"
            )

        meta_file = scheme_dir / ".meta.json"
        loci: list[str] = []
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
            loci = meta.get("loci", [])

        # Discover allele files (.tfa from bigsdb/enterobase, .fasta from cgmlst.org)
        allele_files: dict[str, Path] = {}
        loci_set = set(loci)
        for pattern in ("*.tfa", "*.fasta"):
            for f in sorted(scheme_dir.glob(pattern)):
                locus = f.stem
                if locus not in allele_files:  # .tfa takes priority
                    allele_files[locus] = f
                    if locus not in loci_set:
                        loci.append(locus)
                        loci_set.add(locus)

        if not allele_files:
            raise FileNotFoundError(
                f"No allele files found in {scheme_dir}. "
                f"Try: gmlst scheme download -s {name} --force"
            )

        # Find profile file (prefer .txt, fallback .tsv)
        profile_file: Path | None = None
        for pattern in ("*.txt", "*.tsv"):
            candidates = list(scheme_dir.glob(pattern))
            if candidates:
                profile_file = candidates[0]
                break

        return Scheme(
            name=name,
            loci=loci,
            allele_files=allele_files,
            profile_file=profile_file,
        )

    def list_cached(self) -> list[dict[str, Any]]:
        """Return metadata dicts for all locally cached schemes."""
        results = []
        for provider_dir in sorted(self.root.iterdir()):
            if not provider_dir.is_dir() or provider_dir.name.startswith("_"):
                continue
            for scheme_dir in sorted(provider_dir.iterdir()):
                meta_file = scheme_dir / ".meta.json"
                if not meta_file.exists():
                    continue
                try:
                    meta = json.loads(meta_file.read_text())
                except (OSError, json.JSONDecodeError) as exc:
                    logger.warning(
                        "Failed to read scheme metadata %s: %s", meta_file, exc
                    )
                    meta = {}
                results.append(
                    {
                        "scheme": scheme_dir.name,
                        "provider": provider_dir.name,
                        "scheme_type": meta.get("scheme_type", "mlst"),
                        "loci": len(meta.get("loci", [])),
                        "downloaded_at": meta.get("downloaded_at", ""),
                        "updated_at": meta.get("updated_at", ""),
                    }
                )
        return results

    def index_dir(
        self, scheme_name: str, backend: str, provider: str = "pubmlst"
    ) -> Path:
        """Return (and create) the aligner index directory for a scheme."""
        _validate_scheme_identifier(scheme_name, "scheme name")
        _validate_scheme_identifier(backend, "backend")
        _validate_scheme_identifier(provider, "provider")
        idx = self.root / "_indexes" / provider / backend / scheme_name
        idx.mkdir(parents=True, exist_ok=True)
        return idx

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _download(
        self,
        name: str,
        *,
        provider: str,
        scheme_type: str,
        token: str | None,
        download_tool: DownloadTool,
        max_connections: int | None,
    ) -> None:
        from gmlst.database.providers import get_provider

        p = get_provider(provider)

        # Inject token for Enterobase
        if provider == "enterobase" and token and hasattr(p, "_token"):
            provider_obj: Any = p
            provider_obj._token = token

        # Resolve extra metadata from catalog (e.g. Enterobase directory name)
        extra: dict[str, Any] = {}
        try:
            catalog = self.load_catalog(provider)
            if catalog:
                for entry in catalog:
                    if entry.get("scheme_name") == name:
                        extra = entry.get("extra", {})
                        break
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("Failed to load catalog for download: %s", exc)

        dest = self.scheme_dir(name, provider)
        p.download_scheme(
            name,
            dest,
            scheme_type=scheme_type,
            download_tool=download_tool,
            max_connections=max_connections,
            extra=extra,
        )
        self._record_download_metadata(name, provider=provider)

    def get_scheme_metadata(
        self, name: str, provider: str = "pubmlst"
    ) -> dict[str, Any]:
        """Return metadata dict for a cached scheme, or empty dict."""
        return self._read_scheme_metadata(name, provider)

    def _read_scheme_metadata(self, name: str, provider: str) -> dict[str, Any]:
        meta_file = self.scheme_dir(name, provider) / ".meta.json"
        if not meta_file.exists():
            return {}
        try:
            data = json.loads(meta_file.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read scheme metadata %s: %s", meta_file, exc)
            return {}
        return data if isinstance(data, dict) else {}

    def write_scheme_metadata(
        self,
        name: str,
        provider: str,
        metadata: dict[str, Any],
    ) -> None:
        """Public writer for scheme ``.meta.json`` (atomic)."""
        self._write_scheme_metadata(name, provider, metadata)

    def _write_scheme_metadata(
        self,
        name: str,
        provider: str,
        metadata: dict[str, Any],
    ) -> None:
        meta_file = self.scheme_dir(name, provider) / ".meta.json"
        atomic_write_text(meta_file, json.dumps(metadata, indent=2))

    def _record_download_metadata(self, name: str, *, provider: str) -> None:
        metadata = self._read_scheme_metadata(name, provider)
        if not metadata:
            return
        if not metadata.get("downloaded_at"):
            metadata["downloaded_at"] = utc_now_iso()
            self._write_scheme_metadata(name, provider, metadata)

    def _record_update_metadata(
        self,
        name: str,
        *,
        provider: str,
        original_downloaded_at: str,
    ) -> None:
        metadata = self._read_scheme_metadata(name, provider)
        if not metadata:
            return
        now = utc_now_iso()
        if original_downloaded_at:
            metadata["downloaded_at"] = original_downloaded_at
        elif not metadata.get("downloaded_at"):
            metadata["downloaded_at"] = now
        metadata["updated_at"] = now
        self._write_scheme_metadata(name, provider, metadata)

    # ------------------------------------------------------------------
    # Catalog (scheme list) caching
    # ------------------------------------------------------------------

    def _catalog_dir(self) -> Path:
        """Return the catalog cache directory."""
        d = self.root / "_catalog"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def local_catalog_path(self) -> Path:
        """Return the on-disk path of the ``local`` provider catalog."""
        return self._catalog_path("local")

    def _catalog_path(self, provider: str) -> Path:
        """Path to cached catalog JSON for a provider."""
        return self._catalog_dir() / f"{provider}.json"

    def has_catalog(self, provider: str) -> bool:
        """Check if a cached catalog exists."""
        return self._catalog_path(provider).exists()

    def _get_existing_scheme_owners(
        self, exclude_provider: str | None = None
    ) -> dict[str, str]:
        """Map scheme names from all cached catalogs to their owning provider.

        When several stale catalogs hold the same name, the
        highest-priority provider (earliest in ``AVAILABLE_PROVIDERS``)
        is recorded as the owner, because yielding is only correct while
        every other owner has lower priority.
        """
        from gmlst.database.providers import AVAILABLE_PROVIDERS

        priority = {p: i for i, p in enumerate(AVAILABLE_PROVIDERS)}

        def rank(provider: str) -> int:
            return priority.get(provider, len(priority))

        owners: dict[str, str] = {}
        for catalog_file in self._catalog_dir().glob("*.json"):
            file_provider = catalog_file.stem
            if exclude_provider and file_provider == exclude_provider:
                continue
            try:
                data = json.loads(catalog_file.read_text())
                for scheme in data.get("schemes", []):
                    name = scheme.get("scheme_name", "")
                    current = owners.get(name)
                    if current is None or rank(file_provider) < rank(current):
                        owners[name] = file_provider
            except (OSError, json.JSONDecodeError):
                continue
        return owners

    def _resolve_cross_provider_conflicts(
        self,
        provider: str,
        schemes: list[dict[str, Any]],
        owners: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Rename schemes whose names collide with higher-priority providers.

        Names owned by lower-priority providers are kept as-is — the stale
        owner is repaired by its own load-time heal. Names not present in
        any other catalog never change.
        """
        from gmlst.database.providers import AVAILABLE_PROVIDERS

        priority = {p: i for i, p in enumerate(AVAILABLE_PROVIDERS)}
        my_priority = priority.get(provider, len(priority))

        existing_max_suffix: dict[str, int] = {}
        for name in owners:
            base, _, suffix_str = name.rpartition("_")
            if base and suffix_str.isdigit():
                existing_max_suffix[base] = max(
                    existing_max_suffix.get(base, 0), int(suffix_str)
                )

        taken = set(owners)
        for scheme in schemes:
            name = scheme["scheme_name"]
            if name not in taken:
                taken.add(name)
                continue
            owner = owners.get(name)
            if owner is not None and priority.get(owner, len(priority)) >= my_priority:
                continue
            base, _, suffix_str = name.rpartition("_")
            if not suffix_str.isdigit():
                base, suffix_str = name, "0"
            new_suffix = max(existing_max_suffix.get(base, 0), int(suffix_str)) + 1
            while f"{base}_{new_suffix}" in taken:
                new_suffix += 1
            new_name = f"{base}_{new_suffix}"
            logger.info(
                "Renamed scheme '%s' -> '%s' to ensure global uniqueness",
                name,
                new_name,
            )
            scheme["scheme_name"] = new_name
            taken.add(new_name)
        return schemes

    def _heal_cross_provider_collisions(
        self, provider: str, schemes: list[dict[str, Any]]
    ) -> None:
        """Repair catalogs written before cross-provider uniqueness existed.

        When entries of *provider* collide with a higher-priority
        provider's cached names (e.g. the historical abaumannii_1 mlst vs
        cgMLST collision), the catalog is re-saved through
        :meth:`save_catalog`, renaming only the conflicting entries.
        """
        owners = self._get_existing_scheme_owners(exclude_provider=provider)
        if not owners:
            return
        from gmlst.database.providers import AVAILABLE_PROVIDERS

        priority = {p: i for i, p in enumerate(AVAILABLE_PROVIDERS)}
        my_priority = priority.get(provider, len(priority))
        collides = any(
            scheme.get("scheme_name") in owners
            and priority.get(owners[scheme["scheme_name"]], len(priority)) < my_priority
            for scheme in schemes
        )
        if collides:
            self.save_catalog(provider, schemes)

    def load_catalog(self, provider: str) -> list[dict[str, Any]] | None:
        """Load cached catalog; return None if missing or corrupt.

        If no local cache exists, attempts to copy default catalog from
        package data.
        """
        path = self._catalog_path(provider)
        if not path.exists():
            # Try to copy default catalog from package data
            self._copy_default_catalog(provider)

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load catalog %s: %s", path, exc)
            return None
        schemes = data.get("schemes", [])
        self._heal_cross_provider_collisions(provider, schemes)
        return schemes

    def _normalize_scheme_names(
        self, schemes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize scheme names to short format (e.g., 'lmonocytogenes_1')."""
        from gmlst.database.providers.base import generate_scheme_base_name

        # Group schemes by their base organism
        organism_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for scheme in schemes:
            organism = scheme.get("organism", "")
            organism_groups[organism].append(scheme)

        # Reassign scheme names with short format
        name_counters: dict[str, int] = defaultdict(int)
        for organism, group_schemes in organism_groups.items():
            base_name = generate_scheme_base_name(organism)

            for scheme in group_schemes:
                name_counters[base_name] += 1
                scheme["scheme_name"] = f"{base_name}_{name_counters[base_name]}"

        return schemes

    def _copy_default_catalog(self, provider: str) -> bool:
        """Copy default catalog from package data to cache.

        Ensures global uniqueness by processing through save_catalog.
        Returns True if successful.
        """
        try:
            import importlib.resources as pkg_resources
            import json

            default_file = f"{provider}.json"
            pkg_path = pkg_resources.files("gmlst") / "data" / "catalogs" / default_file

            if pkg_path.is_file():
                # Read schemes from package data
                data = json.loads(pkg_path.read_text())
                schemes = data.get("schemes", [])

                # Process through save_catalog to ensure global uniqueness
                self.save_catalog(provider, schemes)
                logger.info("Copied and processed default catalog: %s", provider)
                return True
        except (OSError, json.JSONDecodeError) as e:  # pyright: ignore[reportPossiblyUnboundVariable]  # json is module-level import; pyright false positive
            logger.warning("Failed to copy default catalog: %s", e)
        return False

    def save_catalog(self, provider: str, schemes: list[dict[str, Any]]) -> None:
        """Write catalog JSON to cache with globally unique scheme names.

        Ensures scheme names are unique across all providers by checking
        existing catalogs and adjusting suffixes as needed. Blocked schemes
        are filtered out before saving.
        """

        blocked = _load_blocked_schemes().get(provider, set())
        if blocked:
            before = len(schemes)
            schemes = [
                s
                for s in schemes
                if s.get("scheme_name") not in blocked
                and s.get("extra", {}).get("directory") not in blocked
            ]
            if before != len(schemes):
                logger.info(
                    "Filtered %d blocked scheme(s) for '%s'",
                    before - len(schemes),
                    provider,
                )

        # First, normalize names within this provider's schemes
        schemes = self._normalize_scheme_names(schemes)

        # Rename only genuine cross-provider conflicts; every other name
        # keeps its identity (stability first).
        owners = self._get_existing_scheme_owners(exclude_provider=provider)
        if owners:
            schemes = self._resolve_cross_provider_conflicts(provider, schemes, owners)

        path = self._catalog_path(provider)
        # Determine scheme_type from schemes (use first one or 'mixed')
        scheme_types = set(s.get("scheme_type", "mlst") for s in schemes)
        scheme_type = scheme_types.pop() if len(scheme_types) == 1 else "mixed"

        payload = {
            "provider": provider,
            "scheme_type": scheme_type,
            "updated_at": utc_now_iso(),
            "count": len(schemes),
            "schemes": schemes,
        }
        atomic_write_text(path, json.dumps(payload, indent=2))
        logger.info("Saved catalog: %s (%d schemes)", path, len(schemes))

    def update_catalog(
        self, provider: str, scheme_type: str = "mlst", token: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch fresh catalog from provider API and cache it.

        Returns the list of scheme dicts.
        """
        from gmlst.database.providers import get_provider

        p = get_provider(provider)
        if provider == "enterobase" and token and hasattr(p, "_token"):
            provider_obj: Any = p
            provider_obj._token = token

        logger.info("Fetching catalog from %s (%s) ...", p.label, scheme_type)
        scheme_infos = p.list_schemes(scheme_type=scheme_type)

        # Convert SchemeInfo to serializable dicts
        schemes = [
            {
                "scheme_name": s.scheme_name,
                "display_name": s.display_name,
                "organism": s.organism,
                "scheme_type": s.scheme_type,
                "n_loci": s.n_loci,
                "provider": s.provider,
                "extra": s.extra,
            }
            for s in scheme_infos
        ]
        self.save_catalog(provider, schemes)
        return schemes
