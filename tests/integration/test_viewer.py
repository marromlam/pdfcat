"""Integration tests for viewer workflows."""

from __future__ import annotations

import threading

import pytest

from pdfcat.app import view
from pdfcat.document import Document
from pdfcat.runtime_context import set_context


@pytest.mark.integration
def test_viewer_startup_shutdown(sample_pdf: str, viewer_context) -> None:
    doc = Document(sample_pdf, ctx=viewer_context)
    viewer_context.buffers.docs.append(doc)
    file_change = threading.Event()

    # Send immediate quit.
    viewer_context.screen.kb_input.getch.return_value = ord("q")
    set_context(viewer_context)

    with pytest.raises(SystemExit):
        view(file_change, doc)


@pytest.mark.integration
def test_viewer_navigation_flow(multi_page_pdf: str, viewer_context) -> None:
    doc = Document(multi_page_pdf, ctx=viewer_context)
    try:
        doc.navigator.next_page(5)
        assert doc.page == 5
        doc.navigator.prev_page(2)
        assert doc.page == 3
        doc.navigator.goto_page(0)
        assert doc.page == 0
    finally:
        doc.close()

