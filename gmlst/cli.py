"""Command-line interface for gmlst."""

from __future__ import annotations

import click

from gmlst import __version__
from gmlst.commands.scheme import scheme_group
from gmlst.commands.typing import cmd_typing
from gmlst.commands.utils import utils_group
from gmlst.utils import setup_logging
from gmlst.visual.cli import visual_group

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=HELP_SETTINGS,
    invoke_without_command=True,
    no_args_is_help=True,
)
@click.version_option(__version__, "--version", "-V")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error logging.")
@click.pass_context
def main(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """gmlst — fast MLST cgMLST/wgMLST typing via multiple alignment backends."""
    if verbose and quiet:
        raise click.UsageError("--verbose and --quiet cannot be used together")
    setup_logging(verbose=verbose, quiet=quiet)
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Register commands
main.add_command(cmd_typing, name="typing")
main.add_command(scheme_group, name="scheme")
main.add_command(utils_group, name="utils")
main.add_command(visual_group, name="visual")


if __name__ == "__main__":
    main()
