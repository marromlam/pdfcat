#!/usr/bin/env python3
"""Render cache tests."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.cache import PageRenderCache


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


class MockPixmap:
    def __init__(self, size: int) -> None:
        self.samples = b"x" * size


def test_cache_lru_eviction() -> None:
    cache = PageRenderCache(max_entries=3, max_bytes=10 * 1024 * 1024)
    for i in range(3):
        cache.put(i, MockPixmap(128), f"m{i}")

    cache.put(3, MockPixmap(128), "m3")
    if cache.get(0) is not None:
        fail("expected oldest entry to be evicted")
    if cache.get(3) is None:
        fail("expected newest entry to exist")
    pass_("LRU eviction by entry count works")


def test_cache_memory_limit() -> None:
    cache = PageRenderCache(max_entries=100, max_bytes=1024)
    cache.put(0, MockPixmap(500), "m0")
    cache.put(1, MockPixmap(500), "m1")
    cache.put(2, MockPixmap(500), "m2")

    stats = cache.get_stats()
    if int(stats["bytes"]) > 1024:
        fail(f"cache exceeds byte limit: {stats}")
    if cache.get(0) is not None:
        fail("expected first item eviction when byte limit exceeded")
    pass_("byte limit eviction works")


def test_get_updates_lru_order() -> None:
    cache = PageRenderCache(max_entries=2, max_bytes=10 * 1024 * 1024)
    cache.put(0, MockPixmap(128), "m0")
    cache.put(1, MockPixmap(128), "m1")
    _ = cache.get(0)
    cache.put(2, MockPixmap(128), "m2")

    if cache.get(0) is None:
        fail("recently accessed entry should not be evicted")
    if cache.get(1) is not None:
        fail("least-recently-used entry should be evicted")
    pass_("get() updates recency")


def main() -> int:
    test_cache_lru_eviction()
    test_cache_memory_limit()
    test_get_updates_lru_order()
    print("SUCCESS: cache tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
