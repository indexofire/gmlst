"""gmlst config command group — inspect and manage environment variables."""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path
from typing import Any

import click
from rich.box import MINIMAL_HEAVY_HEAD
from rich.console import Console
from rich.table import Table

from gmlst import config_registry as _reg
from gmlst.commands.common import HELP_SETTINGS, emit_versioned_json
from gmlst.config_registry import ConfigEntry
from gmlst.schema_versions import CONFIG_GET_V1

console = Console()
status_console = Console(stderr=True)
err_console = Console(stderr=True)


_INIT_MARKER = "# gmlst config"

_SHELL_RC_MAP: dict[str, str] = {
    "bash": ".bashrc",
    "zsh": ".zshrc",
    "fish": ".config/fish/config.fish",
}


def _current_value(name: str) -> str:
    return os.environ.get(name, "")


def _is_secret(name: str) -> bool:
    """Return True when *name* looks like a credential-bearing variable.

    Deliberately simple name heuristic: values of API keys, tokens,
    secrets, and passwords are masked in display-only views
    (`config show`) to keep them out of logged CLI output.
    """
    upper = name.upper()
    return (
        upper.endswith("_API_KEY")
        or "TOKEN" in upper
        or "SECRET" in upper
        or "PASSWORD" in upper
    )


def _mask_secret(value: str) -> str:
    """Mask *value* for display: fully when short, partially when long."""
    if len(value) <= 8:
        return "********"
    return f"{value[:4]}****{value[-4:]}"


def _get_value_snapshot(entry: ConfigEntry, val: str) -> dict[str, Any]:
    """Build the `config get --format json` payload for *entry*.

    *is_default* is False whenever the environment variable is set, even
    if the explicit value happens to equal the built-in default.
    """
    if val:
        source = "file" if _reg.env_file_export_value(entry.name) == val else "env"
        return {
            "name": entry.name,
            "value": val,
            "source": source,
            "is_default": False,
        }
    return {
        "name": entry.name,
        "value": entry.default,
        "source": "default",
        "is_default": True,
    }


@click.group("config", context_settings=HELP_SETTINGS, no_args_is_help=True)
def config_group() -> None:
    """Inspect and manage gmlst configuration."""


@config_group.command("env", context_settings=HELP_SETTINGS)
def cmd_env() -> None:
    """Print all environment variables in shell format (sourceable)."""
    for entry in _reg.CONFIG_REGISTRY:
        val = _current_value(entry.name)
        if val:
            console.print(f'export {entry.name}="{val}"')


@config_group.command("show", context_settings=HELP_SETTINGS)
def cmd_show() -> None:
    """Show configuration grouped by category."""
    categories: dict[str, list[ConfigEntry]] = {}
    for entry in _reg.CONFIG_REGISTRY:
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

    masked_any_secret = False
    for _cat_name, entries in sorted(categories.items()):
        for entry in entries:
            val = _current_value(entry.name)
            if val and _is_secret(entry.name):
                display_val = _mask_secret(val)
                masked_any_secret = True
            else:
                display_val = val if val else f"[dim]{entry.default}[/dim]"
            table.add_row(entry.name, display_val, entry.default, entry.description)
        table.add_row("", "", "", "")

    console.print(table)

    if masked_any_secret:
        status_console.print(
            "[dim]Secret values are masked in this view;"
            " use 'gmlst config get <NAME>' to retrieve.[/dim]"
        )

    env_file = _reg.find_env_file()
    if env_file:
        status_console.print(f"\nConfig file: [bold]{env_file}[/bold]")
    else:
        status_console.print(
            "\n[dim]No config file found."
            " Use [bold]gmlst config set[/bold]"
            " to create one.[/dim]"
        )


@config_group.command("get", context_settings=HELP_SETTINGS)
@click.argument("name", required=True)
@click.option(
    "--reveal",
    is_flag=True,
    help=(
        "Output the plaintext value of credential-bearing variables. "
        "Without this flag, API keys and tokens are masked so secrets "
        "stay out of logs and terminal transcripts."
    ),
)
@click.option(
    "--format",
    "fmt",
    default="text",
    show_default=True,
    type=click.Choice(["text", "json"]),
    help=(
        "Output format. 'json' emits a versioned envelope whose 'source' "
        "reports provenance: 'file' when the value matches an export in the "
        "env.sh config file, 'env' when set in the environment any other "
        "way, 'default' when unset (built-in default, is_default true)."
    ),
)
def cmd_get(name: str, reveal: bool, fmt: str) -> None:
    """Get the current value of a configuration variable.

    Credential-bearing values are masked unless ``--reveal`` is given.
    """
    entry = _reg.REGISTRY_BY_NAME.get(name.upper())
    if not entry:
        err_console.print(f"[red]Unknown variable:[/red] {name}")
        err_console.print(
            "Run [bold]gmlst config show[/bold] to see all available variables."
        )
        sys.exit(1)

    val = _current_value(entry.name)
    if fmt == "json":
        snapshot = _get_value_snapshot(entry, val)
        masked = bool(snapshot["value"]) and _is_secret(entry.name) and not reveal
        snapshot["value"] = (
            _mask_secret(snapshot["value"]) if masked else snapshot["value"]
        )
        snapshot["is_masked"] = masked
        emit_versioned_json(snapshot, None, CONFIG_GET_V1)
        return

    fallback = val if val else entry.default
    masked = bool(val) and _is_secret(entry.name) and not reveal
    shown = _mask_secret(val) if masked else fallback
    if val:
        console.print(shown)
    else:
        console.print(f"[dim]{shown}[/dim]")


@config_group.command("set", context_settings=HELP_SETTINGS)
@click.argument("name", required=True)
@click.argument("value", required=False)
def cmd_set(name: str, value: str | None) -> None:
    """Set a configuration variable in the config file.

    The value is written to ~/.config/gmlst/env.sh. Omit VALUE to be
    prompted instead — credential-bearing variables are prompted with
    hidden input (and confirmation) so the secret never appears in shell
    history or terminal transcripts.

    Source this file in your shell profile to apply the changes:

        source ~/.config/gmlst/env.sh
    """
    entry = _reg.REGISTRY_BY_NAME.get(name.upper())
    if not entry:
        err_console.print(f"[red]Unknown variable:[/red] {name}")
        err_console.print(
            "Run [bold]gmlst config show[/bold] to see all available variables."
        )
        sys.exit(1)

    if value is None:
        if _is_secret(entry.name):
            value = str(
                click.prompt(
                    f"Value for {entry.name}",
                    hide_input=True,
                    confirmation_prompt=True,
                )
            )
        else:
            value = str(click.prompt(f"Value for {entry.name}"))

    env_file = _reg.ENV_FILE_CANDIDATES[0]
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
    env_file.chmod(0o600)

    shown = _mask_secret(value) if _is_secret(entry.name) else value
    status_console.print(f"[green]Set [bold]{entry.name}[/bold] = '{shown}'[/green]")
    status_console.print(f"Written to: [bold]{env_file}[/bold]")
    status_console.print(f"\nApply now with: [bold]source {env_file}[/bold]")
    status_console.print(
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
        status_console.print(
            f"[green]✓ Already configured in [bold]{rc_path}[/bold].[/green]"
        )
        status_console.print(
            "Variables will be loaded automatically in every new shell."
        )
        return

    source_line = _build_source_line(shell_name)

    rc_path.parent.mkdir(parents=True, exist_ok=True)
    with rc_path.open("a") as fh:
        fh.write(f"\n{_INIT_MARKER} >>>\n")
        fh.write(f"{source_line}\n")
        fh.write("# <<< gmlst config <<<\n")

    status_console.print(
        f"[green]✓ Added source line to [bold]{rc_path}[/bold].[/green]"
    )
    status_console.print(
        "Variables from [bold]~/.config/gmlst/env.sh[/bold]"
        " will load in every new shell session."
    )
    status_console.print(f"\nRestart your shell or run: [bold]source {rc_path}[/bold]")
