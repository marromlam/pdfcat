"""Pytest unit tests for navigator behavior."""

from __future__ import annotations

import pytest

from pdfcat.navigator import DocumentNavigator


class FakePageState:
    def __init__(self) -> None:
        self.stale = False


class FakeDoc:
    def __init__(self) -> None:
        self.page = 1
        self.prevpage = 0
        self.pages = 5
        self.chapter = 0
        self.page_states = [FakePageState() for _ in range(self.pages + 1)]

    def physical_to_logical_page(self, p=None):
        if p is None:
            p = self.page
        return f"L{p + 1}"

    def logical_to_physical_page(self, logical):
        if isinstance(logical, str) and logical.startswith("L"):
            return int(logical[1:]) - 1
        return int(logical)

    def get_toc(self):
        return [[1, "A", 1], [1, "B", 3], [1, "C", 6]]


@pytest.mark.unit
def test_goto_page_bounds_and_stale() -> None:
    doc = FakeDoc()
    nav = DocumentNavigator(doc)
    nav.goto_page(99)
    assert doc.page == doc.pages
    assert doc.page_states[doc.page].stale
    nav.goto_page(-10)
    assert doc.page == 0


@pytest.mark.unit
def test_relative_navigation() -> None:
    doc = FakeDoc()
    nav = DocumentNavigator(doc)
    nav.next_page(2)
    assert doc.page == 3
    nav.prev_page(1)
    assert doc.page == 2


@pytest.mark.unit
def test_logical_navigation() -> None:
    doc = FakeDoc()
    nav = DocumentNavigator(doc)
    nav.goto_logical_page("L4")
    assert doc.page == 3
