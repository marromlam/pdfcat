"""Security utilities for input validation."""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path


def sanitize_file_path(path: str) -> Path | None:
    """Sanitize and validate a file path."""
    try:
        resolved = Path(path).resolve()

        if not resolved.exists():
            return None
        if not resolved.is_file():
            return None

        path_str = str(resolved)
        dangerous_patterns = [";", "&", "|", "`", "$", ">", "<", "\n", "\r"]
        if any(pattern in path_str for pattern in dangerous_patterns):
            raise ValueError(f"Path contains dangerous characters: {path_str}")

        return resolved
    except OSError as e:
        raise ValueError(f"Invalid file path: {path}") from e


def sanitize_command_args(viewer_cmd: str) -> list[str]:
    """Sanitize viewer command arguments and validate executable."""
    try:
        parts = shlex.split(viewer_cmd)
    except ValueError as e:
        raise ValueError(f"Invalid command syntax: {viewer_cmd}") from e

    if not parts:
        raise ValueError("Empty command")

    executable = shutil.which(parts[0])
    if executable is None:
        raise ValueError(f"Executable not found: {parts[0]}")

    return [executable, *parts[1:]]
