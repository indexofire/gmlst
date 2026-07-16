"""Shared helpers and constants for scheme management commands."""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import sys
from collections.abc import Iterator
from typing import Any, TextIO

from gmlst.commands.common import (
    _DictSchemeInfo,
    _load_blocked_schemes,
    err_console,
)
from gmlst.database.cache import DatabaseCache
from gmlst.database.download import DownloadTool
from gmlst.database.providers import AVAILABLE_PROVIDERS
from gmlst.fasta_io import write_wrapped_sequence


@contextlib.contextmanager
def _locked_local_catalog(cache: DatabaseCache) -> Iterator[None]:
    catalog_path = cache._catalog_path("local")
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = catalog_path.with_suffix(".lock")
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

logger = logging.getLogger(__name__)


def _reject_if_blocked(
    scheme: str, match_info: _DictSchemeInfo | dict[str, Any], provider: str
) -> None:
    """Exit with error if scheme is blocked."""
    blocked = _load_blocked_schemes()
    provider_blocked = blocked.get(provider, set())
    scheme_dir = match_info.get("extra", {}).get("directory", "")
    if scheme in provider_blocked or scheme_dir in provider_blocked:
        err_console.print(
            f"[red]Error:[/red] Scheme '{scheme}' is blocked for provider '{provider}'."
        )
        sys.exit(1)


DOWNLOAD_TOOL_CHOICES: tuple[DownloadTool, ...] = (
    "auto",
    "aria2c",
    "curl",
    "wget",
    "httpx",
    "requests",
)


def _download_tool_choice(value: str) -> DownloadTool:
    lowered = value.lower()
    if lowered == "auto":
        return "auto"
    if lowered == "aria2c":
        return "aria2c"
    if lowered == "curl":
        return "curl"
    if lowered == "wget":
        return "wget"
    if lowered == "httpx":
        return "httpx"
    if lowered == "requests":
        return "requests"
    raise ValueError(f"Unsupported download tool: {value}")


def _provider_choices(
    *, include_local: bool = True, include_all: bool = True
) -> list[str]:
    choices = list(AVAILABLE_PROVIDERS)
    if include_local and "local" not in choices:
        choices.append("local")
    if include_all and "all" not in choices:
        choices.append("all")
    return choices


def _catalog_providers(*, include_local: bool = False) -> list[str]:
    providers = list(AVAILABLE_PROVIDERS)
    if include_local:
        providers.append("local")
    return providers


def _find_catalog_scheme_matches(
    cache: DatabaseCache,
    scheme_name: str,
    *,
    include_local: bool = False,
    ignore_catalog_errors: bool = False,
) -> list[tuple[str, _DictSchemeInfo]]:
    matches: list[tuple[str, _DictSchemeInfo]] = []
    for prov in _catalog_providers(include_local=include_local):
        try:
            scheme_dicts = cache.load_catalog(prov)
        except (OSError, json.JSONDecodeError) as exc:
            if ignore_catalog_errors:
                logger.debug("Skipping catalog for provider '%s': %s", prov, exc)
                continue
            raise
        if not scheme_dicts:
            continue
        for item in scheme_dicts:
            if item.get("scheme_name") == scheme_name:
                normalized = dict(item)
                normalized.setdefault("provider", prov)
                matches.append((prov, _DictSchemeInfo(normalized)))
                break
    return matches


def _exit_scheme_not_found(scheme_name: str) -> None:
    err_console.print(f"[red]Error:[/red] Scheme '{scheme_name}' not found in catalog.")
    err_console.print("Run [bold]gmlst scheme list[/bold] to see available schemes.")
    sys.exit(1)


def _exit_no_novel_data(*, show_expected_hint: bool) -> None:
    err_console.print("[red]Error:[/red] No novel data found in directory.")
    if show_expected_hint:
        err_console.print("Expected: *_novel.fasta and/or profiles_novel.txt")
    sys.exit(1)


def _exit_validation_errors(errors: list[str]) -> None:
    if not errors:
        return
    err_console.print("[red]Validation errors:[/red]")
    for error in errors:
        err_console.print(f"  - {error}")
    sys.exit(1)


def _write_wrapped_sequence(handle: TextIO, sequence: str, *, width: int = 60) -> None:
    write_wrapped_sequence(handle, sequence, width=width)


def _load_schemes(
    cache: DatabaseCache,
    provider: str,
    scheme_type: str,
) -> list[_DictSchemeInfo]:
    """Load schemes from cache, filtered by provider, type, and blocked list."""
    providers_to_check = AVAILABLE_PROVIDERS if provider == "all" else [provider]
    all_schemes: list[_DictSchemeInfo] = []
    for prov in providers_to_check:
        scheme_dicts = cache.load_catalog(prov)
        if scheme_dicts:
            all_schemes.extend(_DictSchemeInfo(d) for d in scheme_dicts)

    if scheme_type != "all":
        target_type = scheme_type.lower()
        all_schemes = [s for s in all_schemes if s.scheme_type.lower() == target_type]
    else:
        all_schemes = [
            s
            for s in all_schemes
            if s.scheme_type.lower() in ("mlst", "cgmlst", "wgmlst", "rmlst")
        ]

    blocked_schemes = _load_blocked_schemes()
    if blocked_schemes:
        all_schemes = [
            s
            for s in all_schemes
            if s.scheme_name not in blocked_schemes.get(s.provider, [])
            and s.extra.get("directory", "") not in blocked_schemes.get(s.provider, [])
        ]

    return all_schemes
