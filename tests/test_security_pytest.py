"""Pytest unit tests for security validation helpers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pdfcat.security import sanitize_command_args, sanitize_file_path


@pytest.mark.unit
def test_sanitize_file_path_accepts_existing_file() -> None:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = sanitize_file_path(tmp_path)
        assert result is not None
        assert result.is_absolute()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@pytest.mark.unit
def test_sanitize_file_path_rejects_missing_file() -> None:
    missing = os.path.join(tempfile.gettempdir(), "pdfcat-does-not-exist-12345.pdf")
    assert sanitize_file_path(missing) is None


@pytest.mark.unit
def test_sanitize_file_path_rejects_dangerous_chars() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "unsafe;name.pdf")
        Path(path).write_bytes(b"pdf")
        with pytest.raises(ValueError):
            sanitize_file_path(path)


@pytest.mark.unit
def test_sanitize_command_args_resolves_executable() -> None:
    result = sanitize_command_args("echo hello")
    assert len(result) == 2
    assert Path(result[0]).name == "echo"
    assert result[1] == "hello"


@pytest.mark.unit
def test_sanitize_command_args_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        sanitize_command_args("")
    with pytest.raises(ValueError):
        sanitize_command_args("definitely-not-a-real-command-xyz")
