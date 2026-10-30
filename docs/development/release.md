# Release Process

Version locations, the release checklist, tagging, and publishing.

If you are preparing a release, keep the release metadata in sync.

### Version locations

- `pixi.toml`, workspace version
- `pyproject.toml`, package version
- `gmlst/__init__.py`, runtime version if applicable in the current release flow
- `CHANGELOG.md`, release notes

### Typical release checklist

1. update version strings
2. update `CHANGELOG.md`
3. run checks and tests
4. create a release commit
5. create a Git tag such as `v0.1.0`
6. publish the GitHub release

Example commands:

```bash
pixi run check
pixi run test
git add pyproject.toml pixi.toml CHANGELOG.md gmlst/__init__.py
git commit -m "chore: prepare release v0.1.0"
git tag v0.1.0
```

If a release does not change one of those files in the current workflow, do not force an edit just to match the checklist. Keep release changes accurate to the actual repository state.

## Release command sequence

```bash
# 1. bump the same version everywhere
grep -n "version" pyproject.toml pixi.toml gmlst/__init__.py

# 2. update CHANGELOG.md ([Unreleased] -> [x.y.z])

# 3. verify
pixi run check
pixi run test
pixi run mkdocs build --strict

# 4. commit and tag
git add pyproject.toml pixi.toml gmlst/__init__.py CHANGELOG.md pixi.lock
git commit -m "release: gmlst x.y.z"
git tag vx.y.z
git push origin main --tags
```

Creating the GitHub release triggers the PyPI and Docker workflows. If the tag
is only a Zenodo snapshot, PyPI keeps the previous version: verify with
`pip index versions gmlst` before advertising the release.

## Version consistency check

```bash
python - <<'PY'
import tomllib
from gmlst import __version__

py = tomllib.load(open("pyproject.toml", "rb"))["project"]["version"]
pixi = tomllib.load(open("pixi.toml", "rb"))["workspace"]["version"]
assert py == pixi == __version__, (py, pixi, __version__)
print("versions agree:", py)
PY
```
