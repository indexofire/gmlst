#!/usr/bin/env bash
#
# release.sh - One-command release automation for gmlst
#
# Usage:   ./scripts/release.sh <version>
# Example: ./scripts/release.sh 0.2.0
#
# Steps: validate → bump → build frontend → build package → validate →
#        update sha256 → commit → tag → push

set -euo pipefail

VERSION="${1:?Usage: $0 <version> (e.g. 0.2.0)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "ERROR: Invalid version format: $VERSION (expected X.Y.Z)"
    exit 1
fi

cd "$ROOT"

echo "=== gmlst release $VERSION ==="

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: Working tree has uncommitted changes. Commit or stash first."
    git status --short
    exit 1
fi

echo "[1/9] Bumping version to $VERSION..."
python scripts/bump_version.py "$VERSION"

echo "[2/9] Building frontend..."
npm --prefix gmlst/web/frontend ci
npm --prefix gmlst/web/frontend run build

echo "[3/9] Building package..."
rm -rf dist/
python -m build

echo "[4/9] Validating package..."
pip install --upgrade twine >/dev/null 2>&1
twine check dist/*

echo "[5/9] Verifying wheel contents..."
python -c "
import zipfile, glob
whl = glob.glob('dist/*.whl')[0]
with zipfile.ZipFile(whl) as z:
    names = z.namelist()
    assert any('app.js' in n for n in names), 'app.js missing from wheel'
    assert any('app.css' in n for n in names), 'app.css missing from wheel'
"
echo "  Wheel OK"

echo "[6/9] Updating conda recipe sha256..."
SDIST_SHA256=$(sha256sum "dist/gmlst-${VERSION}.tar.gz" | cut -d' ' -f1)
for recipe in recipes/gmlst/meta.yaml conda/recipe/meta.yaml; do
    if [ -f "$recipe" ]; then
        sed -i "s/sha256: .*/sha256: ${SDIST_SHA256}/" "$recipe"
        echo "  Updated $recipe"
    fi
done

echo "[7/9] Committing version bump..."
git add -A
git commit -m "chore: bump version to $VERSION"

echo "[8/9] Creating tag v$VERSION..."
git tag -a "v$VERSION" -m "Release v$VERSION"

echo "[9/9] Pushing to remote..."
echo ""
echo "  Commit: chore: bump version to $VERSION"
echo "  Tag:    v$VERSION"
echo ""
read -p "Proceed with push? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git push origin main
    git push origin "v$VERSION"
    echo ""
    echo "=== Release v$VERSION pushed ==="
    echo ""
    echo "Next steps:"
    echo "  1. Create GitHub Release: https://github.com/indexofire/gmlst/releases/new?tag=v$VERSION"
    echo "  2. PyPI publish triggers automatically via publish-pypi.yml"
    echo "  3. bioconda bot auto-detects new PyPI version and creates update PR"
else
    echo ""
    echo "Push cancelled. Tag and commit are local."
    echo "  git push origin main"
    echo "  git push origin v$VERSION"
fi
