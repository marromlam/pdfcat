"""Per-page render state and thread-safe cache metadata."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PageState:
    """Mutable render/cache state for a single document page."""

    number: int
    stale: bool = True
    factor: tuple[float, float] = (1, 1)
    place: tuple[int, int, int, int] = (0, 0, 40, 40)
    crop: Any = None
    cached_pixmap: Any = None
    cached_matrix: Any = None
    cached_ppm: bytes | None = None
    cached_visual_key: Any = None
    last_image_id: int | None = None
    last_place: tuple[int, int, int, int] | None = None
    prerendering: bool = False
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )

    def get_cached_render(self) -> tuple[Any, Any]:
        with self._lock:
            return self.cached_pixmap, self.cached_matrix

    def set_cached_render(self, pixmap: Any, matrix: Any) -> None:
        with self._lock:
            self.cached_pixmap = pixmap
            self.cached_matrix = matrix

    def get_cached_ppm(self) -> bytes | None:
        with self._lock:
            return self.cached_ppm

    def set_cached_ppm(self, ppm: bytes | None) -> None:
        with self._lock:
            self.cached_ppm = ppm

    def get_cached_visual_key(self) -> Any:
        with self._lock:
            return self.cached_visual_key

    def set_cached_visual_key(self, key: Any) -> None:
        with self._lock:
            self.cached_visual_key = key

    def invalidate_cache(self, keep_pixmap: bool = False) -> None:
        with self._lock:
            self.cached_ppm = None
            self.cached_visual_key = None
            if not keep_pixmap:
                self.cached_pixmap = None
                self.cached_matrix = None

    def begin_prerender(self) -> bool:
        with self._lock:
            if self.prerendering:
                return False
            self.prerendering = True
            return True

    def end_prerender(self) -> None:
        with self._lock:
            self.prerendering = False

    def get_last_image(self) -> tuple[int | None, tuple[int, int, int, int] | None]:
        with self._lock:
            return self.last_image_id, self.last_place

    def set_last_image(
        self, image_id: int, placement: tuple[int, int, int, int]
    ) -> None:
        with self._lock:
            self.last_image_id = image_id
            self.last_place = placement
