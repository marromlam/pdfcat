"""Pytest-native smoke tests for shared fixtures."""

from __future__ import annotations

from pdfcat.document import Document


def test_sample_pdf_fixture(sample_pdf: str) -> None:
    doc = Document(sample_pdf)
    try:
        assert doc.page_count >= 1
    finally:
        doc.close()


def test_context_fixture(viewer_context) -> None:
    assert viewer_context is not None
    assert viewer_context.screen.cols > 0
    assert viewer_context.renderer is not None
