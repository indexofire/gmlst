"""cgMLST.org database provider.

cgMLST.org provides core genome MLST schemes for various bacterial species.
Unlike PubMLST/Pasteur, cgMLST.org doesn't have a REST API — schemes are
downloaded as a single bulk ZIP file per schema.

Source: https://www.cgmlst.org/ncs/
"""

from __future__ import annotations

import json
import logging
import re
import time
import zipfile
from pathlib import Path
from shutil import copyfileobj

import requests

from gmlst.database.atomic import atomic_write_text
from gmlst.database.download import DownloadTool, download_file
from gmlst.database.providers.base import SchemeInfo
from gmlst.database.providers.cgmlst_schemes import _CGMLST_SCHEMES

logger = logging.getLogger("gmlst.providers.cgmlst")

_BASE_URL = "https://www.cgmlst.org/ncs/1000"


class CgmlstProvider:
    """Provider for cgMLST.org database."""

    def __init__(self) -> None:
        self._name = "cgmlst"
        self._label = "cgMLST.org"

    @property
    def name(self) -> str:
        return self._name

    @property
    def label(self) -> str:
        return self._label

    def list_schemes(self, scheme_type: str = "cgmlst") -> list[SchemeInfo]:
        """Return available cgMLST schemes."""
        if scheme_type not in ("cgmlst", "all"):
            return []

        return [
            SchemeInfo(
                scheme_name=f"{scheme['name'].lower()}_{i}",
                display_name=scheme["display"],
                organism=scheme["organism"],
                scheme_type="cgmlst",
                n_loci=scheme["loci"],
                provider=self._name,
                extra={},
            )
            for i, scheme in enumerate(_CGMLST_SCHEMES, 1)
        ]

    def download_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "cgmlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict | None = None,
    ) -> None:
        """Download cgMLST scheme alleles from cgMLST.org.

        Downloads a single bulk ZIP containing all allele FASTA files using
        the best available tool (aria2c → curl → wget → httpx).
        """
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Strip numeric suffix (e.g. 'abaumannii_4' → 'abaumannii')
        base_name = scheme_name
        if "_" in scheme_name:
            parts = scheme_name.rsplit("_", 1)
            if parts[1].isdigit():
                base_name = parts[0]

        scheme_info = next(
            (s for s in _CGMLST_SCHEMES if s["name"].lower() == base_name.lower()),
            None,
        )
        if not scheme_info:
            raise ValueError(f"Unknown cgMLST scheme: {scheme_name}")

        schema_id = scheme_info["schema_id"]
        alleles_url = f"https://www.cgmlst.org/ncs/schema/{schema_id}/alleles/"
        zip_path = dest_dir / f"{scheme_name}.zip"

        if _has_valid_zip(zip_path):
            logger.info("Reusing existing ZIP archive: %s", zip_path)
        else:
            logger.info(
                "Downloading cgMLST scheme '%s' from %s", scheme_name, alleles_url
            )
            download_file(
                alleles_url,
                zip_path,
                tool=download_tool,
                max_connections=max_connections,
            )

        logger.info("Extracting missing loci from %s to %s", zip_path.name, dest_dir)
        try:
            _extract_missing_fasta_entries(zip_path, dest_dir)
        except zipfile.BadZipFile as exc:
            zip_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Invalid ZIP received for scheme '{scheme_name}'"
            ) from exc

        status = _fetch_schema_status(schema_id)
        loci = sorted(
            {
                path.stem
                for path in dest_dir.glob("*.fasta")
                if path.is_file() and path.name != f"{scheme_name}.zip"
            }
        )
        expected_loci = _parse_locus_count(status.get("locus_count", ""))
        if expected_loci <= 0:
            raise RuntimeError(
                f"Could not determine expected locus count for '{scheme_name}'"
            )
        if expected_loci > 0 and len(loci) < expected_loci:
            raise RuntimeError(
                f"Incomplete cgMLST download for '{scheme_name}': "
                f"expected {expected_loci} loci, got {len(loci)}"
            )
        meta = {
            "scheme": scheme_name,
            "provider": self._name,
            "scheme_type": "cgmlst",
            "schema_id": schema_id,
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "loci": loci,
            "remote": status,
        }
        atomic_write_text(dest_dir / ".meta.json", json.dumps(meta, indent=2))
        zip_path.unlink(missing_ok=True)
        logger.info(
            "Successfully downloaded cgMLST scheme '%s' to %s", scheme_name, dest_dir
        )

    def update_scheme(
        self,
        scheme_name: str,
        dest_dir: Path,
        scheme_type: str = "cgmlst",
        download_tool: DownloadTool = "auto",
        max_connections: int | None = None,
        extra: dict | None = None,
    ) -> bool:
        meta_file = dest_dir / ".meta.json"
        local_meta: dict = {}
        if meta_file.exists():
            local_meta = json.loads(meta_file.read_text())

        base_name = scheme_name
        if "_" in scheme_name:
            parts = scheme_name.rsplit("_", 1)
            if parts[1].isdigit():
                base_name = parts[0]

        scheme_info = next(
            (s for s in _CGMLST_SCHEMES if s["name"].lower() == base_name.lower()),
            None,
        )
        if not scheme_info:
            raise ValueError(f"Unknown cgMLST scheme: {scheme_name}")

        schema_id = scheme_info["schema_id"]
        remote = _fetch_schema_status(schema_id)
        old_remote = local_meta.get("remote", {})

        expected_loci = _parse_locus_count(remote.get("locus_count", ""))
        if expected_loci <= 0:
            raise RuntimeError(
                f"Could not determine expected locus count for '{scheme_name}'"
            )
        local_loci_count = _count_local_fasta_files(dest_dir)

        remote_changed = (
            str(old_remote.get("version", "")) != remote.get("version", "")
            or str(old_remote.get("last_change", "")) != remote.get("last_change", "")
            or str(old_remote.get("locus_count", "")) != remote.get("locus_count", "")
        )
        incomplete_local = local_loci_count == 0 or (
            expected_loci > 0 and local_loci_count < expected_loci
        )
        changed = remote_changed or incomplete_local
        if changed:
            if remote_changed:
                (dest_dir / f"{scheme_name}.zip").unlink(missing_ok=True)
            self.download_scheme(
                scheme_name,
                dest_dir,
                scheme_type=scheme_type,
                download_tool=download_tool,
                max_connections=max_connections,
            )
            return True

        local_meta["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        local_meta["remote"] = remote
        atomic_write_text(meta_file, json.dumps(local_meta, indent=2))
        return False


def _fetch_schema_status(schema_id: str) -> dict[str, str]:
    url = f"https://www.cgmlst.org/ncs/schema/{schema_id}/"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Failed to fetch cgMLST schema status for schema_id={schema_id}"
        ) from exc
    html = resp.text
    status = {
        "version": _extract_schema_field(html, "Version"),
        "locus_count": _extract_schema_field(html, "Locus Count"),
        "ct_count": _extract_schema_field(html, "Complex Type Count"),
        "last_change": _extract_schema_field(html, "Last Change"),
    }
    if not any(status.values()):
        raise RuntimeError(
            f"Failed to parse cgMLST schema status page for schema_id={schema_id}"
        )
    return status


def _extract_schema_field(html: str, field_name: str) -> str:
    pattern = rf">\s*{re.escape(field_name)}\s*</td>\s*<td>\s*([^<]+?)\s*</td>"
    match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def _has_valid_zip(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with zipfile.ZipFile(path):
            return True
    except zipfile.BadZipFile:
        return False


def _extract_missing_fasta_entries(zip_path: Path, dest_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            filename = Path(member.filename).name
            if not filename.endswith(".fasta"):
                continue
            dest_file = dest_dir / filename
            if dest_file.exists():
                continue
            with zf.open(member, "r") as src, dest_file.open("wb") as dst:
                copyfileobj(src, dst)


def _parse_locus_count(value: str) -> int:
    digits_only = re.sub(r"[^0-9]", "", value)
    return int(digits_only) if digits_only else 0


def _count_local_fasta_files(dest_dir: Path) -> int:
    return sum(1 for path in dest_dir.glob("*.fasta") if path.is_file())
