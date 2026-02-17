#!/usr/bin/env python3
"""Tests for note path traversal protections."""

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pdfcat.document as document_module
from pdfcat.document import Document, _build_note_filename, _slugify_note_title


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


def test_slugify_removes_path_traversal_chars() -> None:
    slug = _slugify_note_title("../foo\\bar/baz")
    if ".." in slug or "/" in slug or "\\" in slug:
        fail(f"slug should not contain traversal chars: {slug!r}")
    pass_("slugify removes path traversal characters")


def test_build_note_filename_blocks_traversal_patterns() -> None:
    filename = _build_note_filename("../../etc/passwd", "/tmp/source.pdf")
    if ".." in filename or "/" in filename or "\\" in filename:
        fail(f"filename should not include traversal segments: {filename!r}")
    if not filename.endswith(".md"):
        fail(f"expected markdown suffix, got {filename!r}")
    pass_("note filename is traversal-safe")


def test_resolve_note_path_validates_containment() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:

        class DummyDoc:
            filename = ""
            citekey = None
            metadata = {}

            @staticmethod
            def _resolve_notes_dir():
                return tmpdir, None

            @staticmethod
            def _note_title():
                return "Safe Title"

        note_path, err = Document._resolve_note_path(DummyDoc())
        if err is not None or note_path is None:
            fail(f"expected valid note path, got err={err!r}")
        # Use realpath to resolve symlinks (e.g., /var -> /private/var on macOS)
        if not os.path.realpath(note_path).startswith(
            os.path.realpath(tmpdir) + os.sep
        ):
            fail("resolved note path should be inside notes dir")
        if not os.path.exists(note_path):
            fail("resolve should initialize note file on first access")

        original = document_module._build_note_filename
        try:
            document_module._build_note_filename = (
                lambda _title, _source: "../escape.md"
            )
            escaped_path, escaped_err = Document._resolve_note_path(DummyDoc())
        finally:
            document_module._build_note_filename = original

        if escaped_path is not None:
            fail("expected escaped path to be rejected")
        if escaped_err is None:
            fail("expected security error when note path escapes notes directory")
        pass_("resolve_note_path enforces notes-dir containment")


def main() -> int:
    test_slugify_removes_path_traversal_chars()
    test_build_note_filename_blocks_traversal_patterns()
    test_resolve_note_path_validates_containment()
    print("SUCCESS: note security tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
