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
from gmlst.database.download import (
    DownloadTool,
    download_file,
    fetch_with_retry,
)
from gmlst.database.providers.base import SchemeInfo, download_required_files
from gmlst.database.url_guard import assert_public_url
from gmlst.fasta_io import (
    count_fasta_records,
    count_profile_rows,
    is_valid_fasta,
    utc_now_iso,
)

logger = logging.getLogger(__name__)

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
        """Short identifier: ``"enterobase"``."""
        return "enterobase"

    @property
    def label(self) -> str:
        """Human-readable provider name: ``"Enterobase"``."""
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

        # Build URL/dest pairs for batch download — only for loci that are
        # not extracted yet. ``.tfa`` is the final artifact: once it exists
        # (decompression is atomic) the locus is complete, because the
        # ``.gz`` intermediate is deleted right after extraction. Listing
        # extracted loci again would re-download every one of them on each
        # retry of a large scheme.
        url_dest_pairs = []
        already_extracted = 0
        for locus in loci:
            tfa_path = dest_dir / f"{locus}.tfa"
            if tfa_path.exists():
                already_extracted += 1
                continue
            gz_path = dest_dir / f"{locus}.fasta.gz"
            url = f"{_BASE_URL}/{dir_name}/{locus}.fasta.gz"
            url_dest_pairs.append((url, gz_path))
        if already_extracted:
            logger.info(
                "[enterobase] %d/%d loci already extracted — resuming",
                already_extracted,
                len(loci),
            )

        # Batch download all .fasta.gz files
        if url_dest_pairs:
            download_required_files(
                url_dest_pairs,
                provider_name=self.name,
                download_tool=download_tool,
                max_connections=max_connections or 4,
            )

        # Decompress downloaded .fasta.gz to .tfa (parallel; also cleans
        # stale .gz leftovers next to already-extracted .tfa files)
        self._extract_loci(dest_dir, loci, validate=False)

        self._download_profiles(
            dir_name,
            loci,
            dest_dir,
            scheme_name,
            download_tool=download_tool,
            max_connections=max_connections,
        )
        profiles_headers = _head_remote_file(f"{_BASE_URL}/{dir_name}/profiles.list.gz")

        # Per-locus fingerprints (ETag/Last-Modified) are intentionally NOT
        # probed here: HEAD-ing every locus right after downloading all of
        # them doubles the request count for zero benefit. ``locus_remote``
        # starts empty and the first ``scheme update`` records fresh
        # fingerprints while trusting valid local files (see update_scheme).
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
            "locus_remote": {},
        }
        atomic_write_text(dest_dir / ".meta.json", json.dumps(meta, indent=2))
        logger.info("[enterobase] Done → %s", dest_dir)

    def _fetch_locus_headers(
        self, dir_name: str, loci: list[str]
    ) -> dict[str, dict[str, str]]:
        """HEAD-probe every locus ``.fasta.gz`` in parallel.

        Returns a ``locus -> {etag, last_modified, content_length}`` map
        used for future ``update_scheme`` change detection. Parallel HEADs
        keep a 3000-locus scheme from serializing one request per locus.
        """

        def _fetch(locus: str) -> tuple[str, dict[str, str]]:
            locus_url = f"{_BASE_URL}/{dir_name}/{locus}.fasta.gz"
            return (locus, _head_remote_file(locus_url))

        result: dict[str, dict[str, str]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(_fetch, locus) for locus in loci]
            for future in concurrent.futures.as_completed(futures):
                locus, headers = future.result()
                result[locus] = headers
        return result

    def _extract_loci(
        self,
        dest_dir: Path,
        loci: list[str],
        *,
        validate: bool,
        overwrite: bool = False,
    ) -> None:
        """Decompress locus ``.fasta.gz`` files into ``.tfa`` in parallel.

        Each locus is independent (read + gunzip + atomic write + gz
        cleanup), so a thread pool turns a serial 3000-file walk into a
        short parallel burst. The atomic write itself (mkstemp + rename,
        no fsync) is cheap — its purpose is crash safety: a ``.tfa`` that
        exists is always complete, which the resume logic relies on.

        With *validate*, each extracted ``.tfa`` is also checked as FASTA.
        With *overwrite*, a present ``.gz`` replaces an existing ``.tfa``
        (update semantics: fresh data wins); otherwise an existing
        ``.tfa`` is kept and only stale ``.gz`` leftovers are cleaned
        (download/resume semantics).
        All loci are processed even if some fail; the first failure is
        re-raised after the pool drains (successful files are kept so a
        re-run resumes instead of restarting).
        """
        if not loci:
            return

        def _extract(locus: str) -> None:
            gz_path = dest_dir / f"{locus}.fasta.gz"
            tfa_path = dest_dir / f"{locus}.tfa"
            if gz_path.exists() and (overwrite or not tfa_path.exists()):
                try:
                    atomic_write_bytes(tfa_path, gzip.decompress(gz_path.read_bytes()))
                except Exception as exc:
                    raise RuntimeError(
                        f"[enterobase] Failed to decompress {locus}: {exc}"
                    ) from exc
            # Clean up .gz file (also stale leftovers next to an existing .tfa)
            gz_path.unlink(missing_ok=True)
            if validate and not is_valid_fasta(tfa_path):
                raise RuntimeError(
                    f"[enterobase] Invalid FASTA content after update: {locus}"
                )

        logger.info("[enterobase] Decompressing %d files …", len(loci))
        first_error: RuntimeError | None = None
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = {executor.submit(_extract, locus): locus for locus in loci}
            for future in concurrent.futures.as_completed(futures):
                exc = future.exception()
                if exc is not None:
                    logger.error("%s", exc)
                    if first_error is None and isinstance(exc, RuntimeError):
                        first_error = exc
        if first_error is not None:
            raise first_error

    def update_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "mlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        """Re-download only the files whose remote headers changed.

        Probes every locus ``.fasta.gz`` and the profiles archive with HEAD
        requests (ETag / Last-Modified / Content-Length) plus FASTA
        validity, re-downloads and decompresses only the changed or
        missing ones, and rewrites ``.meta.json`` with the fresh headers.
        Loci without a stored fingerprint (fresh downloads record none)
        are trusted when their local ``.tfa`` is present and valid; this
        pass records their fingerprint for exact comparisons later.
        Returns whether any locus, profile, or the locus set changed.
        """
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
        new_locus_meta = self._fetch_locus_headers(dir_name, loci)
        for locus in loci:
            headers = new_locus_meta[locus]
            local_tfa = dest_dir / f"{locus}.tfa"
            old_headers = old_locus_meta.get(locus, {})
            # No stored fingerprint (fresh download, or pre-fingerprint
            # cache): trust a valid local file instead of re-downloading,
            # and let the fresh headers below seed future comparisons.
            fingerprint_changed = bool(old_headers) and _headers_changed(
                old_headers, headers
            )
            if (
                fingerprint_changed
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
            self._extract_loci(dest_dir, changed_loci, validate=True, overwrite=True)

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
        try:
            resp = fetch_with_retry(
                "GET", url, timeout=30, headers=self._auth_headers()
            )
        except RuntimeError as exc:
            if "HTTP 403" in str(exc):
                raise RuntimeError(
                    f"Enterobase returned 403 Forbidden for '{dir_name}'. "
                    "This scheme may require authentication (--token) or "
                    "be unavailable. Try the same scheme from another provider."
                ) from exc
            raise

        loci = []
        for line in resp.text.split("\n"):
            match = re.search(r'href="([^"/]+)\.fasta\.gz"', line)
            if match:
                locus_name = Path(match.group(1)).name
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
        """Download and convert ST profiles to MLST format.

        Streams the archive line by line: cgMLST ``profiles.list.gz``
        archives reach ~1.5 GB compressed (~14 GB raw) and must never be
        held in memory at once. The ``.gz`` is kept when anything fails so
        a retry resumes the download instead of restarting it.
        """
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
            rows = _convert_profiles_archive(gz_path, dest_file, loci)
        except Exception as exc:
            raise RuntimeError(
                f"[enterobase] Failed to download profiles: {exc}"
            ) from exc
        gz_path.unlink(missing_ok=True)
        logger.info("[enterobase] Profiles converted: %d STs", rows)


def _convert_profiles_archive(gz_path: Path, dest_file: Path, loci: list[str]) -> int:
    """Stream-convert a ``profiles.list.gz`` archive into an MLST TSV.

    Reads the archive line by line and writes the converted TSV to a
    ``.tmp`` sibling that atomically replaces *dest_file*, so peak memory
    stays flat regardless of archive size — cgMLST profiles archives reach
    ~1.5 GB compressed (~14 GB raw, ~750k rows), which the previous
    whole-file approach loaded into RAM several times over. Returns the
    number of ST rows written.
    """
    tmp_file = dest_file.parent / f"{dest_file.name}.tmp"
    tmp_file.unlink(missing_ok=True)
    header: list[str] | None = None
    indices: list[int] | None = None
    rows = 0
    try:
        with gzip.open(gz_path, "rt") as src, tmp_file.open("w") as out:
            for line in src:
                line = line.rstrip("\n")
                if header is None:
                    if not line:
                        continue
                    header = line.split("\t")
                    out.write("ST\t" + "\t".join(loci) + "\n")
                    continue
                if indices is None:
                    # Resolve locus -> column once; per-row work stays C-level.
                    column_of = {name: i for i, name in enumerate(header[1:], 1)}
                    indices = [column_of.get(locus, -1) for locus in loci]
                fields = line.split("\t")
                if len(fields) < len(header):
                    continue
                allele_values = [fields[i] if i >= 0 else "-" for i in (indices or [])]
                out.write(fields[0] + "\t" + "\t".join(allele_values) + "\n")
                rows += 1
                if rows % 100_000 == 0:
                    logger.info("[enterobase] Profiles converted: %d STs …", rows)
    except BaseException:
        tmp_file.unlink(missing_ok=True)
        raise
    if header is None:
        tmp_file.unlink(missing_ok=True)
        raise RuntimeError("[enterobase] profiles archive contained no data")
    tmp_file.replace(dest_file)
    return rows


def _head_remote_file(url: str) -> dict[str, str]:
    # fetch_with_retry adds exponential backoff (with Retry-After support)
    # so a mid-connection TLS reset no longer aborts the whole scheme run.
    resp = fetch_with_retry("HEAD", url, timeout=30)
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
