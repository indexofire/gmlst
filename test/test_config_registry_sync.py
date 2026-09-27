"""The config registry must list exactly the GMLST_* variables the code reads."""

from __future__ import annotations

import re
from pathlib import Path

from gmlst.config_registry import CONFIG_REGISTRY

_PKG = Path(__file__).resolve().parents[1] / "gmlst"
_VAR = re.compile(r"""["'](GMLST_[A-Z0-9_]+|ENTEROBASE_TOKEN)["']""")
_EXCLUDED_FILES = {"config_registry.py"}
# Read dynamically: bigsdb.py builds f"GMLST_{provider}_API_KEY".
_DYNAMIC_READS = {"GMLST_PUBMLST_API_KEY", "GMLST_PASTEUR_API_KEY"}
# Matches the pattern but is a Flask app.config key, not an env variable.
_NOT_ENV = {"GMLST_VISUAL_TITLE"}


def _vars_read_by_code() -> set[str]:
    found: set[str] = set()
    for path in _PKG.rglob("*.py"):
        if path.name in _EXCLUDED_FILES:
            continue
        found.update(_VAR.findall(path.read_text(encoding="utf-8")))
    return (found - _NOT_ENV) | _DYNAMIC_READS


def test_every_code_variable_is_registered() -> None:
    registered = {e.name for e in CONFIG_REGISTRY}
    missing = _vars_read_by_code() - registered
    assert not missing, f"read by code but not in CONFIG_REGISTRY: {sorted(missing)}"


def test_every_registered_variable_is_read() -> None:
    registered = {e.name for e in CONFIG_REGISTRY}
    dead = registered - _vars_read_by_code()
    assert not dead, f"in CONFIG_REGISTRY but never read: {sorted(dead)}"


def test_registry_names_are_unique() -> None:
    names = [e.name for e in CONFIG_REGISTRY]
    assert len(names) == len(set(names))
