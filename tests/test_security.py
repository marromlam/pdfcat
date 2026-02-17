#!/usr/bin/env python3
"""Security validation tests."""

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.security import sanitize_command_args, sanitize_file_path


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


def test_sanitize_file_path_accepts_existing_file() -> None:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = sanitize_file_path(tmp_path)
        if result is None:
            fail("existing file should resolve to a Path")
        if not result.is_absolute():
            fail("resolved path should be absolute")
        pass_("sanitize_file_path accepts existing file")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def test_sanitize_file_path_rejects_missing_file() -> None:
    missing = os.path.join(tempfile.gettempdir(), "pdfcat-does-not-exist-12345.pdf")
    result = sanitize_file_path(missing)
    if result is not None:
        fail("missing file should return None")
    pass_("sanitize_file_path rejects missing file")


def test_sanitize_file_path_rejects_dangerous_chars() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "unsafe;name.pdf")
        Path(path).write_bytes(b"pdf")
        try:
            sanitize_file_path(path)
            fail("path containing dangerous characters should raise ValueError")
        except ValueError:
            pass_("sanitize_file_path rejects dangerous characters")


def test_sanitize_command_args_resolves_executable() -> None:
    result = sanitize_command_args("echo hello")
    if len(result) != 2:
        fail(f"expected 2 command args, got {result!r}")
    if Path(result[0]).name != "echo":
        fail(f"expected resolved echo executable, got {result[0]!r}")
    if result[1] != "hello":
        fail(f"expected argument preservation, got {result!r}")
    pass_("sanitize_command_args resolves executable path")


def test_sanitize_command_args_rejects_invalid() -> None:
    try:
        sanitize_command_args("")
        fail("empty command should raise ValueError")
    except ValueError:
        pass_("sanitize_command_args rejects empty command")

    try:
        sanitize_command_args("definitely-not-a-real-command-xyz")
        fail("unknown command should raise ValueError")
    except ValueError:
        pass_("sanitize_command_args rejects unknown executable")


def main() -> int:
    test_sanitize_file_path_accepts_existing_file()
    test_sanitize_file_path_rejects_missing_file()
    test_sanitize_file_path_rejects_dangerous_chars()
    test_sanitize_command_args_resolves_executable()
    test_sanitize_command_args_rejects_invalid()
    print("SUCCESS: security tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
