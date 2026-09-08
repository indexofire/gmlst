"""Atomic file writes for cache and downloaded data.

Both helpers follow the mkstemp-then-``os.replace`` pattern: content is
written to a temporary file in the destination directory and swapped into
place with an atomic rename, so readers never observe partially written
files and concurrent runs cannot corrupt each other's output.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically write *content* as text to *path*.

    Writes to a ``.tmp`` sibling created by ``mkstemp`` (same filesystem,
    so ``os.replace`` is atomic), then renames it over *path*; the temp
    file is removed if writing fails.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f"{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Atomically write *content* as bytes to *path*.

    Same mkstemp + ``os.replace`` pattern as
    :func:`atomic_write_text`, with cleanup of the temp file on failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f"{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise
