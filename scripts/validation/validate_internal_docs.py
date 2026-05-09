from __future__ import annotations

import re
import sys
from pathlib import Path

ARCHIVE_DIR_RE = re.compile(r"^\d{4}-Q[1-4]$")
STABLE_FILE_RE = re.compile(
    r"^(ADR-\d+-[a-z0-9-]+|[a-z0-9_]+_(design|analysis|report))\.md$"
)

REQUIRED_ARCHIVE_FRONTMATTER_KEYS = {
    "status",
    "archived_date",
    "archived_from",
    "archive_reason",
}


def _parse_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}

    frontmatter: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return frontmatter
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"')
    return {}


def _check_internal_structure(root: Path) -> list[str]:
    errors: list[str] = []
    internal_dir = root / "docs" / "internal"
    stable_dir = internal_dir / "stable"
    archive_dir = internal_dir / "archive"

    if not internal_dir.exists():
        return ["Missing docs/internal directory"]
    if not stable_dir.exists():
        errors.append("Missing docs/internal/stable directory")
    if not archive_dir.exists():
        errors.append("Missing docs/internal/archive directory")

    for legacy in ("analysis", "design", "reports"):
        if (internal_dir / legacy).exists():
            errors.append(f"Legacy directory should be removed: docs/internal/{legacy}")

    if stable_dir.exists():
        for path in stable_dir.rglob("*.md"):
            if path.name == "README.md":
                continue
            if not STABLE_FILE_RE.match(path.name):
                errors.append(f"Stable doc naming violation: {path.relative_to(root)}")

    if archive_dir.exists():
        for child in archive_dir.iterdir():
            if child.is_file() and child.name != "README.md":
                errors.append(
                    f"Archive root should contain only README.md: {child.name}"
                )
                continue
            if child.is_dir() and not ARCHIVE_DIR_RE.match(child.name):
                errors.append(
                    f"Archive directory naming violation: {child.relative_to(root)}"
                )

        for path in archive_dir.rglob("*.md"):
            if path.name == "README.md":
                continue
            frontmatter = _parse_frontmatter(path)
            missing = REQUIRED_ARCHIVE_FRONTMATTER_KEYS - set(frontmatter)
            if missing:
                errors.append(
                    "Archive front matter missing keys "
                    f"{sorted(missing)} in {path.relative_to(root)}"
                )
            if frontmatter.get("status") != "archived":
                errors.append(
                    f"Archive status must be 'archived' in {path.relative_to(root)}"
                )

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    errors = _check_internal_structure(root)
    if errors:
        print("Internal docs validation failed:")
        for message in errors:
            print(f"- {message}")
        return 1

    print("Internal docs validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
