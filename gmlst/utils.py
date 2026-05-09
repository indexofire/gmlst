"""Shared utilities: subprocess, logging, temp directories, tool checks."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger("gmlst")


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def setup_logging(
    verbose: bool = False,
    quiet: bool = False,
    log_file: str | None = None,
) -> None:
    """Configure root gmlst logger.  Call once from CLI entry point.

    Parameters
    ----------
    verbose:
        If True, enable INFO level logging to console.
    log_file:
        If provided, log DEBUG level to file (implies verbose=True).
    """
    if verbose and quiet:
        raise ValueError("verbose and quiet cannot be enabled together")

    gmlst_logger = logging.getLogger("gmlst")
    gmlst_logger.handlers = []
    gmlst_logger.propagate = False

    level = logging.ERROR if quiet else logging.DEBUG if verbose else logging.WARNING
    gmlst_logger.setLevel(logging.DEBUG if log_file else level)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if not quiet:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO if verbose else logging.WARNING)
        console_handler.setFormatter(formatter)
        gmlst_logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        gmlst_logger.addHandler(file_handler)


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def run_cmd(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    capture: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run an external command with consistent error handling.

    Parameters
    ----------
    cmd:
        Command as a sequence of strings (no shell escaping needed).
    cwd:
        Working directory for the subprocess.
    capture:
        If ``True``, capture stdout/stderr; otherwise inherit from parent.
    check:
        If ``True``, raise :class:`subprocess.CalledProcessError` on failure.

    Returns
    -------
    subprocess.CompletedProcess
        The completed process with ``.stdout`` and ``.stderr`` attributes.
    """
    logger.debug("Running: %s", " ".join(str(c) for c in cmd))
    result = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}):\n"
            f"  cmd : {' '.join(str(c) for c in cmd)}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return result


# ---------------------------------------------------------------------------
# Tool availability
# ---------------------------------------------------------------------------


def require_tool(tool: str) -> Path:
    """Return the full path to *tool*, or raise ``RuntimeError`` if absent."""
    path = shutil.which(tool)
    if path is None:
        raise RuntimeError(
            f"Required tool '{tool}' not found on PATH. "
            "Install it via pixi or conda-forge/bioconda."
        )
    return Path(path)


def tool_version(tool: str, version_flag: str = "--version") -> str:
    """Return the first line of *tool --version* output, or ``"unknown"``."""
    try:
        result = run_cmd([tool, version_flag], capture=True, check=False)
        return (result.stdout or result.stderr).strip().splitlines()[0]
    except (OSError, IndexError):
        return "unknown"


# ---------------------------------------------------------------------------
# Temporary directory context manager
# ---------------------------------------------------------------------------


@contextmanager
def temp_dir(prefix: str = "gmlst_") -> Generator[Path, None, None]:
    """Yield a temporary directory that is cleaned up on exit."""
    root = get_temp_root()
    tmp = tempfile.mkdtemp(prefix=prefix, dir=str(root) if root is not None else None)
    try:
        yield Path(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def get_temp_root() -> Path | None:
    configured = os.getenv("GMLST_TMPDIR")
    if not configured:
        return None
    root = Path(configured)
    root.mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# FASTA helpers
# ---------------------------------------------------------------------------


def count_sequences(fasta: Path) -> int:
    """Count the number of sequences in a FASTA file (supports .gz)."""
    import gzip

    opener = gzip.open if fasta.suffix == ".gz" else open
    count = 0
    with opener(fasta, "rt") as fh:  # type: ignore[call-overload]
        for line in fh:
            if line.startswith(">"):
                count += 1
    return count
