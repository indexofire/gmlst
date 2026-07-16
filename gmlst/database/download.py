"""Unified download utilities for gmlst providers.

Provides a layered download strategy:
  1. External tools (aria2c → curl → wget) if available — fastest, with native progress
  2. httpx async — pure Python, streaming with Rich progress bar
  3. requests — simple fallback for small files or when httpx is unavailable

Usage:
    from gmlst.database.download import download_file, download_file_requests

    # Full strategy (aria2c → curl → wget → httpx), shows progress bar
    download_file(url, dest)

    # Plain requests (for JSON APIs, small files, when in a sync context)
    download_file_requests(url, dest)
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from gmlst.database.url_guard import assert_public_url

logger = logging.getLogger("gmlst.download")

DownloadTool = Literal["auto", "aria2c", "curl", "wget", "httpx", "requests"]


def _cleanup_partial_download(dest: Path, *, backend: str) -> None:
    if backend == "aria2c":
        logger.info("Preserving partial file for aria2c resume: %s", dest)
        return
    if dest.exists():
        dest.unlink()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_TIMEOUT = 120.0
_CHUNK_SIZE = 1024 * 1024  # 1 MB
_MAX_RETRIES = 3
_RETRY_DELAY = 5.0


# ---------------------------------------------------------------------------
# External-tool backends (aria2c, curl, wget)
# ---------------------------------------------------------------------------


def _try_aria2c(
    url: str,
    dest: Path,
    *,
    silent: bool = True,
    connections: int = 4,
    headers: dict[str, str] | None = None,
) -> bool:
    if not shutil.which("aria2c"):
        return False
    per_server = min(connections, 2)
    cmd = [
        "aria2c",
        "--continue=true",
        f"--max-connection-per-server={per_server}",
        f"--split={per_server}",
        "--out",
        dest.name,
        "--dir",
        str(dest.parent),
    ]
    if headers:
        for key, value in headers.items():
            cmd.append(f"--header={key}: {value}")
    cmd.append(url)
    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL if silent else None,
        stderr=subprocess.DEVNULL if silent else None,
    )
    return result.returncode == 0 and dest.exists()


def _try_curl(
    url: str,
    dest: Path,
    *,
    silent: bool = True,
    headers: dict[str, str] | None = None,
) -> bool:
    if not shutil.which("curl"):
        return False
    cmd = [
        "curl",
        "--location",
        "--continue-at",
        "-",
        "--progress-bar",
        "--output",
        str(dest),
    ]
    if headers:
        for key, value in headers.items():
            cmd.extend(["-H", f"{key}: {value}"])
    cmd.append(url)
    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL if silent else None,
        stderr=subprocess.DEVNULL if silent else None,
    )
    return result.returncode == 0 and dest.exists()


def _try_wget(
    url: str,
    dest: Path,
    *,
    silent: bool = True,
    headers: dict[str, str] | None = None,
) -> bool:
    if not shutil.which("wget"):
        return False
    cmd = [
        "wget",
        "--continue",
        "--show-progress",
        "--progress=bar:force",
        "--output-document",
        str(dest),
    ]
    if headers:
        for key, value in headers.items():
            cmd.extend(["--header", f"{key}: {value}"])
    cmd.append(url)
    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL if silent else None,
        stderr=subprocess.DEVNULL if silent else None,
    )
    return result.returncode == 0 and dest.exists()


# ---------------------------------------------------------------------------
# httpx async backend with Rich progress bar
# ---------------------------------------------------------------------------


async def _try_httpx_async(url: str, dest: Path, timeout: float) -> bool:
    """Download with httpx async + Rich progress bar. Returns True on success."""
    try:
        import httpx  # type: ignore[import-not-found]  # httpx is an optional dependency, guarded by try/except ImportError
        from rich.progress import (
            BarColumn,
            DownloadColumn,
            Progress,
            TextColumn,
            TimeRemainingColumn,
            TransferSpeedColumn,
        )
    except ImportError:
        logger.debug("httpx or rich not available")
        return False

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            progress = Progress(
                TextColumn("[bold blue]{task.fields[filename]}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            )
            with progress:
                task_id = progress.add_task(
                    "Downloading", total=None, filename=dest.name
                )
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    total = int(resp.headers.get("content-length", 0))
                    if total:
                        progress.update(task_id, total=total)
                    with dest.open("wb") as f:
                        async for chunk in resp.aiter_bytes(_CHUNK_SIZE):
                            f.write(chunk)
                            progress.update(task_id, advance=len(chunk))
        return dest.exists()
    except Exception as exc:
        logger.debug("httpx download failed: %s", exc)
        dest.unlink(missing_ok=True)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def download_file(
    url: str,
    dest: Path,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    tool: DownloadTool = "auto",
    max_connections: int | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Download url to dest using the best available method.

    Tries in order: aria2c → curl → wget → httpx (async with progress bar).
    All methods support resume/continue on partial downloads.

    Raises RuntimeError if all methods fail.
    """
    # SSRF guard: validate the URL *before* handing it to any backend so a
    # value that came from an external API response can never reach an
    # internal network. UrlGuardError propagates to the caller unchanged.
    assert_public_url(url)

    dest.parent.mkdir(parents=True, exist_ok=True)

    connections = max_connections if max_connections is not None else 4
    req_headers = headers or {}

    backends: list[tuple[str, Callable[[], bool]]] = [
        (
            "aria2c",
            lambda: _try_aria2c(
                url,
                dest,
                silent=True,
                connections=connections,
                headers=req_headers or None,
            ),
        ),
        (
            "curl",
            lambda: _try_curl(url, dest, headers=req_headers or None),
        ),
        (
            "wget",
            lambda: _try_wget(url, dest, headers=req_headers or None),
        ),
        ("httpx", lambda: asyncio.run(_try_httpx_async(url, dest, timeout))),
    ]

    if tool == "requests":
        download_file_requests(url, dest, timeout=timeout, headers=req_headers or None)
        return

    if tool != "auto":
        selected = next((item for item in backends if item[0] == tool), None)
        if selected is None:
            raise RuntimeError(f"Unknown download tool: {tool}")
        name, fn = selected
        if name != "httpx" and not shutil.which(name):
            raise RuntimeError(f"Requested download tool not found in PATH: {name}")
        if name == "aria2c":
            ok = _try_aria2c(url, dest, silent=False, connections=connections)
        elif name == "curl":
            ok = _try_curl(url, dest, silent=False)
        elif name == "wget":
            ok = _try_wget(url, dest, silent=False)
        else:
            ok = bool(fn())
        if ok:
            return
        _cleanup_partial_download(dest, backend=name)
        raise RuntimeError(f"Requested download tool failed: {name} ({url})")

    for name, fn in backends:
        if name != "httpx" and not shutil.which(name):
            logger.debug("Skipping %s (not found)", name)
            continue
        logger.info("Downloading via %s ...", name)
        try:
            if fn():
                return
            logger.warning("%s failed, trying next ...", name)
        except Exception as exc:
            logger.warning("%s error: %s, trying next ...", name, exc)
        _cleanup_partial_download(dest, backend=name)

    logger.info("Falling back to requests (with retry) ...")
    download_file_requests(url, dest, timeout=timeout, headers=req_headers or None)


def download_file_requests(
    url: str,
    dest: Path,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    retries: int = _MAX_RETRIES,
    retry_delay: float = _RETRY_DELAY,
    chunk_size: int = _CHUNK_SIZE,
    headers: dict[str, str] | None = None,
) -> None:
    """Download url to dest using requests with streaming and retry.

    Used for bigsdb (PubMLST/Pasteur) where files are moderate-sized and
    called in a synchronous context (JSON API, allele FASTA, profiles CSV).

    Raises RuntimeError after exhausting retries.
    """
    import requests

    assert_public_url(url)

    req_headers = headers or {}

    dest.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, stream=True, headers=req_headers)
            resp.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    fh.write(chunk)
            return
        except requests.RequestException as exc:
            if attempt == retries:
                dest.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Download failed after {retries} attempts: {url}"
                ) from exc
            logger.warning(
                "Download attempt %d/%d failed for %s: %s",
                attempt,
                retries,
                url,
                exc,
            )
            time.sleep(retry_delay)


def fetch_json(
    url: str,
    *,
    timeout: float = 60.0,
    retries: int = _MAX_RETRIES,
    retry_delay: float = _RETRY_DELAY,
    headers: dict[str, str] | None = None,
) -> dict | list:
    """GET a JSON endpoint with retry. Returns parsed data.

    Used by bigsdb (PubMLST/Pasteur) for API calls.
    """
    import requests

    assert_public_url(url)

    req_headers = headers or {}

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers=req_headers)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries:
                raise RuntimeError(
                    f"JSON fetch failed after {retries} attempts: {url}"
                ) from exc
            logger.warning(
                "JSON fetch attempt %d/%d failed: %s - %s",
                attempt,
                retries,
                url,
                exc,
            )
            time.sleep(retry_delay)
    # unreachable, but satisfies type checkers
    raise RuntimeError(f"JSON fetch failed: {url}")


def _download_batch_threadpool(
    pending: list[tuple[str, Path]],
    already_done: int,
    max_concurrent: int,
    timeout: float,
    tool: DownloadTool,
) -> tuple[int, int]:
    """Fallback parallel download using ThreadPoolExecutor.

    Used when aria2c is not available. Downloads files concurrently using
    ThreadPoolExecutor, with each file downloaded using the standard
    download_file() function (which tries aria2c -> curl -> wget -> httpx).

    Args:
        pending: List of (url, dest) tuples to download
        already_done: Number of files already downloaded (skipped)
        max_concurrent: Maximum concurrent downloads
        timeout: Timeout per file

    Returns:
        Tuple of (success_count, fail_count)
    """
    logger.info(
        "Batch downloading %d files with ThreadPoolExecutor (concurrency: %d) ...",
        len(pending),
        max_concurrent,
    )

    success_count = already_done
    fail_count = 0

    def _download_one(pair: tuple[str, Path]) -> bool:
        url, dest = pair
        try:
            download_file(
                url,
                dest,
                timeout=timeout,
                tool=tool,
                max_connections=max_concurrent,
            )
            return True
        except Exception as exc:
            logger.warning("Failed to download %s: %s", url, exc)
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {executor.submit(_download_one, p): p for p in pending}
        for future in concurrent.futures.as_completed(futures):
            if future.result():
                success_count += 1
            else:
                fail_count += 1

    logger.info(
        "Batch download complete: %d success, %d failed",
        success_count,
        fail_count,
    )
    return (success_count, fail_count)


def download_files_batch(
    url_dest_pairs: list[tuple[str, Path]],
    *,
    max_concurrent: int = 16,
    timeout: float = _DEFAULT_TIMEOUT,
    tool: DownloadTool = "auto",
    headers: dict[str, str] | None = None,
) -> tuple[int, int]:
    """Download multiple files in parallel using aria2c batch mode.

    Args:
        url_dest_pairs: List of (url, dest_path) tuples
        max_concurrent: Maximum concurrent downloads (default 16)
        timeout: Timeout per file

    Returns:
        Tuple of (success_count, fail_count)

    Uses aria2c's -i option for efficient parallel downloads.
    Falls back to ThreadPoolExecutor if aria2c not available.
    """
    if not url_dest_pairs:
        return (0, 0)

    # Filter out already downloaded files
    pending = [
        (url, dest)
        for url, dest in url_dest_pairs
        if not (dest.exists() and dest.stat().st_size > 0)
    ]
    already_done = len(url_dest_pairs) - len(pending)

    if already_done > 0:
        logger.info("Skipping %d already downloaded files", already_done)

    if not pending:
        return (already_done, 0)

    # For large batches (>500 files), download in chunks to avoid
    # overwhelming upstream servers (HTTP 429 Too Many Requests)
    _BATCH_SIZE = 500
    if len(pending) > _BATCH_SIZE:
        total_fail = 0
        for i in range(0, len(pending), _BATCH_SIZE):
            chunk = pending[i : i + _BATCH_SIZE]
            batch_num = i // _BATCH_SIZE + 1
            total_batches = (len(pending) + _BATCH_SIZE - 1) // _BATCH_SIZE
            logger.info(
                "Downloading batch %d/%d (%d files) ...",
                batch_num,
                total_batches,
                len(chunk),
            )
            s, f = _download_single_batch(
                chunk,
                max_concurrent,
                timeout,
                tool,
                headers,
            )
            total_fail += f
            if f > 0:
                logger.warning(
                    "Batch %d had %d failures, continuing to next batch",
                    batch_num,
                    f,
                )
        total_success = already_done + (len(pending) - total_fail)
        return (total_success, total_fail)

    return _download_single_batch(pending, max_concurrent, timeout, tool, headers)


def _download_single_batch(
    pending: list[tuple[str, Path]],
    max_concurrent: int,
    timeout: float,
    tool: DownloadTool,
    headers: dict[str, str] | None,
) -> tuple[int, int]:
    if not pending:
        return (0, 0)

    for url, _dest in pending:
        assert_public_url(url)

    # Single file: use regular download
    if len(pending) == 1:
        url, dest = pending[0]
        try:
            download_file(
                url,
                dest,
                timeout=timeout,
                tool=tool,
                max_connections=max_concurrent,
                headers=headers,
            )
            return (1, 0)
        except Exception as exc:
            logger.warning("Single-file download failed for %s: %s", url, exc)
            return (0, 1)

    if tool != "auto" and tool != "aria2c":
        logger.info("Batch mode using selected tool '%s' via ThreadPoolExecutor", tool)
        return _download_batch_threadpool(
            pending,
            0,
            max_concurrent,
            timeout,
            tool,
        )

    # Check if aria2c is available
    if not shutil.which("aria2c"):
        if tool == "aria2c":
            raise RuntimeError("Requested download tool not found in PATH: aria2c")
        logger.warning("aria2c not found, using ThreadPoolExecutor")
        return _download_batch_threadpool(
            pending,
            0,
            max_concurrent,
            timeout,
            tool,
        )

    # Use aria2c batch download
    # All files must go to same directory for aria2c -i
    dest_dir = pending[0][1].parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Build aria2c input file
    # Format: URL per line, followed by out=filename
    input_lines = []
    for url, dest in pending:
        input_lines.append(url)
        input_lines.append(f"  out={dest.name}")

    # Write temporary input file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("\n".join(input_lines))
        input_file = f.name

    try:
        logger.info(
            "Batch downloading %d files with aria2c (concurrency: %d) ...",
            len(pending),
            max_concurrent,
        )
        show_progress = tool == "aria2c"
        aria_cmd = [
            "aria2c",
            "--input-file",
            input_file,
            "--dir",
            str(dest_dir),
            "--continue=true",
            "--max-connection-per-server=2",
            "--split=2",
            "--max-concurrent-downloads",
            str(max_concurrent),
            "--max-tries=5",
            "--retry-wait=3",
            "--connect-timeout=30",
            "--timeout=120",
            "--auto-file-renaming=false",
            "--allow-overwrite=true",
            "--summary-interval=10",
        ]
        if headers:
            for key, value in headers.items():
                aria_cmd.append(f"--header={key}: {value}")
        result = subprocess.run(
            aria_cmd,
            stdout=None if show_progress else subprocess.DEVNULL,
            stderr=None if show_progress else subprocess.DEVNULL,
        )

        if result.returncode != 0:
            logger.warning(
                "aria2c batch download failed with exit code %d", result.returncode
            )
            success = sum(1 for _, d in pending if d.exists())
            return (success, len(pending) - success)

        success, fail = 0, 0
        for url, dest in pending:
            if dest.exists():
                success += 1
            else:
                fail += 1
                logger.warning("Failed to download: %s", url)

        logger.info("Batch download complete: %d success, %d failed", success, fail)
        return (success, fail)

    finally:
        Path(input_file).unlink(missing_ok=True)
