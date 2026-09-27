"""Configuration registry and env.sh loading (standard library only).

This module is imported by the console entry point before any other gmlst
package so that values from ``~/.config/gmlst/env.sh`` are in the
environment when import-time readers (provider base URLs, aligner
presets, the URL guard) evaluate. Keep it free of third-party and
gmlst-internal imports.
"""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfigEntry:
    """One registry entry describing a supported environment variable."""

    name: str
    description: str
    default: str
    category: str


CONFIG_REGISTRY: list[ConfigEntry] = [
    ConfigEntry("GMLST_CACHE_DIR", "Cache root directory", "~/.cache/gmlst", "Cache"),
    ConfigEntry("GMLST_TMPDIR", "Temp working directory for typing", "/tmp", "Cache"),
    ConfigEntry(
        "GMLST_PUBMLST_BASE_URL",
        "PubMLST REST API base URL",
        "https://rest.pubmlst.org/db",
        "Provider",
    ),
    ConfigEntry(
        "GMLST_PASTEUR_BASE_URL",
        "Pasteur BIGSdb API base URL",
        "https://bigsdb.pasteur.fr/api/db",
        "Provider",
    ),
    ConfigEntry(
        "GMLST_PRIVATE_BIGSDB_URL", "Private BIGSdb instance URL", "", "Provider"
    ),
    ConfigEntry(
        "GMLST_PRIVATE_BIGSDB_NAME", "Private BIGSdb provider name", "", "Provider"
    ),
    ConfigEntry(
        "GMLST_PRIVATE_BIGSDB_LABEL", "Private BIGSdb display label", "", "Provider"
    ),
    ConfigEntry(
        "GMLST_PUBMLST_API_KEY",
        "PubMLST API key (post-2024 data access)",
        "",
        "Auth",
    ),
    ConfigEntry(
        "GMLST_PASTEUR_API_KEY",
        "Pasteur BIGSdb API key (post-2024 data access)",
        "",
        "Auth",
    ),
    ConfigEntry(
        "GMLST_ALLOW_PRIVATE_URLS",
        "Bypass SSRF guard for private URLs (1/0)",
        "0",
        "Security",
    ),
    ConfigEntry("ENTEROBASE_TOKEN", "Enterobase API auth token", "", "Auth"),
    ConfigEntry(
        "GMLST_MINIMAP2_FASTA_PRESET",
        "minimap2 preset for FASTA index/alignment",
        "asm5",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_CANDIDATE_MAX_ALLELES",
        "Max alleles per locus in candidate FASTA (0 = all)",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_MINIMAP2_FASTA_EMIT_CIGAR",
        "minimap2 FASTA emit CIGAR (1/0)",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_MINIMAP2_FASTA_SPEED_PROFILE",
        "minimap2 FASTA speed profile",
        "",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_PREFILTER_MAX_LOCI",
        "Max loci for cgMLST prefilter",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_MINIMAP2_HASH_PREFILTER",
        "Use minimap2 hash prefilter (1/0)",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_MINIMAP2_HASH_REFINE_MAX_LOCI",
        "Max loci for hash refinement",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_MINIMAP2_HASH_LOCI_TOP_N",
        "Top-N loci for hash prefilter",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_MINIMAP2_BSR_CONFIRM_MAX_LOCI",
        "Max loci for BSR confirmation",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_MINIMAP2_ULTRA_SECOND_PASS_MAX_LOCI",
        "Max loci for ultrafast 2nd pass",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_MINIMAP2_REPRESENTATIVE_MAIN_ALIGNMENT",
        "Use representative alignment (1/0)",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_KMA_FASTQ_MEM_MODE", "KMA FASTQ mem mode (1/0)", "0", "cgMLST"
    ),
    ConfigEntry(
        "GMLST_CGMLST_KMA_FASTQ_MEM_CONFIRM_MAX_LOCI",
        "Max loci for KMA FASTQ confirm",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_EXACT_HASH_PREFILTER",
        "Use exact hash prefilter (1/0)",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_EVIDENCE_FALLBACK_BACKEND",
        "Evidence fallback backend",
        "blastn",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_EVIDENCE_FALLBACK_MAX_LOCI",
        "Max loci for evidence fallback",
        "0",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_CDS_PREDICTION_MODE",
        "CDS prediction mode (prodigal/none)",
        "prodigal",
        "cgMLST",
    ),
    ConfigEntry(
        "GMLST_CGMLST_CDS_TRAINING_FILE", "CDS training file path", "", "cgMLST"
    ),
    ConfigEntry("GMLST_CGMLST_CDS_CLOSED_ENDS", "CDS closed ends (1/0)", "0", "cgMLST"),
    ConfigEntry(
        "GMLST_CGMLST_CDS_COORDINATES_OUT", "Output CDS coordinates file", "", "cgMLST"
    ),
    ConfigEntry(
        "GMLST_CGMLST_FASTQ_KMA_AUTO_THREADS",
        "Auto threads for FASTQ KMA (1/0)",
        "0",
        "cgMLST",
    ),
]

REGISTRY_BY_NAME: dict[str, ConfigEntry] = {e.name: e for e in CONFIG_REGISTRY}

ENV_FILE_CANDIDATES = [
    Path.home() / ".config" / "gmlst" / "env.sh",
    Path.home() / ".gmlst" / "env.sh",
]


def find_env_file() -> Path | None:
    for p in ENV_FILE_CANDIDATES:
        if p.exists():
            return p
    return None


def env_file_export_value(name: str) -> str | None:
    """Return the value exported for *name* in the env.sh config file, if any.

    The config file is sourced by the shell before the CLI runs, so its
    values are indistinguishable from other environment variables at
    runtime; matching the live value against the file's export line is the
    closest available provenance heuristic. Later exports win, matching
    shell semantics.
    """
    env_file = find_env_file()
    if env_file is None:
        return None
    prefix = f"export {name}="
    value: str | None = None
    for line in env_file.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        raw = stripped[len(prefix) :]
        try:
            tokens = shlex.split(raw, comments=True)
        except ValueError:
            # Malformed quoting in a user-edited file; skip this line.
            continue
        value = " ".join(tokens)
    return value


def load_env_file_into_environ() -> dict[str, str]:
    """Apply env.sh values into ``os.environ`` for keys not already set.

    ``gmlst config set`` writes env.sh expecting the shell to source it;
    when the current shell hasn't (new machine, subshell, CI), the CLI
    applies the file itself as a fallback layer so ``config show``/``get``
    and authenticated provider downloads see the configured values.
    Explicit environment variables always win. Returns the injected
    mapping.
    """
    if find_env_file() is None:
        return {}
    injected: dict[str, str] = {}
    for entry in CONFIG_REGISTRY:
        if os.environ.get(entry.name):
            continue
        value = env_file_export_value(entry.name)
        if value:
            os.environ[entry.name] = value
            injected[entry.name] = value
    return injected
