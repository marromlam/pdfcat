"""Viewer runtime context for dependency injection."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ViewerContext:
    """Container for runtime singletons and lifecycle helpers."""

    config: Any
    buffers: Any
    screen: Any
    renderer: Any = None
    worker_pool: Any = None
    temp_file_manager: Any = None
    clean_exit: Any = None
    prerender_adjacent_pages: Any = None
    active_threads: list[threading.Thread] = field(default_factory=list)
    shutdown_event: threading.Event = field(default_factory=threading.Event)

    def cleanup(self) -> None:
        self.shutdown_event.set()
        if self.worker_pool is not None:
            try:
                self.worker_pool.shutdown(wait=True)
            except Exception as exc:
                logging.debug("worker pool cleanup failed: %s", exc)
        if self.temp_file_manager is not None:
            try:
                self.temp_file_manager.cleanup_all()
            except Exception as exc:
                logging.debug("temp file cleanup failed: %s", exc)
        if self.renderer is not None:
            try:
                self.renderer.cleanup()
            except Exception as exc:
                logging.debug("renderer cleanup failed: %s", exc)
