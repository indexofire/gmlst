"""BIGSdb provider — covers both PubMLST and Pasteur (identical REST API).

API structure (verified against both hosts):
  GET <base>/               → list of organism groups:
    [{"name": "saureus", "description": "...", "databases": [
        {"name": "pubmlst_saureus_isolates", "href": "...", "description": "..."},
        {"name": "pubmlst_saureus_seqdef",   "href": "...", "description": "..."},
    ]}, ...]

  GET <seqdef>/schemes → {"schemes": [{"scheme": "<url>", "description": "MLST"}, ...]}
                               "description": "MLST", "locus_count": 7, ...}
  #  GET <locus_url>/alleles_fasta  → FASTA text

scheme_type mapping:
  "mlst"   → description contains "MLST" (case-insensitive), locus_count <= 10
  "cgmlst" → description contains "cgMLST" or "core genome"
  "wgmlst" → description contains "wgMLST" or "whole genome"
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
from pathlib import Path
from typing import Any

from gmlst.database.atomic import atomic_write_text
from gmlst.database.download import (
    DownloadTool,
    download_file,
    fetch_json,
)
from gmlst.database.providers.base import (
    SchemeInfo,
    download_required_files,
    generate_scheme_base_name,
)
from gmlst.fasta_io import count_fasta_records, count_profile_rows, utc_now_iso

logger = logging.getLogger(__name__)


# How to classify schemes by description keyword
_TYPE_KEYWORDS: dict[str, list[str]] = {
    "mlst": ["mlst"],
    "cgmlst": ["cgmlst", "core genome mlst", "core-genome"],
    "wgmlst": ["wgmlst", "whole genome mlst", "whole-genome"],
}


def _load_mapping_json(filename: str) -> dict[str, Any]:
    """Load a JSON mapping file from package data, filtering keys starting with '_'."""
    try:
        import importlib.resources as pkg_resources

        mapping_path = Path(str(pkg_resources.files("gmlst") / "data" / filename))
        if mapping_path.is_file():
            with mapping_path.open() as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {k: v for k, v in data.items() if not k.startswith("_")}
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.warning("Could not load %s: %s", filename, e)
    return {}


# Load organism name mapping for all providers
_ORGANISM_MAPPINGS: dict[str, dict[str, str]] = _load_mapping_json(
    "organism_mapping.json"
)
_ORGANISM_MAPPING: dict[str, str] = _load_mapping_json("pasteur_organism_mapping.json")


class BigSdbProvider:
    """Database provider for BIGSdb-powered REST APIs (PubMLST, Pasteur)."""

    def __init__(self, name: str, base_url: str, label: str) -> None:
        self._name = name
        self._base_url = base_url.rstrip("/")
        self._label = label

    def _auth_headers(self) -> dict[str, str]:
        env_var = f"GMLST_{self._name.upper()}_API_KEY"
        key = os.getenv(env_var, "")
        if key:
            return {"X-API-Key": key}
        return {}

    # ------------------------------------------------------------------
    # Provider Protocol
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def label(self) -> str:
        return self._label

    def list_schemes(self, scheme_type: str = "mlst") -> list[SchemeInfo]:
        """Return all schemes of *scheme_type* available on this BIGSdb host."""
        orgs: list[dict[str, Any]] = _get_json(  # type: ignore[assignment]  # root endpoint returns list at runtime
            self._base_url, headers=self._auth_headers()
        )

        # First pass: collect all schemes with their base names
        raw_schemes: list[dict[str, Any]] = []

        for org in orgs:
            # Get all seqdef databases for this organism
            seqdef_dbs = _find_seqdef_databases(org)
            if not seqdef_dbs:
                continue

            org_name = org.get("name", "")

            for seqdef_info in seqdef_dbs:
                seqdef_url = seqdef_info["url"]
                # Extract organism name from database description
                db_desc = seqdef_info.get("description", "")
                organism_name = _extract_organism_name(db_desc) or org.get(
                    "description", org_name
                )

                # Apply organism name mapping if available for this provider
                provider_mappings = _ORGANISM_MAPPINGS.get(self._name, {})
                if org_name in provider_mappings:
                    organism_name = provider_mappings[org_name]

                # Generate short base name for scheme naming (e.g., "lmonocytogenes")
                base_name = generate_scheme_base_name(organism_name)

                try:
                    schemes = _fetch_schemes(seqdef_url)
                except (RuntimeError, OSError) as exc:
                    logger.warning(
                        "Could not fetch schemes for %s: %s", seqdef_url, exc
                    )
                    continue

                for scheme_entry in schemes:
                    s_url = scheme_entry.get("scheme", "")
                    s_desc = scheme_entry.get("description", "")
                    s_type = _classify_scheme_type(s_desc)

                    if scheme_type != "all" and s_type != scheme_type:
                        continue
                    if scheme_type == "all" and s_type == "other":
                        continue

                    # Fetch locus count
                    n_loci = scheme_entry.get("locus_count", 0)
                    if not n_loci and s_url:
                        try:
                            detail = _get_json(s_url, headers=self._auth_headers())
                            if isinstance(detail, dict):
                                n_loci = detail.get(
                                    "locus_count", len(detail.get("loci", []))
                                )
                        except (OSError, ValueError) as exc:
                            logger.warning(
                                "Failed to fetch locus count for %s: %s", s_url, exc
                            )

                    raw_schemes.append(
                        {
                            "base_name": base_name,
                            "organism_name": organism_name,
                            "s_desc": s_desc,
                            "s_type": s_type,
                            "n_loci": n_loci,
                            "s_url": s_url,
                            "seqdef_url": seqdef_url,
                        }
                    )

        # Second pass: assign sequential numbers to each base_name group
        from collections import defaultdict

        name_counters: dict[str, int] = defaultdict(int)

        results: list[SchemeInfo] = []
        for raw in raw_schemes:
            base_name = raw["base_name"]
            name_counters[base_name] += 1
            scheme_name = f"{base_name}_{name_counters[base_name]}"

            results.append(
                SchemeInfo(
                    scheme_name=scheme_name,
                    display_name=f"{raw['organism_name']} {raw['s_desc']}".strip(),
                    organism=raw["organism_name"],
                    scheme_type=raw["s_type"],
                    n_loci=raw["n_loci"],
                    provider=self._name,
                    extra={
                        "seqdef_url": raw["seqdef_url"],
                        "scheme_url": raw["s_url"],
                    },
                )
            )

        return results

    def _fetch_scheme_detail(
        self, scheme_name: str, scheme_type: str
    ) -> tuple[str, str, dict]:
        """Resolve seqdef/scheme URLs and fetch validated scheme detail.

        Returns ``(seqdef_url, scheme_url, scheme_detail)`` where
        *scheme_detail* is guaranteed to be a dict with a non-empty ``loci``
        list.
        """
        seqdef_url, matched_db = self._resolve_seqdef_url(scheme_name)
        logger.info("[%s] Resolved seqdef: %s (%s)", self._name, matched_db, seqdef_url)

        scheme_url = _resolve_scheme_url(self, seqdef_url, scheme_name, scheme_type)
        logger.info("[%s] Using scheme: %s", self._name, scheme_url)

        scheme_detail = _get_json(scheme_url, headers=self._auth_headers())
        if not isinstance(scheme_detail, dict):
            raise ValueError(f"Unexpected scheme response for '{scheme_name}'")
        loci_urls: list[str] = scheme_detail.get("loci", [])
        if not loci_urls:
            raise ValueError(
                f"No loci found in scheme '{scheme_url}' for '{scheme_name}'"
            )
        return seqdef_url, scheme_url, scheme_detail

    def download_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "mlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Download allele FASTAs + ST profile for *scheme_name*."""
        dest_dir.mkdir(parents=True, exist_ok=True)

        seqdef_url, scheme_url, scheme_detail = self._fetch_scheme_detail(
            scheme_name, scheme_type
        )
        loci_urls: list[str] = scheme_detail.get("loci", [])

        profiles_csv_url = scheme_detail.get("profiles_csv")
        profile_dest = dest_dir / f"{scheme_name}.txt"
        profile_tmp = dest_dir / f"{scheme_name}.txt.tmp"
        profile_future: concurrent.futures.Future[None] | None = None
        profile_executor: concurrent.futures.ThreadPoolExecutor | None = None
        if profiles_csv_url and not profile_dest.exists():
            logger.info("[%s] Downloading ST profile in parallel …", self._name)
            profile_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            profile_future = profile_executor.submit(
                _download_file,
                profiles_csv_url,
                profile_tmp,
                tool=download_tool,
                max_connections=max_connections,
            )
        elif not profiles_csv_url:
            logger.warning("[%s] No profiles_csv for '%s'", self._name, scheme_name)

        # Download allele FASTAs
        logger.info(
            "[%s] Downloading %d loci for '%s' …",
            self._name,
            len(loci_urls),
            scheme_name,
        )
        url_dest_pairs: list[tuple[str, Path]] = []
        for locus_url in loci_urls:
            locus_name = locus_url.rstrip("/").split("/")[-1]
            dest_file = dest_dir / f"{locus_name}.tfa"
            if dest_file.exists():
                logger.debug("Skipping %s (already exists)", locus_name)
                continue
            url_dest_pairs.append((f"{locus_url}/alleles_fasta", dest_file))

        if url_dest_pairs:
            logger.info(
                "[%s] Downloading %d locus FASTA files ...",
                self._name,
                len(url_dest_pairs),
            )
            download_required_files(
                url_dest_pairs,
                provider_name=self._name,
                download_tool=download_tool,
                max_connections=max_connections or 4,
                headers=self._auth_headers(),
            )
        if profile_future is not None:
            try:
                profile_future.result()
                profile_tmp.replace(profile_dest)
            except (OSError, RuntimeError, ValueError):
                profile_tmp.unlink(missing_ok=True)
                raise
            finally:
                assert profile_executor is not None
                profile_executor.shutdown(wait=True)

        # Write metadata
        meta = {
            "scheme": scheme_name,
            "provider": self._name,
            "scheme_type": scheme_type,
            "seqdef_url": seqdef_url,
            "scheme_url": scheme_url,
            "downloaded_at": utc_now_iso(),
            "loci": [u.rstrip("/").split("/")[-1] for u in loci_urls],
            "locus_meta": {
                path.stem: {
                    "records": count_fasta_records(path),
                    "last_updated": "",
                }
                for path in sorted(dest_dir.glob("*.tfa"))
            },
            "profile_meta": {
                "records": count_profile_rows(profile_dest),
                "last_updated": str(scheme_detail.get("last_updated", "")),
                "last_added": str(scheme_detail.get("last_added", "")),
            },
        }
        atomic_write_text(dest_dir / ".meta.json", json.dumps(meta, indent=2))
        logger.info("[%s] Done → %s", self._name, dest_dir)

    def update_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "mlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        dest_dir.mkdir(parents=True, exist_ok=True)

        meta_file = dest_dir / ".meta.json"
        local_meta: dict[str, Any] = {}
        if meta_file.exists():
            local_meta = json.loads(meta_file.read_text())

        seqdef_url, scheme_url, scheme_detail = self._fetch_scheme_detail(
            scheme_name, scheme_type
        )
        loci_urls: list[str] = scheme_detail.get("loci", [])

        old_locus_meta = local_meta.get("locus_meta", {})
        new_locus_meta: dict[str, dict[str, str | int]] = {}
        changed_loci: list[str] = []
        all_loci = [u.rstrip("/").split("/")[-1] for u in loci_urls]

        for locus_url in loci_urls:
            locus_name = locus_url.rstrip("/").split("/")[-1]
            allele_info = _get_json(
                f"{locus_url}/alleles", headers=self._auth_headers()
            )
            if not isinstance(allele_info, dict):
                raise ValueError(f"Unexpected locus response for '{locus_name}'")
            records = int(allele_info.get("records", 0))
            last_updated = str(allele_info.get("last_updated", ""))
            new_locus_meta[locus_name] = {
                "records": records,
                "last_updated": last_updated,
            }

            old = old_locus_meta.get(locus_name, {})
            local_file = dest_dir / f"{locus_name}.tfa"
            old_records = old.get("records", None)
            old_last_updated = str(old.get("last_updated", ""))
            if (
                not local_file.exists()
                or count_fasta_records(local_file) < records
                or (old_records is not None and int(old_records) != records)
                or (old_last_updated and old_last_updated != last_updated)
            ):
                changed_loci.append(locus_name)

        url_dest_pairs: list[tuple[str, Path]] = []
        for locus_name in changed_loci:
            tmp_file = dest_dir / f"{locus_name}.tfa.tmp"
            url_dest_pairs.append(
                (f"{seqdef_url}/loci/{locus_name}/alleles_fasta", tmp_file)
            )

        if url_dest_pairs:
            logger.info(
                "[%s] Updating %d/%d loci in parallel ...",
                self._name,
                len(url_dest_pairs),
                len(all_loci),
            )
            download_required_files(
                url_dest_pairs,
                provider_name=self._name,
                download_tool=download_tool,
                max_connections=max_connections or 4,
                headers=self._auth_headers(),
            )

            for _, tmp_file in url_dest_pairs:
                locus_name = tmp_file.name.removesuffix(".tfa.tmp")
                expected = int(new_locus_meta[locus_name]["records"])
                actual = count_fasta_records(tmp_file)
                if actual < expected:
                    raise RuntimeError(
                        f"[{self._name}] Incomplete locus download for {locus_name}: "
                        f"expected >= {expected} alleles, got {actual}"
                    )
                final_file = tmp_file.with_suffix("")
                tmp_file.replace(final_file)

        old_profile_meta = local_meta.get("profile_meta", {})
        new_profile_meta = {
            "records": int(scheme_detail.get("records", 0)),
            "last_updated": str(scheme_detail.get("last_updated", "")),
            "last_added": str(scheme_detail.get("last_added", "")),
        }
        profile_dest = dest_dir / f"{scheme_name}.txt"
        local_profile_records = count_profile_rows(profile_dest)
        old_profile_records = old_profile_meta.get("records", None)
        old_profile_updated = str(old_profile_meta.get("last_updated", ""))
        profile_changed = (
            not profile_dest.exists()
            or local_profile_records < new_profile_meta["records"]
            or (
                old_profile_records is not None
                and int(old_profile_records) != new_profile_meta["records"]
            )
            or (
                old_profile_updated
                and old_profile_updated != new_profile_meta["last_updated"]
            )
        )
        profiles_csv_url = scheme_detail.get("profiles_csv")
        if profile_changed and profiles_csv_url:
            tmp_profile = dest_dir / f"{scheme_name}.txt.tmp"
            _download_file(
                profiles_csv_url,
                tmp_profile,
                tool=download_tool,
                max_connections=max_connections,
                headers=self._auth_headers(),
            )
            tmp_profile.replace(profile_dest)

        changed = bool(changed_loci or profile_changed)
        needs_metadata_backfill = not isinstance(
            local_meta.get("locus_meta", None), dict
        ) or not isinstance(local_meta.get("profile_meta", None), dict)
        if changed or needs_metadata_backfill:
            now = utc_now_iso()
            updated_meta = {
                "scheme": scheme_name,
                "provider": self._name,
                "scheme_type": scheme_type,
                "seqdef_url": seqdef_url,
                "scheme_url": scheme_url,
                "downloaded_at": local_meta.get("downloaded_at", now),
                "updated_at": now,
                "loci": all_loci,
                "locus_meta": new_locus_meta,
                "profile_meta": new_profile_meta,
            }
            atomic_write_text(meta_file, json.dumps(updated_meta, indent=2))

        return changed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_seqdef_url(self, scheme_name: str) -> tuple[str, str]:
        """Match *scheme_name* to a seqdef database URL.

        Returns (href, db_name).  Priority:
        1. ``pubmlst_<scheme_name>_seqdef`` exact match
        2. ``scheme_name`` substring in db name
        3. ``scheme_name`` substring in organism description

        Handles suffixed scheme names (e.g., 'bcc_1' -> 'bcc').
        """
        orgs: list[dict[str, Any]] = _get_json(  # type: ignore[assignment]  # root endpoint returns list at runtime
            self._base_url, headers=self._auth_headers()
        )

        # Remove suffix (_1, _2, etc.) if present
        base_scheme_name = scheme_name
        if "_" in scheme_name:
            parts = scheme_name.rsplit("_", 1)
            if parts[1].isdigit():
                base_scheme_name = parts[0]

        lower = base_scheme_name.lower()
        provider_mappings = _ORGANISM_MAPPINGS.get(self._name, {})
        candidates: list[tuple[int, str, str]] = []

        for org in orgs:
            org_name = str(org.get("name", ""))
            org_description = str(org.get("description", ""))

            mapped_organism = provider_mappings.get(org_name, "")
            mapped_base_name = (
                generate_scheme_base_name(mapped_organism).lower()
                if mapped_organism
                else ""
            )

            for db in org.get("databases", []):
                db_name: str = db.get("name", "")
                href: str = db.get("href", "")
                if "seqdef" not in db_name:
                    continue
                if db_name == f"pubmlst_{lower}_seqdef" or db_name == base_scheme_name:
                    candidates.append((1, href, db_name))
                elif mapped_base_name and lower == mapped_base_name:
                    candidates.append((2, href, db_name))
                elif lower in db_name.lower():
                    candidates.append((3, href, db_name))
                elif (
                    lower in org_description.lower() or lower in mapped_organism.lower()
                ):
                    candidates.append((4, href, db_name))

        if not candidates:
            raise ValueError(
                f"[{self._name}] Cannot find seqdef database for '{scheme_name}'. "
                "Run `gmlst scheme list` to browse available schemes."
            )

        candidates.sort(key=lambda t: t[0])
        _, href, db_name = candidates[0]
        return href, db_name


def _resolve_scheme_url(
    self, seqdef_url: str, scheme_name: str, scheme_type: str
) -> str:
    """Find the URL for the best-matching scheme within *seqdef_url*."""
    schemes = _fetch_schemes(seqdef_url)

    target_index: int | None = None
    if "_" in scheme_name:
        suffix = scheme_name.rsplit("_", 1)[1]
        if suffix.isdigit():
            target_index = int(suffix)

    if target_index is not None:
        typed_schemes = [
            entry
            for entry in schemes
            if _classify_scheme_type(entry.get("description", "").lower())
            == scheme_type
        ]
        if 1 <= target_index <= len(typed_schemes):
            return str(typed_schemes[target_index - 1]["scheme"])

    for entry in schemes:
        desc = entry.get("description", "").lower()
        if _classify_scheme_type(desc) == scheme_type:
            return entry["scheme"]

    if schemes:
        logger.warning(
            "[%s] No scheme matching type '%s' for '%s', using first scheme: %s",
            self._name,
            scheme_type,
            scheme_name,
            schemes[0].get("description", ""),
        )
        return schemes[0]["scheme"]

    raise ValueError(f"[{self._name}] No schemes found at {seqdef_url}/schemes")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _find_seqdef_databases(org: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all seqdef databases from an organism entry.

    Returns list of dicts with 'url', 'description' and 'name' keys.
    """
    results = []
    for db in org.get("databases", []):
        if "seqdef" in db.get("name", ""):
            results.append(
                {
                    "url": db.get("href", ""),
                    "description": db.get("description", ""),
                    "name": db.get("name", ""),
                }
            )
    return results


def _extract_organism_name(db_description: str) -> str | None:
    """Extract organism name from database description.

    Examples:
        "Staphylococcus aureus sequence/profile definitions" -> "Staphylococcus aureus"
        "Escherichia coli MLST" -> "Escherichia coli"

    Returns None if no clear organism name can be extracted.
    """
    if not db_description:
        return None

    # Common suffixes to strip
    suffixes = [
        " sequence/profile definitions",
        " sequence definitions",
        " profile definitions",
        " MLST",
        " cgMLST",
        " wgMLST",
    ]

    name = db_description
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break

    name = name.strip()
    # Return None if we ended up with something too short or generic
    if len(name) < 3 or name.endswith("spp."):
        return None

    return name


def _fetch_schemes(seqdef_url: str) -> list[dict[str, Any]]:
    """Return the list of scheme dicts from ``<seqdef>/schemes``."""
    data = _get_json(f"{seqdef_url}/schemes")
    return data.get("schemes", [])  # type: ignore[union-attr]  # _fetch_schemes is only called on /schemes endpoints which return a dict


_NON_TYPING_KEYWORDS = [
    "pgmlst",
    "agmlst",
    "vmlst",
    "pmlst",
    "virulence",
    "resistance",
    "antimicrobial",
    "antibiotic",
    "pathogenicity",
    "plasmid mlst",
    "genoser",
]


def _classify_scheme_type(description: str) -> str:
    """Map a scheme description string to a canonical scheme_type.

    Non-typing schemes (virulence, resistance, plasmid, pathogenicity) are
    filtered to 'other' first. Then specific typing subtypes (cgmlst, wgmlst)
    are checked before the generic mlst fallback.
    """
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in _NON_TYPING_KEYWORDS):
        return "other"
    for stype in ("wgmlst", "cgmlst", "mlst"):
        if any(kw in desc_lower for kw in _TYPE_KEYWORDS[stype]):
            return stype
    return "other"


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict | list:
    """Fetch a JSON API endpoint with retry (delegates to download.fetch_json)."""
    return fetch_json(url, headers=headers)


def _download_file(
    url: str,
    dest: Path,
    *,
    tool: DownloadTool = "auto",
    max_connections: int | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Download a file with streaming and retry."""
    download_file(
        url,
        dest,
        tool=tool,
        max_connections=max_connections,
        headers=headers,
    )
