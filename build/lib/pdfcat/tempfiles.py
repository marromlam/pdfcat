"""Temporary-file tracking utilities."""

from __future__ import annotations

import atexit
import logging
import os
import tempfile
from contextlib import contextmanager
from typing import Any, Generator


class TempFileManager:
    """Track temporary files and clean them up reliably."""

    def __init__(self) -> None:
        self._temp_files: set[str] = set()
        atexit.register(self.cleanup_all)

    @contextmanager
    def temp_file(
        self,
        *,
        suffix: str = "",
        prefix: str = "pdfcat-",
        mode: str = "w",
        encoding: str = "utf-8",
    ) -> Generator[tuple[str, Any], None, None]:
        with tempfile.NamedTemporaryFile(
            mode=mode,
            encoding=encoding,
            suffix=suffix,
            prefix=prefix,
            delete=False,
        ) as tmp:
            path = tmp.name
            self._temp_files.add(path)
            yield path, tmp

    def track(self, path: str) -> None:
        self._temp_files.add(path)

    def cleanup_path(self, path: str) -> None:
        try:
            if os.path.exists(path):
                os.unlink(path)
        except OSError as exc:
            logging.warning("Failed to delete temp file %s: %s", path, exc)
        finally:
            self._temp_files.discard(path)

    def cleanup_all(self) -> None:
        for path in list(self._temp_files):
            self.cleanup_path(path)


_TEMP_FILE_MANAGER = TempFileManager()


def get_temp_file_manager(ctx: Any | None = None) -> TempFileManager:
    """Resolve the active temp-file manager for a viewer context."""
    manager = getattr(ctx, "temp_file_manager", None) if ctx is not None else None
    if isinstance(manager, TempFileManager):
        return manager
    if ctx is not None:
        setattr(ctx, "temp_file_manager", _TEMP_FILE_MANAGER)
    return _TEMP_FILE_MANAGER
