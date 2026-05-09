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
import time
from pathlib import Path

import requests

from gmlst.database.atomic import atomic_write_bytes, atomic_write_text
from gmlst.database.download import DownloadTool, download_file
from gmlst.database.providers.base import SchemeInfo, download_required_files

logger = logging.getLogger("gmlst.database.providers.enterobase")

_BASE_URL = "https://enterobase.warwick.ac.uk/schemes"

# Scheme mapping: scheme_id -> directory name
# Note: Includes both catalog names (ecoli_1) and legacy names (ecoli_mlst)
_SCHEME_MAP: dict[str, str] = {
    # Salmonella
    "senterica_1": "Salmonella.Achtman7GeneMLST",
    "senterica_2": "Salmonella.cgMLSTv2",
    "senterica_3": "Salmonella.rMLST",
    "senterica_4": "Salmonella.wgMLST",
    "senterica_mlst": "Salmonella.Achtman7GeneMLST",
    "senterica_cgmlst": "Salmonella.cgMLSTv2",
    "senterica_rmlst": "Salmonella.rMLST",
    "senterica_wgmlst": "Salmonella.wgMLST",
    # E. coli
    "ecoli_1": "Escherichia.Achtman7GeneMLST",
    "ecoli_2": "Escherichia.cgMLSTv1",
    "ecoli_3": "Escherichia.wgMLST",
    "ecoli_mlst": "Escherichia.Achtman7GeneMLST",
    "ecoli_cgmlst": "Escherichia.cgMLSTv1",
    "ecoli_wgmlst": "Escherichia.wgMLST",
    # Yersinia
    "yenterocolitica_1": "Yersinia.Achtman7GeneMLST",
    "yenterocolitica_2": "Yersinia.McNally",
    "yenterocolitica_3": "Yersinia.cgMLSTv1",
    "yenterocolitica_4": "Yersinia.wgMLST",
    "yenterocolitica_mlst": "Yersinia.Achtman7GeneMLST",
    "yenterocolitica_mcnally": "Yersinia.McNally",
    "yenterocolitica_cgmlst": "Yersinia.cgMLSTv1",
    "yenterocolitica_wgmlst": "Yersinia.wgMLST",
    # Klebsiella
    "kpneumoniae_1": "klebsiella.pasteur7gene",
    "kpneumoniae_2": "klebsiella.pasteurcgmlst",
    "kpneumoniae_mlst": "klebsiella.pasteur7gene",
    "kpneumoniae_cgmlst": "klebsiella.pasteurcgmlst",
    # Moraxella
    "mcatarrhalis_1": "Moraxella.Achtman7GeneMLST",
    "mcatarrhalis_mlst": "Moraxella.Achtman7GeneMLST",
    # Clostridium
    "cbotulinum_1": "clostridium.Griffiths",
    "cbotulinum_2": "clostridium.Griffiths_MLST",
    "cbotulinum_3": "clostridium.cgMLSTv1",
    "cbotulinum_4": "clostridium.wgMLST",
    "cbotulinum_mlst": "clostridium.Griffiths",
    "cbotulinum_griffiths": "clostridium.Griffiths_MLST",
    "cbotulinum_cgmlst": "clostridium.cgMLSTv1",
    "cbotulinum_wgmlst": "clostridium.wgMLST",
    # Streptococcus
    "spneumoniae_1": "Streptococcus.cgMLSTv1",
    "spneumoniae_2": "Streptococcus.wgMLSTv1",
    "spneumoniae_cgmlst": "Streptococcus.cgMLSTv1",
    "spneumoniae_wgmlst": "Streptococcus.wgMLSTv1",
    # Vibrio
    "vibrio_1": "Vibrio.Lan7Gene",
    "vibrio_2": "VIBwgMLST.cgMLSTv1",
    "vibrio_mlst": "Vibrio.Lan7Gene",
    "vibrio_cgmlst": "VIBwgMLST.cgMLSTv1",
    # Photorhabdus
    "pluminescens_1": "Photorhabdus.cgMLSTv1",
    "pluminescens_cgmlst": "Photorhabdus.cgMLSTv1",
}

_LEGACY_SCHEME_ALIASES: dict[str, str] = {
    "vibriospp_1": "vibrio_1",
    "vibriospp_2": "vibrio_2",
}


def _classify_scheme_type(dir_name: str) -> str:
    """Infer scheme type from directory name."""
    lower = dir_name.lower()
    if "wgmlst" in lower:
        return "wgmlst"
    elif "cgmlst" in lower:
        return "cgmlst"
    elif "rmlst" in lower:
        return "rmlst"
    return "mlst"


class EnterobaseProvider:
    """Database provider for Enterobase with HTTP direct download."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    @property
    def name(self) -> str:
        return "enterobase"

    @property
    def label(self) -> str:
        return "Enterobase"

    def list_schemes(self, scheme_type: str = "mlst") -> list[SchemeInfo]:
        """Return available Enterobase schemes."""
        results: list[SchemeInfo] = []

        for scheme_id, dir_name in _SCHEME_MAP.items():
            s_type = _classify_scheme_type(dir_name)
            if scheme_type != "all" and s_type != scheme_type:
                continue

            if scheme_id.startswith("senterica"):
                organism = "Salmonella enterica"
            elif scheme_id.startswith("ecoli"):
                organism = "Escherichia coli"
            elif scheme_id.startswith("yenterocolitica"):
                organism = "Yersinia enterocolitica"
            elif scheme_id.startswith("kpneumoniae"):
                organism = "Klebsiella pneumoniae"
            elif scheme_id.startswith("mcatarrhalis"):
                organism = "Moraxella catarrhalis"
            elif scheme_id.startswith("cbotulinum"):
                organism = "Clostridium botulinum"
            elif scheme_id.startswith("spneumoniae"):
                organism = "Streptococcus pneumoniae"
            elif scheme_id.startswith("vibrio"):
                organism = "Vibrio spp."
            elif scheme_id.startswith("pluminescens"):
                organism = "Photorhabdus luminescens"
            else:
                organism = dir_name.split(".")[0]

            n_loci = None
            with contextlib.suppress(OSError, ValueError):
                n_loci = self._count_loci(dir_name)

            results.append(
                SchemeInfo(
                    scheme_name=scheme_id,
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
        resp = requests.get(url, timeout=120)
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
    ) -> None:
        """Download allele FASTAs and ST profiles from Enterobase via HTTP.

        Uses aria2c batch mode for parallel downloading when available.
        All .fasta.gz files are downloaded first, then decompressed to .tfa.
        """
        scheme_name = _resolve_enterobase_scheme_name(scheme_name, scheme_type)

        dir_name = _SCHEME_MAP[scheme_name]
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
            max_connections=max_connections or 16,
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
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "loci": loci,
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
    ) -> bool:
        scheme_name = _resolve_enterobase_scheme_name(scheme_name, scheme_type)

        dest_dir.mkdir(parents=True, exist_ok=True)
        dir_name = _SCHEME_MAP[scheme_name]
        meta_file = dest_dir / ".meta.json"
        local_meta: dict = {}
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
                    or not _is_valid_fasta_file(local_tfa)
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
                max_connections=max_connections or 16,
            )

            for locus in changed_loci:
                gz_path = dest_dir / f"{locus}.fasta.gz"
                tfa_path = dest_dir / f"{locus}.tfa"
                atomic_write_bytes(tfa_path, gzip.decompress(gz_path.read_bytes()))
                gz_path.unlink(missing_ok=True)
                if not _is_valid_fasta_file(tfa_path):
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

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        meta = {
            "scheme": scheme_name,
            "provider": self.name,
            "scheme_type": _classify_scheme_type(dir_name),
            "directory": dir_name,
            "downloaded_at": local_meta.get("downloaded_at", now),
            "updated_at": now,
            "loci": loci,
            "profiles_remote": profiles_headers,
            "locus_remote": new_locus_meta,
        }
        atomic_write_text(meta_file, json.dumps(meta, indent=2))

        return bool(changed_loci or profile_changed or loci_changed)

    def _get_loci(self, dir_name: str) -> list[str]:
        """Get list of locus names from the scheme HTTP directory listing."""
        url = f"{_BASE_URL}/{dir_name}/"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        loci = []
        for line in resp.text.split("\n"):
            match = re.search(r'href="([^"]+)\.fasta\.gz"', line)
            if match:
                locus_name = match.group(1)
                if not locus_name.endswith("_ref") and not locus_name.endswith(".ref"):
                    loci.append(locus_name)
        return sorted(loci)

    def _download_locus(
        self,
        dir_name: str,
        locus: str,
        dest_dir: Path,
        *,
        download_tool: DownloadTool = "auto",
    ) -> None:
        """Download a single locus .fasta.gz and decompress to .tfa."""
        dest_file = dest_dir / f"{locus}.tfa"
        if dest_file.exists():
            logger.debug("Skipping %s (already exists)", locus)
            return

        gz_path = dest_dir / f"{locus}.fasta.gz"
        url = f"{_BASE_URL}/{dir_name}/{locus}.fasta.gz"
        logger.info("  Downloading %s …", locus)

        try:
            download_file(url, gz_path, tool=download_tool)
            atomic_write_bytes(dest_file, gzip.decompress(gz_path.read_bytes()))
        finally:
            gz_path.unlink(missing_ok=True)

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
    resp = requests.head(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return {
        "etag": resp.headers.get("ETag", ""),
        "last_modified": resp.headers.get("Last-Modified", ""),
        "content_length": resp.headers.get("Content-Length", ""),
    }


def _headers_changed(old: dict, new: dict[str, str]) -> bool:
    return (
        str(old.get("etag", "")) != new.get("etag", "")
        or str(old.get("last_modified", "")) != new.get("last_modified", "")
        or str(old.get("content_length", "")) != new.get("content_length", "")
    )


def _is_valid_fasta_file(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    has_header = False
    has_sequence = False
    with path.open() as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                has_header = True
                continue
            has_sequence = True
    return has_header and has_sequence


def _resolve_enterobase_scheme_name(scheme_name: str, scheme_type: str) -> str:
    candidate = _LEGACY_SCHEME_ALIASES.get(scheme_name, scheme_name)
    if candidate in _SCHEME_MAP:
        return candidate

    typed_candidate = _LEGACY_SCHEME_ALIASES.get(
        f"{scheme_name}_{scheme_type}", f"{scheme_name}_{scheme_type}"
    )
    if typed_candidate in _SCHEME_MAP:
        return typed_candidate

    raise ValueError(
        f"Unknown Enterobase scheme: {scheme_name}. "
        "Run 'gmlst scheme list -p enterobase' to see available schemes."
    )
