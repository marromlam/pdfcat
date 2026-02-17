"""Pytest unit tests for page-state thread safety."""

from __future__ import annotations

import threading
import time

import pytest

from pdfcat.document import Page_State


@pytest.mark.unit
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

    assert not errors


@pytest.mark.unit
def test_begin_prerender_exclusive() -> None:
    page_state = Page_State(0)
    assert page_state.begin_prerender()
    assert not page_state.begin_prerender()
    page_state.end_prerender()
    assert page_state.begin_prerender()
    page_state.end_prerender()
