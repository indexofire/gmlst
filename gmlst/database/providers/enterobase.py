"""Enterobase provider with HTTP direct download support.

Enterobase provides open HTTP access to schemes at:
  https://enterobase.warwick.ac.uk/schemes/

Each scheme directory contains .fasta.gz allele files and a profiles.list.gz.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import gzip
import json
import logging
import re
from pathlib import Path
from typing import Any

import requests

from gmlst.database.atomic import atomic_write_bytes, atomic_write_text
from gmlst.database.download import DownloadTool, download_file
from gmlst.database.providers.base import SchemeInfo, download_required_files
from gmlst.database.url_guard import assert_public_url
from gmlst.fasta_io import (
    count_fasta_records,
    count_profile_rows,
    is_valid_fasta,
    utc_now_iso,
)

logger = logging.getLogger("gmlst.database.providers.enterobase")

_BASE_URL = "https://enterobase.warwick.ac.uk/schemes"

_SCHEME_ALIASES: dict[str, str] = {
    "senterica_mlst": "Salmonella.Achtman7GeneMLST",
    "senterica_cgmlst": "Salmonella.cgMLSTv2",
    "senterica_rmlst": "Salmonella.rMLST",
    "senterica_wgmlst": "Salmonella.wgMLST",
    "ecoli_mlst": "Escherichia.Achtman7GeneMLST",
    "ecoli_cgmlst": "Escherichia.cgMLSTv1",
    "ecoli_wgmlst": "Escherichia.wgMLST",
    "yersinia_mlst": "Yersinia.Achtman7GeneMLST",
    "yersinia_mcnally": "Yersinia.McNally",
    "yersinia_cgmlst": "Yersinia.cgMLSTv1",
    "yersinia_wgmlst": "Yersinia.wgMLST",
    "klebsiella_mlst": "klebsiella.pasteur7gene",
    "klebsiella_cgmlst": "klebsiella.pasteurcgmlst",
    "moraxella_mlst": "Moraxella.Achtman7GeneMLST",
    "clostridium_mlst": "clostridium.Griffiths",
    "clostridium_cgmlst": "clostridium.cgMLSTv1",
    "clostridium_wgmlst": "clostridium.wgMLST",
    "spneumoniae_cgmlst": "Streptococcus.cgMLSTv1",
    "spneumoniae_wgmlst": "Streptococcus.wgMLSTv1",
    "vibrio_mlst": "Vibrio.Lan7Gene",
    "vibrio_cgmlst": "VIBwgMLST.cgMLSTv1",
    "pluminescens_cgmlst": "Photorhabdus.cgMLSTv1",
}

# Ordered scheme_id prefix -> organism mapping (first match wins).
_ORGANISM_BY_PREFIX: list[tuple[str, str]] = [
    ("senterica", "Salmonella enterica"),
    ("ecoli", "Escherichia coli"),
    ("yenterocolitica", "Yersinia enterocolitica"),
    ("kpneumoniae", "Klebsiella pneumoniae"),
    ("mcatarrhalis", "Moraxella catarrhalis"),
    ("cbotulinum", "Clostridium botulinum"),
    ("spneumoniae", "Streptococcus pneumoniae"),
    ("vibrio", "Vibrio spp."),
    ("pluminescens", "Photorhabdus luminescens"),
]


def _classify_scheme_type(dir_name: str) -> str:
    """Infer scheme type from directory name."""
    lower = dir_name.lower()
    if "cgmlst" in lower:
        return "cgmlst"
    elif "wgmlst" in lower:
        return "wgmlst"
    elif "rmlst" in lower:
        return "rmlst"
    return "mlst"


class EnterobaseProvider:
    """Database provider for Enterobase with HTTP direct download."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    def _auth_headers(self) -> dict[str, str]:
        if self._token:
            return {"Authorization": f"Basic {self._token}"}
        return {}

    @property
    def name(self) -> str:
        return "enterobase"

    @property
    def label(self) -> str:
        return "Enterobase"

    def _discover_remote_directories(self) -> list[str]:
        """Fetch the list of scheme directories from the Enterobase /schemes/ index."""
        try:
            assert_public_url(_BASE_URL + "/")
            resp = requests.get(
                _BASE_URL + "/", timeout=30, headers=self._auth_headers()
            )
            resp.raise_for_status()
            dirs = re.findall(r'href="([^"]+)/"', resp.text)
            return [d for d in dirs if d not in ("../", "..")]
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Failed to discover Enterobase directories: %s", exc)
            return []

    @staticmethod
    def _derive_organism(dir_name: str) -> str:
        genus = dir_name.split(".")[0].lower()
        for prefix, name in _ORGANISM_BY_PREFIX:
            if genus.startswith(prefix.replace("spp", "")):
                return name
        return dir_name.split(".")[0]

    def list_schemes(self, scheme_type: str = "mlst") -> list[SchemeInfo]:
        """Return available Enterobase schemes.

        Discovers scheme directories dynamically from the Enterobase /schemes/
        HTTP index. Falls back to the static _SCHEME_ALIASES if the network is
        unavailable.
        """
        results: list[SchemeInfo] = []
        seen_dirs: set[str] = set()

        remote_dirs = self._discover_remote_directories()
        if remote_dirs:
            source_dirs = remote_dirs
            logger.debug(
                "Discovered %d Enterobase scheme directories from server",
                len(remote_dirs),
            )
        else:
            source_dirs = list(_SCHEME_ALIASES.values())
            logger.debug("Using static aliases (%d dirs)", len(source_dirs))

        for dir_name in source_dirs:
            if dir_name in seen_dirs:
                continue
            seen_dirs.add(dir_name)

            s_type = _classify_scheme_type(dir_name)
            if scheme_type != "all" and s_type != scheme_type:
                continue

            organism = self._derive_organism(dir_name)

            n_loci = None
            # count_loci may fail on restricted/inaccessible dirs — leave n_loci as None
            with contextlib.suppress(OSError, ValueError):
                n_loci = self._count_loci(dir_name)

            results.append(
                SchemeInfo(
                    scheme_name=dir_name,
                    display_name=dir_name.replace(".", " "),
                    organism=organism,
                    scheme_type=s_type,
                    n_loci=n_loci or 0,
                    provider=self.name,
                    extra={"directory": dir_name},
                )
            )

        return results

    def _count_loci(self, dir_name: str) -> int:
        """Count number of loci by listing the scheme HTTP directory."""
        url = f"{_BASE_URL}/{dir_name}/"
        assert_public_url(url)
        resp = requests.get(url, timeout=120, headers=self._auth_headers())
        if resp.status_code == 403:
            logger.warning(
                "[enterobase] Directory '%s' returned 403 Forbidden. "
                "This scheme may require authentication or be restricted.",
                dir_name,
            )
            return 0
        resp.raise_for_status()
        return sum(
            1
            for line in resp.text.split("\n")
            if ".fasta.gz" in line and "href" in line
        )

    def download_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "mlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Download allele FASTAs and ST profiles from Enterobase via HTTP.

        Uses aria2c batch mode for parallel downloading when available.
        All .fasta.gz files are downloaded first, then decompressed to .tfa.
        """
        dir_name = (extra or {}).get("directory")
        if not dir_name:
            resolved = _resolve_enterobase_scheme_name(scheme_name, scheme_type)
            dir_name = _SCHEME_ALIASES[resolved]
        dest_dir.mkdir(parents=True, exist_ok=True)

        logger.info("[enterobase] Downloading %s (%s) …", scheme_name, dir_name)

        loci = self._get_loci(dir_name)
        logger.info("[enterobase] %d loci to download", len(loci))

        # Build URL/dest pairs for batch download
        url_dest_pairs = []
        for locus in loci:
            gz_path = dest_dir / f"{locus}.fasta.gz"
            url = f"{_BASE_URL}/{dir_name}/{locus}.fasta.gz"
            url_dest_pairs.append((url, gz_path))

        # Batch download all .fasta.gz files
        download_required_files(
            url_dest_pairs,
            provider_name=self.name,
            download_tool=download_tool,
            max_connections=max_connections or 4,
        )
        success = len(url_dest_pairs)

        # Decompress downloaded .fasta.gz to .tfa
        logger.info("[enterobase] Decompressing %d files …", success)
        new_locus_meta: dict[str, dict[str, str]] = {}
        for locus in loci:
            gz_path = dest_dir / f"{locus}.fasta.gz"
            tfa_path = dest_dir / f"{locus}.tfa"
            new_locus_meta[locus] = _head_remote_file(
                f"{_BASE_URL}/{dir_name}/{locus}.fasta.gz"
            )
            if gz_path.exists() and not tfa_path.exists():
                try:
                    atomic_write_bytes(tfa_path, gzip.decompress(gz_path.read_bytes()))
                except Exception as exc:
                    raise RuntimeError(
                        f"[enterobase] Failed to decompress {locus}: {exc}"
                    ) from exc
            # Clean up .gz file
            gz_path.unlink(missing_ok=True)

        self._download_profiles(
            dir_name,
            loci,
            dest_dir,
            scheme_name,
            download_tool=download_tool,
            max_connections=max_connections,
        )
        profiles_headers = _head_remote_file(f"{_BASE_URL}/{dir_name}/profiles.list.gz")

        meta = {
            "scheme": scheme_name,
            "provider": self.name,
            "scheme_type": _classify_scheme_type(dir_name),
            "directory": dir_name,
            "downloaded_at": utc_now_iso(),
            "loci": loci,
            "locus_meta": {
                locus: {"records": count_fasta_records(dest_dir / f"{locus}.tfa")}
                for locus in loci
            },
            "profile_meta": {
                "records": count_profile_rows(dest_dir / f"{scheme_name}.txt"),
            },
            "profiles_remote": profiles_headers,
            "locus_remote": new_locus_meta,
        }
        atomic_write_text(dest_dir / ".meta.json", json.dumps(meta, indent=2))
        logger.info("[enterobase] Done → %s", dest_dir)

    def update_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "mlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        dir_name = (extra or {}).get("directory")
        if not dir_name:
            resolved = _resolve_enterobase_scheme_name(scheme_name, scheme_type)
            dir_name = _SCHEME_ALIASES[resolved]
        meta_file = dest_dir / ".meta.json"
        local_meta: dict[str, Any] = {}
        if meta_file.exists():
            local_meta = json.loads(meta_file.read_text())

        profiles_url = f"{_BASE_URL}/{dir_name}/profiles.list.gz"
        profiles_headers = _head_remote_file(profiles_url)
        old_profiles = local_meta.get("profiles_remote", {})

        loci = self._get_loci(dir_name)
        local_loci = set(local_meta.get("loci", []))
        loci_changed = set(loci) != local_loci

        profile_changed = (
            _headers_changed(old_profiles, profiles_headers)
            or not (dest_dir / f"{scheme_name}.txt").exists()
        )

        old_locus_meta = local_meta.get("locus_remote", {})
        changed_loci: list[str] = []
        new_locus_meta: dict[str, dict[str, str]] = {}

        def _fetch_locus_headers(locus: str) -> tuple[str, dict[str, str]]:
            locus_url = f"{_BASE_URL}/{dir_name}/{locus}.fasta.gz"
            return (locus, _head_remote_file(locus_url))

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(_fetch_locus_headers, locus) for locus in loci]
            for future in concurrent.futures.as_completed(futures):
                locus, headers = future.result()
                new_locus_meta[locus] = headers
                local_tfa = dest_dir / f"{locus}.tfa"
                if (
                    _headers_changed(old_locus_meta.get(locus, {}), headers)
                    or not local_tfa.exists()
                    or not is_valid_fasta(local_tfa)
                ):
                    changed_loci.append(locus)

        if changed_loci:
            logger.info(
                "[enterobase] Updating %d/%d loci in parallel ...",
                len(changed_loci),
                len(loci),
            )
            pairs = [
                (
                    f"{_BASE_URL}/{dir_name}/{locus}.fasta.gz",
                    dest_dir / f"{locus}.fasta.gz",
                )
                for locus in changed_loci
            ]
            download_required_files(
                pairs,
                provider_name=self.name,
                download_tool=download_tool,
                max_connections=max_connections or 4,
            )

            for locus in changed_loci:
                gz_path = dest_dir / f"{locus}.fasta.gz"
                tfa_path = dest_dir / f"{locus}.tfa"
                atomic_write_bytes(tfa_path, gzip.decompress(gz_path.read_bytes()))
                gz_path.unlink(missing_ok=True)
                if not is_valid_fasta(tfa_path):
                    raise RuntimeError(
                        f"[enterobase] Invalid FASTA content after update: {locus}"
                    )

        if profile_changed:
            self._download_profiles(
                dir_name,
                loci,
                dest_dir,
                scheme_name,
                download_tool=download_tool,
                max_connections=max_connections,
            )

        now = utc_now_iso()

        meta = {
            "scheme": scheme_name,
            "provider": self.name,
            "scheme_type": _classify_scheme_type(dir_name),
            "directory": dir_name,
            "downloaded_at": local_meta.get("downloaded_at", now),
            "updated_at": now,
            "loci": loci,
            "locus_meta": {
                locus: {"records": count_fasta_records(dest_dir / f"{locus}.tfa")}
                for locus in loci
            },
            "profile_meta": {
                "records": count_profile_rows(dest_dir / f"{scheme_name}.txt"),
            },
            "profiles_remote": profiles_headers,
            "locus_remote": new_locus_meta,
        }
        atomic_write_text(meta_file, json.dumps(meta, indent=2))

        return bool(changed_loci or profile_changed or loci_changed)

    def _get_loci(self, dir_name: str) -> list[str]:
        """Get list of locus names from the scheme HTTP directory listing."""
        url = f"{_BASE_URL}/{dir_name}/"
        assert_public_url(url)
        resp = requests.get(url, timeout=30, headers=self._auth_headers())
        if resp.status_code == 403:
            raise RuntimeError(
                f"Enterobase returned 403 Forbidden for '{dir_name}'. "
                "This scheme may require authentication (--token) or "
                "be unavailable. Try the same scheme from another provider."
            )
        resp.raise_for_status()

        loci = []
        for line in resp.text.split("\n"):
            match = re.search(r'href="([^"]+)\.fasta\.gz"', line)
            if match:
                locus_name = match.group(1)
                if not locus_name.endswith("_ref") and not locus_name.endswith(".ref"):
                    loci.append(locus_name)
        return sorted(loci)

    def _download_profiles(
        self,
        dir_name: str,
        loci: list[str],
        dest_dir: Path,
        scheme_name: str,
        *,
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
    ) -> None:
        """Download and convert ST profiles to MLST format."""
        dest_file = dest_dir / f"{scheme_name}.txt"
        if dest_file.exists():
            logger.debug("Profiles already exist")
            return

        gz_path = dest_dir / "profiles.list.gz"
        url = f"{_BASE_URL}/{dir_name}/profiles.list.gz"
        logger.info("[enterobase] Downloading ST profiles …")

        try:
            download_file(
                url,
                gz_path,
                tool=download_tool,
                max_connections=max_connections,
            )
            profile_data = gzip.decompress(gz_path.read_bytes()).decode("utf-8")
        except Exception as exc:
            raise RuntimeError(
                f"[enterobase] Failed to download profiles: {exc}"
            ) from exc
        finally:
            gz_path.unlink(missing_ok=True)

        lines = profile_data.strip().split("\n")
        if not lines:
            return

        header = lines[0].split("\t")
        output_lines = ["ST\t" + "\t".join(loci)]
        for line in lines[1:]:
            fields = line.split("\t")
            if len(fields) >= len(header):
                st = fields[0]
                allele_map = dict(zip(header[1:], fields[1:], strict=False))
                allele_values = [allele_map.get(locus, "-") for locus in loci]
                output_lines.append(st + "\t" + "\t".join(allele_values))

        atomic_write_text(dest_file, "\n".join(output_lines))


def _head_remote_file(url: str) -> dict[str, str]:
    assert_public_url(url)
    resp = requests.head(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return {
        "etag": resp.headers.get("ETag", ""),
        "last_modified": resp.headers.get("Last-Modified", ""),
        "content_length": resp.headers.get("Content-Length", ""),
    }


def _headers_changed(old: dict[str, Any], new: dict[str, str]) -> bool:
    return (
        str(old.get("etag", "")) != new.get("etag", "")
        or str(old.get("last_modified", "")) != new.get("last_modified", "")
        or str(old.get("content_length", "")) != new.get("content_length", "")
    )


def _resolve_enterobase_scheme_name(scheme_name: str, scheme_type: str) -> str:
    if scheme_name in _SCHEME_ALIASES:
        return scheme_name
    typed = f"{scheme_name}_{scheme_type}"
    if typed in _SCHEME_ALIASES:
        return typed
    raise ValueError(
        f"Unknown Enterobase scheme: {scheme_name}. "
        "Run 'gmlst scheme list -p enterobase' to see available schemes."
    )
