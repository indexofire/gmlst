"""Entry-point ordering: env.sh must apply before import-time env readers.

Provider base URLs (``gmlst/database/providers``), the minimap2 FASTA preset
and the URL guard read their environment variables when the module is
imported, so the env.sh fallback has to run before the CLI package loads.
Each test uses a fresh interpreter with an isolated HOME.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_FILE_URL = "https://example.invalid/db"


@pytest.fixture
def isolated_home(tmp_path: Path) -> dict[str, str]:
    env_dir = tmp_path / ".config" / "gmlst"
    env_dir.mkdir(parents=True)
    (env_dir / "env.sh").write_text(
        f'export GMLST_PUBMLST_BASE_URL="{_FILE_URL}"\n'
        'export GMLST_MINIMAP2_FASTA_PRESET="asm20"\n'
        'export GMLST_TMPDIR="/from-file"\n'
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("GMLST_")}
    env["HOME"] = str(tmp_path)
    return env


def _run(code: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return result.stdout.strip()


def test_entry_applies_env_file_before_import_time_readers(
    isolated_home: dict[str, str],
) -> None:
    code = """
import sys
sys.argv = ["gmlst", "--version"]
from gmlst._entry import main
try:
    main()
except SystemExit:
    pass
from gmlst.database.providers import get_provider
from gmlst.aligners import minimap2
print(get_provider("pubmlst")._base_url)
print(minimap2._FASTA_PRESET)
"""
    out = _run(code, isolated_home).splitlines()

    assert out[-2] == _FILE_URL
    assert out[-1] == "asm20"


def test_python_dash_m_goes_through_entry(isolated_home: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "gmlst", "config", "get", "GMLST_PUBMLST_BASE_URL"],
        env=isolated_home,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )

    assert _FILE_URL in result.stdout


def test_importing_cli_does_not_read_env_file(isolated_home: dict[str, str]) -> None:
    code = """
import os
from click.testing import CliRunner
from gmlst.cli import main
CliRunner().invoke(main, ["config", "get", "GMLST_TMPDIR"])
print(os.environ.get("GMLST_TMPDIR", "UNSET"))
"""
    assert _run(code, isolated_home) == "UNSET"
