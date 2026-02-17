"""Pytest unit tests for render cache behavior."""

from __future__ import annotations

import pytest

from pdfcat.cache import PageRenderCache


class MockPixmap:
    def __init__(self, size: int) -> None:
        self.samples = b"x" * size


@pytest.mark.unit
def test_cache_lru_eviction() -> None:
    cache = PageRenderCache(max_entries=3, max_bytes=10 * 1024 * 1024)
    for i in range(3):
        cache.put(i, MockPixmap(128), f"m{i}")

    cache.put(3, MockPixmap(128), "m3")
    assert cache.get(0) is None
    assert cache.get(3) is not None


@pytest.mark.unit
def test_cache_memory_limit() -> None:
    cache = PageRenderCache(max_entries=100, max_bytes=1024)
    cache.put(0, MockPixmap(500), "m0")
    cache.put(1, MockPixmap(500), "m1")
    cache.put(2, MockPixmap(500), "m2")

    stats = cache.get_stats()
    assert int(stats["bytes"]) <= 1024
    assert cache.get(0) is None


@pytest.mark.unit
def test_get_updates_lru_order() -> None:
    cache = PageRenderCache(max_entries=2, max_bytes=10 * 1024 * 1024)
    cache.put(0, MockPixmap(128), "m0")
    cache.put(1, MockPixmap(128), "m1")
    _ = cache.get(0)
    cache.put(2, MockPixmap(128), "m2")

    assert cache.get(0) is not None
    assert cache.get(1) is None
