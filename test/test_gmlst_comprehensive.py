#!/usr/bin/env python3

import subprocess
import sys


def run_command(cmd, timeout=30):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result


def gmlst_cmd(*args: str) -> list[str]:
    return [sys.executable, "-m", "gmlst", *args]


def test_basic_commands():
    result = run_command(gmlst_cmd("--help"))
    assert result.returncode == 0, f"Help failed: {result.stderr}"
    assert "gmlst" in result.stdout, "Help output should mention gmlst"

    result = run_command(gmlst_cmd("--version"))
    assert result.returncode == 0, f"Version failed: {result.stderr}"

    result = run_command(gmlst_cmd("invalidcmd"))
    assert result.returncode != 0, "Invalid command should fail"
    assert (
        "Error" in result.stderr
        or "Invalid" in result.stderr
        or "Usage" in result.stdout
    ), "Invalid command should show an error or usage message"


def test_scheme_listing():
    providers = ["pubmlst", "pasteur", "enterobase", "cgmlst"]

    for provider in providers:
        result = run_command(
            gmlst_cmd("scheme", "list", "-p", provider),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"List schemes failed for {provider}: {result.stderr}"
        )
        assert "total" in result.stdout.lower(), f"No schemes displayed for {provider}"

        if provider in ["enterobase", "cgmlst"]:
            result = run_command(
                gmlst_cmd(
                    "scheme",
                    "list",
                    "-p",
                    provider,
                    "--type",
                    "cgmlst",
                ),
                timeout=60,
            )
            assert result.returncode == 0, (
                f"cgmlst filter failed for {provider}: {result.stderr}"
            )

    result = run_command(
        gmlst_cmd("scheme", "list", "--provider", "all"),
        timeout=120,
    )
    assert result.returncode == 0, f"List all providers failed: {result.stderr}"
    assert "total" in result.stdout, "Combined listing missing"


def test_scheme_uniqueness():
    result = run_command(
        gmlst_cmd("scheme", "list", "--provider", "all"),
        timeout=120,
    )
    assert result.returncode == 0, f"Scheme uniqueness check failed: {result.stderr}"

    scheme_names = []
    for line in result.stdout.split("\n"):
        stripped = line.strip()
        if stripped and stripped.startswith(("✓", "-")):
            parts = stripped.split("|")
            if len(parts) > 2:
                name = parts[1].strip().lstrip("*").strip()
                if name:
                    clean = name.replace("[bold]", "").replace("[/bold]", "")
                    for seg in clean.split():
                        if "_" in seg and any(c.isdigit() for c in seg):
                            scheme_names.append(seg)
                            break

    seen = set()
    duplicates = []
    for name in scheme_names:
        if name in seen:
            duplicates.append(name)
        seen.add(name)

    assert len(duplicates) <= len(scheme_names) * 0.05, (
        f"Too many duplicate scheme names: {duplicates[:5]}"
    )


def test_cgmlst_schemes():
    result = run_command(
        gmlst_cmd("scheme", "list", "-p", "cgmlst", "--type", "cgmlst"),
        timeout=60,
    )
    assert result.returncode == 0, f"cgmlst scheme listing failed: {result.stderr}"

    expected = ["senterica", "ecoli", "abaumannii"]
    for exp in expected:
        assert exp in result.stdout.lower(), f"Expected {exp} in cgmlst schemes"

    assert "cgmlst" in result.stdout.lower()


def test_naming_conventions():
    result = run_command(
        gmlst_cmd("scheme", "list", "--provider", "all"),
        timeout=120,
    )
    assert result.returncode == 0, f"Naming convention check failed: {result.stderr}"

    bad_patterns = []
    for line in result.stdout.split("\n"):
        if line.startswith("│") and "Scheme Name" not in line:
            parts = line.split("│")
            if len(parts) > 2:
                name = parts[1].strip()
                if name and "spp" in name.lower() and not name.startswith("spp"):
                    bad_patterns.append(name)

    assert not bad_patterns, f"Names with 'spp' suffix found: {bad_patterns[:5]}"


def test_error_handling():
    result = run_command(gmlst_cmd("scheme", "list", "-p", "cgmlst", "--type", "mlst"))
    assert "No schemes found" in result.stdout or "No local catalog" in result.stdout, (
        "Invalid type filter should show a no-schemes-message"
    )

    result = run_command(gmlst_cmd("scheme", "list", "-p", "invalid_provider"))
    assert (
        result.returncode != 0
        or "Error" in result.stderr
        or "invalid" in result.stderr.lower()
    ), "Invalid provider should fail or report an error"
