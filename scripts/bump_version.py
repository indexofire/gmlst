#!/usr/bin/env python3
"""Bump version across all project config files.

Usage:
    python scripts/bump_version.py <new_version>

Example:
    python scripts/bump_version.py 0.2.0

Files updated:
    - gmlst/__init__.py          (__version__)
    - pyproject.toml             (project.version)
    - pixi.toml                  (workspace.version)
    - recipes/gmlst/meta.yaml    ({% set version = "..." %})
    - conda/recipe/meta.yaml     ({% set version = "..." %})
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES_WITH_VERSION: list[tuple[Path, str, str]] = [
    (
        ROOT / "gmlst" / "__init__.py",
        r'__version__ = "[^"]+"',
        '__version__ = "{version}"',
    ),
    (
        ROOT / "pyproject.toml",
        r'^version = "[^"]+"',
        'version = "{version}"',
    ),
    (
        ROOT / "pixi.toml",
        r'^version = "[^"]+"',
        'version = "{version}"',
    ),
    (
        ROOT / "recipes" / "gmlst" / "meta.yaml",
        r"""{% set version = "[^"]+" %}""",
        '{{% set version = "{version}" %}}',
    ),
    (
        ROOT / "conda" / "recipe" / "meta.yaml",
        r"""{% set version = "[^"]+" %}""",
        '{{% set version = "{version}" %}}',
    ),
]


def bump_version(new_version: str) -> None:
    """Update version in all config files."""
    if not re.match(r"\d+\.\d+\.\d+", new_version):
        print(f"ERROR: Invalid version format: {new_version}")
        print("Expected format: X.Y.Z (e.g. 0.2.0)")
        sys.exit(1)

    changed: list[str] = []
    for path, pattern, replacement in FILES_WITH_VERSION:
        if not path.exists():
            print(f"WARN: File not found, skipping: {path}")
            continue
        text = path.read_text()
        new_text, count = re.subn(
            pattern,
            replacement.format(version=new_version),
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if count == 0:
            print(f"WARN: Version pattern not found in: {path}")
            continue
        path.write_text(new_text)
        changed.append(str(path.relative_to(ROOT)))

    print(f"Version bumped to {new_version} in {len(changed)} file(s):")
    for f in changed:
        print(f"  - {f}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py <new_version>")
        print("Example: python bump_version.py 0.2.0")
        sys.exit(1)
    bump_version(sys.argv[1])


if __name__ == "__main__":
    main()
