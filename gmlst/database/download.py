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
import contextlib
import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import requests

from gmlst.database.url_guard import (
    UrlGuardError,
    assert_public_url,
    assert_safe_url_text,
)

logger = logging.getLogger(__name__)

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

# Politeness throttling. Sustained request bursts get gmlst IPs rate-limited
# or banned by provider hosts (PubMLST/Pasteur answer HTTP 429 or drop the
# connection). Large batch downloads (> _BATCH_SIZE files) pause between
# chunks; per-request delays are opt-in for stricter hosts. Both are
# overridable via environment variables.
_BATCH_SIZE = 500
_DEFAULT_CHUNK_PAUSE = 20.0
_DEFAULT_REQUEST_DELAY = 0.0
_MAX_RETRY_BACKOFF = 120.0

# Batch-level auto-retry. Transient network failures (TLS resets, connection
# drops) on large scheme downloads used to abort the whole command and force
# the user to re-run it manually. Failed batches are now retried within the
# same run after a long pause, re-downloading only the still-missing files.
_DEFAULT_RETRY_ROUNDS = 3
_DEFAULT_RETRY_PAUSE = 60.0


def _env_seconds(name: str, default: float) -> float:
    """Read a non-negative float seconds value from env var *name*."""
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %.1fs", name, raw, default)
        return default
    return max(0.0, value)


def _chunk_pause_seconds() -> float:
    """Pause between large-batch chunks (``GMLST_DOWNLOAD_CHUNK_PAUSE``)."""
    return _env_seconds("GMLST_DOWNLOAD_CHUNK_PAUSE", _DEFAULT_CHUNK_PAUSE)


def _retry_rounds() -> int:
    """Batch retry rounds (``GMLST_DOWNLOAD_RETRY_ROUNDS``, 0 disables)."""
    raw = os.environ.get("GMLST_DOWNLOAD_RETRY_ROUNDS", "")
    if not raw:
        return _DEFAULT_RETRY_ROUNDS
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning(
            "Invalid GMLST_DOWNLOAD_RETRY_ROUNDS=%r; using %d",
            raw,
            _DEFAULT_RETRY_ROUNDS,
        )
        return _DEFAULT_RETRY_ROUNDS


def _retry_pause_seconds() -> float:
    """Pause between batch retry rounds (``GMLST_DOWNLOAD_RETRY_PAUSE``)."""
    return _env_seconds("GMLST_DOWNLOAD_RETRY_PAUSE", _DEFAULT_RETRY_PAUSE)


def _throttle_request() -> None:
    """Sleep ``GMLST_DOWNLOAD_DELAY`` seconds; no-op when unset or zero.

    Called before each provider HTTP request so sequential API walks (e.g.
    ``scheme update`` checking every locus) cannot hammer the server.
    """
    delay = _env_seconds("GMLST_DOWNLOAD_DELAY", _DEFAULT_REQUEST_DELAY)
    if delay > 0:
        time.sleep(delay)


def _retry_wait_seconds(exc: BaseException, attempt: int, base_delay: float) -> float:
    """Exponential backoff for retry *attempt*, honoring ``Retry-After``.

    Grows as ``base_delay * 2^(attempt-1)`` and is raised to the server's
    ``Retry-After`` header (seconds) when present, capped at
    ``_MAX_RETRY_BACKOFF``.
    """
    delay = base_delay * (2 ** (attempt - 1))
    response = getattr(exc, "response", None)
    retry_after = None
    if response is not None:
        headers = getattr(response, "headers", None) or {}
        retry_after = headers.get("Retry-After")
    if retry_after is not None:
        with contextlib.suppress(ValueError, TypeError):
            delay = max(delay, float(retry_after))
    return min(delay, _MAX_RETRY_BACKOFF)


# ---------------------------------------------------------------------------
# External-tool backends (aria2c, curl, wget)
# ---------------------------------------------------------------------------


def _try_aria2c(
    url: str,
    dest: Path,
    *,
    silent: bool = True,
    headers: dict[str, str] | None = None,
) -> bool:
    if not shutil.which("aria2c"):
        return False
    # Single connection per server: allele FASTA/profile files are small, so
    # extra parallel connections only multiply the request rate and trip
    # provider rate limiters (PubMLST bans bursty IPs).
    per_server = 1
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

    req_headers = headers or {}

    # Credential headers must not leak into the process argument list
    # (visible to other local users via ps on shared machines), so skip
    # the external-tool backends entirely when headers are present.
    if req_headers and tool == "auto":
        tool = "requests"

    backends: list[tuple[str, Callable[[], bool]]] = [
        (
            "aria2c",
            lambda: _try_aria2c(
                url,
                dest,
                silent=True,
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
            ok = _try_aria2c(url, dest, silent=False)
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


class _RedirectValidatingSession(requests.Session):
    """Session that re-checks every redirect hop against the SSRF guard.

    requests invokes ``rebuild_auth`` on each redirect hop (before the
    redirected request is sent), making it a reliable per-hop hook. URLs
    from untrusted API responses therefore stay guarded even after a
    3xx redirect to a different host.
    """

    def rebuild_auth(
        self,
        prepared_request: requests.PreparedRequest,
        response: requests.Response,
    ) -> None:
        """Re-validate every redirect hop against the SSRF guard.

        SECURITY: requests calls this hook on each redirect before the
        redirected request is sent, so re-checking ``prepared_request.url``
        here prevents an attacker-controlled redirect (e.g. from a URL
        obtained via an external API response) from reaching an internal
        network address that the originally validated URL would never
        have been allowed to touch.
        """
        assert_public_url(str(prepared_request.url))


def _public_session() -> requests.Session:
    return _RedirectValidatingSession()


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
    assert_public_url(url)

    req_headers = headers or {}

    dest.parent.mkdir(parents=True, exist_ok=True)

    _throttle_request()

    for attempt in range(1, retries + 1):
        try:
            with _public_session() as session:
                resp = session.get(
                    url, timeout=timeout, stream=True, headers=req_headers
                )
                resp.raise_for_status()
                with dest.open("wb") as fh:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        fh.write(chunk)
            return
        except requests.RequestException as exc:
            status = _non_retryable_status(exc)
            if status is not None:
                dest.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Download failed (HTTP {status}) for {url}"
                ) from exc
            if attempt == retries:
                dest.unlink(missing_ok=True)
                raise RuntimeError(
                    f"[network:{_classify_network_error(exc)}] "
                    f"cannot reach {_short_host(url)} after {retries} attempts — {url}"
                ) from exc
            logger.warning(
                "retry %d/%d [%s] %s — waiting %.0fs",
                attempt,
                retries,
                _classify_network_error(exc),
                _short_host(url),
                _retry_wait_seconds(exc, attempt, retry_delay),
            )
            time.sleep(_retry_wait_seconds(exc, attempt, retry_delay))


def _non_retryable_status(exc: BaseException) -> int | None:
    """Return the HTTP status if *exc* is a deterministic 4xx (except 429)."""
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        if response is not None:
            status = response.status_code
            if 400 <= status < 500 and status != 429:
                return status
    return None


def _classify_network_error(exc: BaseException) -> str:
    """Categorize a requests exception into a short human-readable reason."""
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return "connection timeout"
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return "read timeout"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "connection error"
    if isinstance(exc, requests.exceptions.HTTPError):
        return (
            f"HTTP {exc.response.status_code}"
            if exc.response is not None
            else "HTTP error"
        )
    if isinstance(exc, requests.exceptions.TooManyRedirects):
        return "too many redirects"
    if isinstance(exc, ValueError):
        # covers requests JSONDecodeError (a ValueError subclass)
        return "invalid JSON response"
    return type(exc).__name__


def _short_host(url: str) -> str:
    """Extract hostname from a URL for concise error messages."""
    from urllib.parse import urlparse

    return urlparse(url).netloc or url


def fetch_json(
    url: str,
    *,
    timeout: float = 60.0,
    retries: int = _MAX_RETRIES,
    retry_delay: float = _RETRY_DELAY,
    headers: dict[str, str] | None = None,
) -> dict | list:
    """GET a JSON endpoint with retry. Returns parsed data.

    Used by bigsdb (PubMLST/Pasteur) for API calls. Client errors (4xx
    except 429) fail immediately without retry: the server's answer is
    deterministic for the same request.
    """
    assert_public_url(url)

    req_headers = headers or {}

    _throttle_request()
    for attempt in range(1, retries + 1):
        try:
            with _public_session() as session:
                resp = session.get(url, timeout=timeout, headers=req_headers)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            status = _non_retryable_status(exc)
            if status is not None:
                raise RuntimeError(
                    f"JSON fetch failed (HTTP {status}) for {url}"
                ) from exc
            if attempt == retries:
                raise RuntimeError(
                    f"[network:{_classify_network_error(exc)}] "
                    f"cannot reach {_short_host(url)} after {retries} attempts — {url}"
                ) from exc
            logger.warning(
                "retry %d/%d [%s] %s — %s — waiting %.0fs",
                attempt,
                retries,
                _classify_network_error(exc),
                _short_host(url),
                url.split("/loci/")[-1].split("/alleles")[0]
                if "/loci/" in url
                else url.rstrip("/").split("/")[-1],
                _retry_wait_seconds(exc, attempt, retry_delay),
            )
            time.sleep(_retry_wait_seconds(exc, attempt, retry_delay))
    # unreachable, but satisfies type checkers
    raise RuntimeError(f"JSON fetch failed: {url}")


def fetch_with_retry(
    method: str,
    url: str,
    *,
    timeout: float = 60.0,
    retries: int = _MAX_RETRIES,
    retry_delay: float = _RETRY_DELAY,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    """Send one HTTP request with exponential-backoff retry.

    Used for non-JSON endpoints (directory listings, HEAD fingerprints)
    where a raw transport failure — e.g. a TLS reset mid-connection —
    must not escape unwrapped or unretried. Honors server ``Retry-After``
    headers; deterministic client errors (4xx except 429) fail
    immediately. Raises ``RuntimeError`` with a classified reason when
    retries are exhausted.
    """
    assert_public_url(url)

    req_headers = headers or {}

    _throttle_request()

    for attempt in range(1, retries + 1):
        try:
            with _public_session() as session:
                resp = session.request(
                    method, url, timeout=timeout, headers=req_headers
                )
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            status = _non_retryable_status(exc)
            if status is not None:
                raise RuntimeError(f"Request failed (HTTP {status}) for {url}") from exc
            if attempt == retries:
                raise RuntimeError(
                    f"[network:{_classify_network_error(exc)}] "
                    f"cannot reach {_short_host(url)} after {retries} attempts — {url}"
                ) from exc
            wait = _retry_wait_seconds(exc, attempt, retry_delay)
            logger.warning(
                "retry %d/%d [%s] %s — waiting %.0fs",
                attempt,
                retries,
                _classify_network_error(exc),
                _short_host(url),
                wait,
            )
            time.sleep(wait)
    # unreachable, but satisfies type checkers
    raise RuntimeError(f"Request failed: {url}")


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
            _throttle_request()
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


def _download_with_chunks(
    pending: list[tuple[str, Path]],
    max_concurrent: int,
    timeout: float,
    tool: DownloadTool,
    headers: dict[str, str] | None,
) -> tuple[int, int]:
    """One full pass over *pending*, chunked for large batches.

    For large batches (> _BATCH_SIZE files), download in chunks with a
    pause between them to avoid overwhelming upstream servers
    (HTTP 429 Too Many Requests / IP bans).
    """
    if len(pending) <= _BATCH_SIZE:
        return _download_single_batch(pending, max_concurrent, timeout, tool, headers)

    total_fail = 0
    chunks = [pending[i : i + _BATCH_SIZE] for i in range(0, len(pending), _BATCH_SIZE)]
    for batch_num, chunk in enumerate(chunks, 1):
        logger.info(
            "Downloading batch %d/%d (%d files) ...",
            batch_num,
            len(chunks),
            len(chunk),
        )
        _successes, f = _download_single_batch(
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
        if batch_num < len(chunks):
            pause = _chunk_pause_seconds()
            if pause > 0:
                logger.info(
                    "Pausing %.0fs before next batch "
                    "(rate-limit protection; override with "
                    "GMLST_DOWNLOAD_CHUNK_PAUSE) ...",
                    pause,
                )
                time.sleep(pause)
    return (len(pending) - total_fail, total_fail)


def download_files_batch(
    url_dest_pairs: list[tuple[str, Path]],
    *,
    max_concurrent: int = 16,
    timeout: float = _DEFAULT_TIMEOUT,
    tool: DownloadTool = "auto",
    headers: dict[str, str] | None = None,
) -> tuple[int, int]:
    """Download multiple files in parallel, retrying transient failures.

    Args:
        url_dest_pairs: List of (url, dest_path) tuples
        max_concurrent: Maximum concurrent downloads (default 16)
        timeout: Timeout per file

    Returns:
        Tuple of (success_count, fail_count)

    Uses aria2c's -i option for efficient parallel downloads.
    Falls back to ThreadPoolExecutor if aria2c not available. Transient
    network failures (TLS resets, dropped connections) are retried inside
    the same run: after each pass the still-missing files are re-listed
    and re-downloaded after ``GMLST_DOWNLOAD_RETRY_PAUSE`` seconds, up to
    ``GMLST_DOWNLOAD_RETRY_ROUNDS`` extra rounds. Files that succeeded
    are never re-downloaded.
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

    rounds = _retry_rounds()
    for attempt in range(rounds + 1):
        if attempt > 0:
            pause = _retry_pause_seconds()
            logger.warning(
                "Retry round %d/%d: %d file(s) still missing — pausing %.0fs "
                "(override with GMLST_DOWNLOAD_RETRY_PAUSE) ...",
                attempt,
                rounds,
                len(pending),
                pause,
            )
            time.sleep(pause)
        _download_with_chunks(pending, max_concurrent, timeout, tool, headers)
        pending = [
            (url, dest)
            for url, dest in pending
            if not (dest.exists() and dest.stat().st_size > 0)
        ]
        if not pending:
            break

    total_success = already_done + (len(url_dest_pairs) - already_done - len(pending))
    return (total_success, len(pending))


def _assert_safe_batch_entry(url: str, dest: Path) -> None:
    """Reject entries that could inject lines/options into an aria2c input file."""
    assert_safe_url_text(url)
    name = dest.name
    if (
        not name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
        or any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F for ch in name)
    ):
        raise UrlGuardError(f"Refusing unsafe download file name: {name!r}")


def _download_single_batch(
    pending: list[tuple[str, Path]],
    max_concurrent: int,
    timeout: float,
    tool: DownloadTool,
    headers: dict[str, str] | None,
) -> tuple[int, int]:
    if not pending:
        return (0, 0)

    for url, dest in pending:
        _assert_safe_batch_entry(url, dest)
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
            # Single connection per file: the per-request rate matters far
            # more than per-file parallelism for small allele FASTAs, and
            # multi-connection splits multiply the request burst that gets
            # gmlst IPs banned by provider rate limiters.
            "--max-connection-per-server=1",
            "--split=1",
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
