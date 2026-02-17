"""Pytest unit tests for note management."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdfcat.document import Document


@pytest.mark.unit
def test_resolve_note_path_creates_header(
    sample_pdf: str, temp_dir: Path, viewer_context
) -> None:
    viewer_context.config.NOTES_DIR = str(temp_dir)
    viewer_context.config._loaded_keys = {"NOTES_DIR"}
    doc = Document(sample_pdf, ctx=viewer_context)
    try:
        note_path, err = doc._resolve_note_path()
        assert err is None
        assert note_path is not None
        assert Path(note_path).exists()
        assert Path(note_path).read_text(encoding="utf-8").startswith("# ")
    finally:
        doc.close()


@pytest.mark.unit
def test_append_note_writes_payload(
    sample_pdf: str, temp_dir: Path, viewer_context
) -> None:
    viewer_context.config.NOTES_DIR = str(temp_dir)
    viewer_context.config._loaded_keys = {"NOTES_DIR"}
    doc = Document(sample_pdf, ctx=viewer_context)
    try:
        err = doc.send_to_notes("pytest note line")
        assert err is None
        note_path, err = doc._resolve_note_path()
        assert err is None
        assert note_path is not None
        content = Path(note_path).read_text(encoding="utf-8")
        assert "pytest note line" in content
    finally:
        doc.close()
