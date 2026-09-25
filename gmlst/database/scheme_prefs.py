"""Loader for the bundled scheme preferences list.

``gmlst/data/scheme_preferences.json`` records the preferred scheme order
for (organism, type) groups that have multiple same-type schemes. Only
entries carrying ``order`` are policy; entries with ``order_suggested``
are pending curation and are ignored here. ``aliases`` merges organism
keys that refer to the same species group (e.g. the three E. coli keys
used by different providers).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SchemePreference:
    """Preferred scheme order for one (organism, type) candidate group."""

    organism: str
    type: str
    order: list[str | dict[str, str]]
    aliases: frozenset[str] = field(default_factory=frozenset)

    def matches_organism(self, name: str) -> bool:
        """Case-insensitive match against the organism or any alias."""
        needle = name.strip().lower()
        return needle == self.organism.strip().lower() or needle in {
            alias.lower() for alias in self.aliases
        }

    @property
    def order_names(self) -> list[str]:
        """Scheme names in preference order (provider dicts flattened)."""
        return [item["name"] if isinstance(item, dict) else item for item in self.order]

    def provider_for(self, scheme_name: str) -> str | None:
        """Return the pinned provider for *scheme_name*, if any."""
        for item in self.order:
            if isinstance(item, dict) and item.get("name") == scheme_name:
                return item.get("provider")
        return None


def load_scheme_preferences(
    path: Path | None = None,
) -> list[SchemePreference]:
    """Load curated preferences; pending (``order_suggested``) entries are skipped."""
    if path is None:
        import importlib.resources as pkg_resources

        path = Path(
            str(pkg_resources.files("gmlst") / "data" / "scheme_preferences.json")
        )
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []

    preferences: list[SchemePreference] = []
    for entry in payload.get("entries", []):
        order = entry.get("order")
        if not order:
            continue
        preferences.append(
            SchemePreference(
                organism=str(entry.get("organism", "")),
                type=str(entry.get("type", "")).lower(),
                order=order,
                aliases=frozenset(entry.get("aliases", [])),
            )
        )
    return preferences


def resolve_preferred_scheme(
    candidates: list[str],
    organism: str,
    scheme_type: str,
    preferences: list[SchemePreference],
) -> str | None:
    """Return the first preference-list scheme present in *candidates*.

    Looks up the preference by organism (or alias) and matching scheme
    type; ``None`` when no curated entry applies or none of its schemes
    are among the candidates.
    """
    for pref in preferences:
        if pref.type != scheme_type.lower() or not pref.matches_organism(organism):
            continue
        for name in pref.order_names:
            if name in candidates:
                return name
        return None
    return None
