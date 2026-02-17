#!/usr/bin/env python3
"""Thread-safety tests for Page_State."""

import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.document import Page_State


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


def test_concurrent_cache_access() -> None:
    page_state = Page_State(0)
    errors: list[Exception] = []

    def writer() -> None:
        try:
            for i in range(150):
                page_state.set_cached_render(f"pix-{i}", f"mat-{i}")
                page_state.set_cached_ppm(f"ppm-{i}".encode("utf-8"))
                time.sleep(0.0005)
        except Exception as exc:
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(150):
                _ = page_state.get_cached_render()
                _ = page_state.get_cached_ppm()
                _ = page_state.get_cached_visual_key()
                time.sleep(0.0005)
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if errors:
        fail(f"unexpected concurrency errors: {errors!r}")
    pass_("concurrent access is safe")


def test_begin_prerender_exclusive() -> None:
    page_state = Page_State(0)
    if not page_state.begin_prerender():
        fail("first prerender begin should succeed")
    if page_state.begin_prerender():
        fail("second prerender begin should fail while active")
    page_state.end_prerender()
    if not page_state.begin_prerender():
        fail("begin should succeed after end")
    page_state.end_prerender()
    pass_("prerender lock is exclusive")


def main() -> int:
    test_concurrent_cache_access()
    test_begin_prerender_exclusive()
    print("SUCCESS: thread-safety tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
