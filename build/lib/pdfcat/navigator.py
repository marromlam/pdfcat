"""Navigation helpers for Document."""

from __future__ import annotations

from typing import Any


class DocumentNavigator:
    """Encapsulate page/chapter navigation logic."""

    def __init__(self, doc: Any) -> None:
        self.doc = doc

    def goto_page(self, p: int) -> None:
        self.doc.prevpage = self.doc.page
        if p > self.doc.pages:
            self.doc.page = self.doc.pages
        elif p < 0:
            self.doc.page = 0
        else:
            self.doc.page = p
        self.doc.logicalpage = self.doc.physical_to_logical_page(self.doc.page)
        self.doc.page_states[self.doc.page].stale = True

    def goto_logical_page(self, p: Any) -> None:
        self.goto_page(self.doc.logical_to_physical_page(p))

    def next_page(self, count: int = 1) -> None:
        current_page = int(self.doc.page) if self.doc.page else 0
        self.goto_page(current_page + count)

    def prev_page(self, count: int = 1) -> None:
        current_page = int(self.doc.page) if self.doc.page else 0
        self.goto_page(current_page - count)

    def goto_chapter(self, n: int) -> None:
        toc = self.doc.get_toc()
        if n > len(toc):
            n = len(toc)
        elif n < 0:
            n = 0
        self.doc.chapter = n
        try:
            self.goto_page(toc[n][2] - 1)
        except Exception:
            self.goto_page(0)

    def current_chapter(self) -> int:
        toc = self.doc.get_toc()
        p = self.doc.page
        for i, ch in enumerate(toc):
            cp = ch[2] - 1
            if cp > p:
                return i - 1
        return len(toc)

    def next_chapter(self, count: int = 1) -> None:
        self.goto_chapter(self.doc.chapter + count)

    def previous_chapter(self, count: int = 1) -> None:
        self.goto_chapter(self.doc.chapter - count)
