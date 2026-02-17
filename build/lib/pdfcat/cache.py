"""Memory-bounded cache for page rendering."""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """Cached render payload for a single page."""

    key: int
    pixmap: Any
    matrix: Any
    ppm: bytes | None = None
    size_bytes: int = 0

    def estimate_size(self) -> int:
        size = int(self.size_bytes)
        if self.ppm is not None:
            size += len(self.ppm)
        return size


class PageRenderCache:
    """Thread-safe LRU cache with entry and memory bounds."""

    def __init__(
        self,
        *,
        max_entries: int = 10,
        max_bytes: int = 500 * 1024 * 1024,
    ) -> None:
        self._cache: OrderedDict[int, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._max_entries = max(1, int(max_entries))
        self._max_bytes = max(1, int(max_bytes))
        self._current_bytes = 0

    def _entry_size(self, pixmap: Any, ppm: bytes | None) -> int:
        if hasattr(pixmap, "samples"):
            base_size = len(pixmap.samples)
        else:
            width = int(getattr(pixmap, "width", 0) or 0)
            height = int(getattr(pixmap, "height", 0) or 0)
            base_size = max(1, width) * max(1, height) * 4
        if ppm is not None:
            base_size += len(ppm)
        return base_size

    def _evict_lru(self) -> None:
        if not self._cache:
            return
        page_num, entry = self._cache.popitem(last=False)
        self._current_bytes -= entry.estimate_size()
        logging.debug("evicted cached page %s", page_num)

    def get(self, page_num: int) -> CacheEntry | None:
        with self._lock:
            entry = self._cache.get(page_num)
            if entry is None:
                return None
            self._cache.move_to_end(page_num)
            return entry

    def put(self, page_num: int, pixmap: Any, matrix: Any, ppm: bytes | None = None) -> None:
        with self._lock:
            if page_num in self._cache:
                old = self._cache.pop(page_num)
                self._current_bytes -= old.estimate_size()

            entry = CacheEntry(
                key=page_num,
                pixmap=pixmap,
                matrix=matrix,
                ppm=ppm,
                size_bytes=self._entry_size(pixmap, ppm),
            )

            while self._cache and (
                len(self._cache) >= self._max_entries
                or (self._current_bytes + entry.estimate_size()) > self._max_bytes
            ):
                self._evict_lru()

            self._cache[page_num] = entry
            self._current_bytes += entry.estimate_size()
            logging.debug(
                "cache put page=%s entries=%s usage=%.2fMB",
                page_num,
                len(self._cache),
                self._current_bytes / (1024 * 1024),
            )

    def invalidate(self, page_num: int) -> None:
        with self._lock:
            entry = self._cache.pop(page_num, None)
            if entry is not None:
                self._current_bytes -= entry.estimate_size()

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._current_bytes = 0

    def keys(self) -> list[int]:
        with self._lock:
            return list(self._cache.keys())

    def get_stats(self) -> dict[str, float | int]:
        with self._lock:
            return {
                "entries": len(self._cache),
                "max_entries": self._max_entries,
                "bytes": self._current_bytes,
                "max_bytes": self._max_bytes,
                "utilization": self._current_bytes / self._max_bytes,
            }
