#!/usr/bin/env python3
"""Tests for DocumentNavigator behavior."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.navigator import DocumentNavigator


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


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


def test_goto_page_bounds_and_stale() -> None:
    doc = FakeDoc()
    nav = DocumentNavigator(doc)
    nav.goto_page(99)
    if doc.page != doc.pages:
        fail("goto_page should clamp upper bound")
    if not doc.page_states[doc.page].stale:
        fail("goto_page should mark current page stale")
    nav.goto_page(-10)
    if doc.page != 0:
        fail("goto_page should clamp lower bound")
    pass_("goto_page clamps bounds and marks stale")


def test_relative_navigation() -> None:
    doc = FakeDoc()
    nav = DocumentNavigator(doc)
    nav.next_page(2)
    if doc.page != 3:
        fail(f"next_page expected 3, got {doc.page}")
    nav.prev_page(1)
    if doc.page != 2:
        fail(f"prev_page expected 2, got {doc.page}")
    pass_("next/prev page navigation works")


def test_logical_navigation() -> None:
    doc = FakeDoc()
    nav = DocumentNavigator(doc)
    nav.goto_logical_page("L4")
    if doc.page != 3:
        fail(f"goto_logical_page expected 3, got {doc.page}")
    pass_("logical page navigation works")


def main() -> int:
    test_goto_page_bounds_and_stale()
    test_relative_navigation()
    test_logical_navigation()
    print("SUCCESS: navigator tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
