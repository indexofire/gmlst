"""gmlst config command group — inspect and manage environment variables."""

from __future__ import annotations

import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

import click
from rich.box import MINIMAL_HEAVY_HEAD
from rich.console import Console
from rich.table import Table

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

console = Console()
err_console = Console(stderr=True)


@dataclass(frozen=True)
class ConfigEntry:
    name: str
    description: str
    default: str
    category: str


_CONFIG_REGISTRY: list[ConfigEntry] = [
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
        "GMLST_MINIMAP2_KMER_ENGINE",
        "minimap2 k-mer scoring engine (python/kmc/auto)",
        "auto",
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

_REGISTRY_BY_NAME: dict[str, ConfigEntry] = {e.name: e for e in _CONFIG_REGISTRY}

_ENV_FILE_CANDIDATES = [
    Path.home() / ".config" / "gmlst" / "env.sh",
    Path.home() / ".gmlst" / "env.sh",
]

_INIT_MARKER = "# gmlst config"

_SHELL_RC_MAP: dict[str, str] = {
    "bash": ".bashrc",
    "zsh": ".zshrc",
    "fish": ".config/fish/config.fish",
}


def _current_value(name: str) -> str:
    return os.environ.get(name, "")


def _find_env_file() -> Path | None:
    for p in _ENV_FILE_CANDIDATES:
        if p.exists():
            return p
    return None


@click.group("config", context_settings=HELP_SETTINGS, no_args_is_help=True)
def config_group() -> None:
    """Inspect and manage gmlst configuration."""


@config_group.command("env", context_settings=HELP_SETTINGS)
def cmd_env() -> None:
    """Print all environment variables in shell format (sourceable)."""
    for entry in _CONFIG_REGISTRY:
        val = _current_value(entry.name)
        if val:
            console.print(f'export {entry.name}="{val}"')


@config_group.command("show", context_settings=HELP_SETTINGS)
def cmd_show() -> None:
    """Show configuration grouped by category."""
    categories: dict[str, list[ConfigEntry]] = {}
    for entry in _CONFIG_REGISTRY:
        categories.setdefault(entry.category, []).append(entry)

    table = Table(
        title="gmlst Configuration",
        box=MINIMAL_HEAVY_HEAD,
        expand=True,
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("Variable", style="cyan", overflow="fold", ratio=3)
    table.add_column("Value", style="green", overflow="fold", ratio=3)
    table.add_column("Default", style="dim", overflow="fold", ratio=2)
    table.add_column("Description", style="white", overflow="fold", ratio=4)

    for _cat_name, entries in sorted(categories.items()):
        for entry in entries:
            val = _current_value(entry.name)
            display_val = val if val else f"[dim]{entry.default}[/dim]"
            table.add_row(entry.name, display_val, entry.default, entry.description)
        table.add_row("", "", "", "")

    console.print(table)

    env_file = _find_env_file()
    if env_file:
        console.print(f"\nConfig file: [bold]{env_file}[/bold]")
    else:
        console.print(
            "\n[dim]No config file found."
            " Use [bold]gmlst config set[/bold]"
            " to create one.[/dim]"
        )


@config_group.command("get", context_settings=HELP_SETTINGS)
@click.argument("name", required=True)
def cmd_get(name: str) -> None:
    """Get the current value of a configuration variable."""
    entry = _REGISTRY_BY_NAME.get(name.upper())
    if not entry:
        err_console.print(f"[red]Unknown variable:[/red] {name}")
        err_console.print(
            "Run [bold]gmlst config show[/bold] to see all available variables."
        )
        sys.exit(1)

    val = _current_value(entry.name)
    if val:
        console.print(val)
    else:
        console.print(f"[dim]{entry.default}[/dim]")


@config_group.command("set", context_settings=HELP_SETTINGS)
@click.argument("name", required=True)
@click.argument("value", required=True)
def cmd_set(name: str, value: str) -> None:
    """Set a configuration variable in the config file.

    The value is written to ~/.config/gmlst/env.sh.
    Source this file in your shell profile to apply the changes:

        source ~/.config/gmlst/env.sh
    """
    entry = _REGISTRY_BY_NAME.get(name.upper())
    if not entry:
        err_console.print(f"[red]Unknown variable:[/red] {name}")
        err_console.print(
            "Run [bold]gmlst config show[/bold] to see all available variables."
        )
        sys.exit(1)

    env_file = _ENV_FILE_CANDIDATES[0]
    env_file.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    if env_file.exists():
        existing = env_file.read_text().splitlines()
        prefix = f"export {entry.name}="
        lines = [ln for ln in existing if not ln.startswith(prefix)]
        if lines and lines[-1].strip():
            lines.append("")

    lines.append(f"export {entry.name}={shlex.quote(value)}")
    env_file.write_text("\n".join(lines) + "\n")

    console.print(f"[green]Set [bold]{entry.name}[/bold] = '{value}'[/green]")
    console.print(f"Written to: [bold]{env_file}[/bold]")
    console.print(f"\nApply now with: [bold]source {env_file}[/bold]")
    console.print(
        "Or run [bold]gmlst config init[/bold] to auto-load in every new shell."
    )


# ---------------------------------------------------------------------------
# config init — inject source line into shell rc file
# ---------------------------------------------------------------------------


def _detect_shell_rc() -> tuple[str, Path | None]:
    """Return *(shell_name, rc_path)* for the current user's shell.

    Falls back to bash when *$SHELL* is unset.  Returns *(name, None)* when
    the shell has no known rc file.
    """
    shell_path = os.environ.get("SHELL", "")
    shell_name = Path(shell_path).name if shell_path else "bash"

    rc_relative = _SHELL_RC_MAP.get(shell_name)
    if rc_relative is None:
        return shell_name, None
    return shell_name, Path.home() / rc_relative


def _build_source_line(shell_name: str) -> str:
    env_path = '"$HOME/.config/gmlst/env.sh"'
    if shell_name == "fish":
        return f"test -f {env_path}; and source {env_path}"
    return f"[ -f {env_path} ] && source {env_path}"


@config_group.command("init", context_settings=HELP_SETTINGS)
def cmd_init() -> None:
    """Add a source line to your shell rc file.

    This makes gmlst environment variables available in every new shell
    session automatically.  Safe to run multiple times — it will not
    duplicate the source line.
    """
    shell_name, rc_path = _detect_shell_rc()

    if rc_path is None:
        err_console.print(
            f"[yellow]Could not detect a rc file for shell '{shell_name}'.[/yellow]"
        )
        err_console.print("Add this line to your shell profile manually:\n")
        err_console.print('  [bold]source "$HOME/.config/gmlst/env.sh"[/bold]')
        sys.exit(1)

    if rc_path.exists() and _INIT_MARKER in rc_path.read_text():
        console.print(f"[green]✓ Already configured in [bold]{rc_path}[/bold].[/green]")
        console.print("Variables will be loaded automatically in every new shell.")
        return

    source_line = _build_source_line(shell_name)

    rc_path.parent.mkdir(parents=True, exist_ok=True)
    with rc_path.open("a") as fh:
        fh.write(f"\n{_INIT_MARKER} >>>\n")
        fh.write(f"{source_line}\n")
        fh.write("# <<< gmlst config <<<\n")

    console.print(f"[green]✓ Added source line to [bold]{rc_path}[/bold].[/green]")
    console.print(
        "Variables from [bold]~/.config/gmlst/env.sh[/bold]"
        " will load in every new shell session."
    )
    console.print(f"\nRestart your shell or run: [bold]source {rc_path}[/bold]")
