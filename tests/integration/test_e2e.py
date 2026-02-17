"""End-to-end CLI smoke tests."""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.integration
@pytest.mark.slow
def test_cli_help_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pdfcat", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0
    assert "Usage:" in result.stdout


@pytest.mark.integration
@pytest.mark.slow
def test_cli_version_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pdfcat", "--version"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() != ""

