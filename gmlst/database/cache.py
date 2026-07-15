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

logger = logging.getLogger("gmlst.database_cache")


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
        return (self.scheme_dir(name, provider) / ".meta.json").exists()

    def detect_provider(self, name: str) -> str | None:
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
        for pattern in ("*.tfa", "*.fasta"):
            for f in sorted(scheme_dir.glob(pattern)):
                locus = f.stem
                if locus not in allele_files:  # .tfa takes priority
                    allele_files[locus] = f
                    if locus not in loci:
                        loci.append(locus)

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

    def list_cached(self) -> list[dict]:
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

    def _catalog_path(self, provider: str) -> Path:
        """Path to cached catalog JSON for a provider."""
        return self._catalog_dir() / f"{provider}.json"

    def has_catalog(self, provider: str) -> bool:
        """Check if a cached catalog exists."""
        return self._catalog_path(provider).exists()

    def load_catalog(self, provider: str) -> list[dict] | None:
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
            return data.get("schemes", [])
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load catalog %s: %s", path, exc)
            return None

    def _normalize_scheme_names(self, schemes: list[dict]) -> list[dict]:
        """Normalize scheme names to short format (e.g., 'lmonocytogenes_1')."""
        from gmlst.database.providers.base import generate_scheme_base_name

        # Group schemes by their base organism
        organism_groups: dict[str, list[dict]] = defaultdict(list)

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

    def _get_all_existing_scheme_names(
        self, exclude_provider: str | None = None
    ) -> set[str]:
        """Get all scheme names from all cached catalogs.

        Args:
            exclude_provider: If specified, skip this provider's catalogs

        Returns:
            Set of all existing scheme names
        """
        existing_names: set[str] = set()

        catalog_dir = self._catalog_dir()
        if not catalog_dir.exists():
            return existing_names

        for catalog_file in catalog_dir.glob("*.json"):
            # Filename format: {provider}.json
            file_provider = catalog_file.stem
            if exclude_provider and file_provider == exclude_provider:
                continue

            try:
                data = json.loads(catalog_file.read_text())
                for scheme in data.get("schemes", []):
                    existing_names.add(scheme.get("scheme_name", ""))
            except (OSError, json.JSONDecodeError):
                continue

        return existing_names

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
        except Exception as e:
            logger.debug("Failed to copy default catalog: %s", e)
        return False

    def save_catalog(self, provider: str, schemes: list[dict]) -> None:
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

        # Get all existing scheme names from other providers
        existing_names = self._get_all_existing_scheme_names(exclude_provider=provider)

        # Check for conflicts and reassign names if needed
        # Group by base name to handle suffix allocation
        base_name_groups: dict[str, list[dict]] = defaultdict(list)
        for scheme in schemes:
            scheme_name = scheme["scheme_name"]
            # Extract base name (e.g., "abaumannii_1" -> "abaumannii")
            if "_" in scheme_name:
                base_name = scheme_name.rsplit("_", 1)[0]
            else:
                base_name = scheme_name
            base_name_groups[base_name].append(scheme)

        # Reassign names ensuring global uniqueness
        # Preprocess existing_names into {base_name: max_suffix} mapping for O(1) lookup
        existing_max_suffix: dict[str, int] = {}
        for existing_name in existing_names:
            if "_" in existing_name:
                try:
                    base, suffix_str = existing_name.rsplit("_", 1)
                    suffix = int(suffix_str)
                    existing_max_suffix[base] = max(
                        existing_max_suffix.get(base, 0), suffix
                    )
                except ValueError:
                    pass  # Not a numbered suffix, skip

        for base_name, group_schemes in base_name_groups.items():
            # Start from the highest existing suffix for this base_name
            max_suffix = existing_max_suffix.get(base_name, 0)

            # Assign new suffixes starting from max_suffix + 1
            for i, scheme in enumerate(group_schemes, start=1):
                new_suffix = max_suffix + i
                old_name = scheme["scheme_name"]
                new_name = f"{base_name}_{new_suffix}"
                scheme["scheme_name"] = new_name
                if old_name != new_name:
                    logger.info(
                        "Renamed scheme '%s' -> '%s' to ensure global uniqueness",
                        old_name,
                        new_name,
                    )

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
    ) -> list[dict]:
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
