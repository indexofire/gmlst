#!/usr/bin/env python3
"""
TDD Test: CLI scheme_obj None check and bare except clauses
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCLIErrorHandling:
    """Test CLI error handling issues"""

    def test_scheme_obj_none_check_exists(self):
        typing_path = Path(__file__).parent.parent / "gmlst" / "commands" / "typing.py"
        source = typing_path.read_text()

        # Check that there's a None check after scheme_obj assignment
        has_none_check = "if scheme_obj is None:" in source

        if not has_none_check:
            pytest.fail(
                "CRITICAL BUG: scheme_obj None check is missing.\n"
                "scheme_obj can be None but .loci is accessed without checking.\n"
                "Fix: Add 'if scheme_obj is None: err_console.print(...); "
                "sys.exit(1)' after line 186"
            )


class TestBareExceptClauses:
    """Test for bare except clauses that should be specific"""

    def test_no_bare_except_in_cli(self):
        typing_path = Path(__file__).parent.parent / "gmlst" / "commands" / "typing.py"
        source = typing_path.read_text()

        # Count bare except clauses (but allow 'except Exception:')
        lines = source.split("\n")
        bare_excepts = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except:" or (
                stripped.startswith("except:")
                and "Exception" not in stripped
                and "(" not in stripped
            ):
                bare_excepts.append((i, line.strip()))

        if bare_excepts:
            locations = "\n".join([f"  Line {ln}: {code}" for ln, code in bare_excepts])
            pytest.fail(
                f"Found {len(bare_excepts)} bare 'except:' "
                "clauses that hide real errors:\n"
                f"{locations}\n\n"
                "Fix: Change 'except:' to 'except Exception:' to still "
                "catch all errors "
                "while allowing KeyboardInterrupt to propagate"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
