"""Background worker thread pool."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


class WorkerPool:
    """Thread pool for background tasks."""

    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="pdfcat-worker",
        )
        self._active_futures: set[Future[Any]] = set()
        self._lock = threading.Lock()
        self._shutdown = False

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any] | None:
        with self._lock:
            if self._shutdown:
                return None
            future = self._executor.submit(fn, *args, **kwargs)
            self._active_futures.add(future)
            future.add_done_callback(self._on_future_done)
            return future

    def _on_future_done(self, future: Future[Any]) -> None:
        with self._lock:
            self._active_futures.discard(future)
        try:
            exc = future.exception()
        except Exception:
            exc = None
        if exc is not None:
            logging.error("Worker task failed: %s", exc, exc_info=exc)

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
        self._executor.shutdown(wait=wait, cancel_futures=not wait)

    def get_stats(self) -> dict[str, int | bool]:
        with self._lock:
            return {
                "active_tasks": len(self._active_futures),
                "shutdown": self._shutdown,
            }
