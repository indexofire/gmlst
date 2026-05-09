#!/usr/bin/env python3
"""
TDD Test: bigsdb.py duplicate method
Tests that _resolve_seqdef_url is not defined twice
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBigsdbDuplicateMethod:
    """Test for duplicate method definition in bigsdb.py"""

    def test_no_duplicate_resolve_seqdef_url(self):
        """Test that _resolve_seqdef_url is defined only once"""
        import inspect

        from gmlst.database.providers import bigsdb

        # Get source of the module
        source = inspect.getsource(bigsdb)

        # Count definitions of _resolve_seqdef_url
        lines = source.split("\n")
        definition_lines = []

        for i, line in enumerate(lines, 1):
            if "def _resolve_seqdef_url" in line:
                definition_lines.append(i)

        # Should be exactly 1 definition
        if len(definition_lines) > 1:
            pytest.fail(
                "CRITICAL BUG: _resolve_seqdef_url is defined "
                f"{len(definition_lines)} times "
                f"at lines {definition_lines}.\n"
                "The second definition overwrites the first, breaking suffix "
                "handling logic.\n"
                "Fix: Remove the duplicate definition (the second one starting "
                "around line 305)"
            )
        elif len(definition_lines) == 0:
            pytest.fail("Method _resolve_seqdef_url not found!")

    def test_first_resolve_seqdef_url_has_suffix_handling(self):
        """Test that the kept version has suffix handling logic"""
        import inspect

        from gmlst.database.providers import bigsdb

        source = inspect.getsource(bigsdb.BigSdbProvider._resolve_seqdef_url)

        # The first version (lines 261-304) has this important logic:
        # Remove suffix (_1, _2, etc.) if present
        has_suffix_handling = (
            ('"_" in scheme_name' in source or "'_' in scheme_name" in source)
            and "rsplit" in source
            and "isdigit" in source
        )

        if not has_suffix_handling:
            pytest.fail(
                "The kept _resolve_seqdef_url method is missing suffix handling "
                "logic.\n"
                "This breaks scheme name resolution for suffixed names like 'bcc_1'.\n"
                "Fix: Ensure the version with suffix handling (lines 261-304) is kept"
            )


class TestBigsdbErrorHandling:
    """Test for error handling in bigsdb provider"""

    def test_get_json_has_retry(self):
        """Test that _get_json has retry logic"""
        import inspect

        from gmlst.database.providers import bigsdb

        source = inspect.getsource(bigsdb._get_json)

        # Should have retry logic
        has_retry = (
            "for attempt" in source or "while" in source or "retry" in source.lower()
        )

        if not has_retry:
            pytest.fail(
                "_get_json lacks retry logic.\n"
                "Network failures will crash immediately.\n"
                "Fix: Add retry loop with exponential backoff"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
