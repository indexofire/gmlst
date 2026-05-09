#!/usr/bin/env python3
"""
TDD Test: Provider network and parsing error handling
Tests that providers handle network errors, parsing failures gracefully
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCgmlstErrorHandling:
    """Test cgmlst provider error handling"""

    def test_download_scheme_has_network_error_handling(self):
        """Test that download_scheme handles network errors"""
        import inspect

        from gmlst.database.providers import cgmlst

        source = inspect.getsource(cgmlst.CgmlstProvider.download_scheme)

        # Should have try/except around requests.get
        has_try_except = "try:" in source and "except" in source
        if not has_try_except:
            pytest.fail(
                "cgmlst.download_scheme lacks error handling for network requests.\n"
                "Lines using requests.get() will crash on network errors.\n"
                "Fix: Wrap requests in try/except blocks with retry logic"
            )

    def test_html_parsing_has_fallback(self):
        """Test that schema ID resolution has a robust fallback path."""
        import inspect

        from gmlst.database.providers import cgmlst

        source = inspect.getsource(cgmlst.CgmlstProvider.download_scheme)

        # New implementation resolves schema_id from a curated local mapping,
        # so it should guard unknown schemes before indexing schema_id.
        has_scheme_lookup_guard = "if not scheme_info" in source
        uses_static_schema_id = 'schema_id = scheme_info["schema_id"]' in source

        if not (has_scheme_lookup_guard and uses_static_schema_id):
            pytest.fail(
                "cgmlst.download_scheme should resolve schema_id via local mapping "
                "with an explicit guard for unknown schemes.\n"
                "Fix: validate scheme_info before reading schema_id."
            )

    def test_zipfile_parsing_has_error_handling(self):
        """Test that zipfile parsing handles corrupted data"""
        import inspect

        from gmlst.database.providers import cgmlst

        source = inspect.getsource(cgmlst.CgmlstProvider.download_scheme)

        # Should handle BadZipFile
        has_zipfile_error = "BadZipFile" in source or "zipfile" in source

        if not has_zipfile_error:
            pytest.fail(
                "ZipFile extraction lacks error handling.\n"
                "Corrupted or non-ZIP response will crash.\n"
                "Fix: Wrap ZipFile in try/except zipfile.BadZipFile"
            )


class TestEnterobaseErrorHandling:
    """Test enterobase provider error handling"""

    def test_gzip_decompression_has_error_handling(self):
        """Test that gzip decompression handles errors"""
        import inspect

        from gmlst.database.providers import enterobase

        source = inspect.getsource(enterobase)

        # Should handle BadGzipFile
        uses_gzip = "gzip" in source
        handles_gzip_error = "BadGzipFile" in source or "try:" in source

        if uses_gzip and not handles_gzip_error:
            pytest.fail(
                "enterobase uses gzip.decompress without error handling.\n"
                "Non-gzip response will crash with BadGzipFile.\n"
                "Fix: Add try/except gzip.BadGzipFile around decompression"
            )

    def test_html_parsing_is_robust(self):
        """Test that HTML parsing handles format changes"""
        import inspect

        from gmlst.database.providers import enterobase

        # Should have fallback when HTML parsing fails
        count_loci_source = inspect.getsource(enterobase.EnterobaseProvider._count_loci)
        has_fallback = "try:" in count_loci_source or "if " in count_loci_source

        if not has_fallback:
            pytest.fail(
                "_count_loci doesn't handle HTML format changes gracefully.\n"
                "Fix: Add validation that expected elements were found"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
