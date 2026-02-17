"""Coordinator for document presentation helpers."""

from __future__ import annotations

from typing import Any

from .presenter_links import PresenterLinks
from .presenter_views import PresenterViews


class DocumentPresenter:
    """Compose presentation helpers for a document."""

    def __init__(self, doc: Any) -> None:
        self.doc = doc
        self._views = PresenterViews(self)
        self._links = PresenterLinks(self)

    def _screen(self) -> Any:
        return self.doc._screen()

    def _config(self) -> Any:
        return self.doc._config()

    def _renderer(self) -> Any:
        return self.doc._renderer()

    def _clean_exit(self) -> None:
        self.doc._clean_exit()

    def show_toc(self, bar: Any) -> None:
        self._views.show_toc(bar)

    def show_meta(self, bar: Any) -> None:
        self._views.show_meta(bar)

    def goto_link(self, link: dict[str, Any]) -> str:
        return self._links.goto_link(link)

    def show_link_hints(self, bar: Any) -> None:
        self._links.show_link_hints(bar)

    def show_links_list(self, bar: Any) -> None:
        self._links.show_links_list(bar)

    def show_links(self, bar: Any) -> None:
        self._links.show_links(bar)
