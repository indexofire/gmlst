"""Console entry point: apply env.sh, then load and run the CLI.

The CLI package reads several environment variables at import time
(provider base URLs, the minimap2 FASTA preset, the private-URL guard), so
``~/.config/gmlst/env.sh`` must be applied before ``gmlst.cli`` is imported.
``gmlst.cli.main`` stays a plain click group (tests drive it directly
without touching the user's config file).
"""

from __future__ import annotations


def main() -> None:
    from gmlst.config_registry import load_env_file_into_environ

    load_env_file_into_environ()

    from gmlst.cli import main as cli_main

    cli_main()
