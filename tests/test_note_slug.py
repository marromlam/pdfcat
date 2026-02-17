#!/usr/bin/env python3
"""Tests for document note slug/hash filename helpers."""

import os
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.document import (
    Document,
    _build_note_filename,
    _short_note_hash,
    _slugify_note_title,
)
from pdfcat.runtime_context import get_context, set_context


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


def test_slugify_handles_unicode_and_symbols() -> None:
    got = _slugify_note_title("My Paper: Über Trends!!")
    expected = "my-paper-uber-trends"
    if got != expected:
        fail(f"expected slug {expected!r}, got {got!r}")
    pass_("slugify normalizes unicode and punctuation")


def test_short_hash_is_stable_and_short() -> None:
    a = _short_note_hash("/tmp/example-a.pdf")
    b = _short_note_hash("/tmp/example-a.pdf")
    c = _short_note_hash("/tmp/example-b.pdf")
    if a != b:
        fail("same input should produce same short hash")
    if a == c:
        fail("different input should produce different short hash")
    if not re.fullmatch(r"[0-9a-f]{8}", a):
        fail(f"short hash should be 8 hex chars, got {a!r}")
    pass_("short hash is stable, distinct, and 8-char hex")


def test_build_note_filename_format() -> None:
    name = _build_note_filename("Paper Title", "/tmp/paper.pdf")
    if not name.startswith("paper-title-"):
        fail(f"unexpected filename prefix: {name!r}")
    if not name.endswith(".md"):
        fail(f"expected markdown suffix, got {name!r}")
    m = re.fullmatch(r"paper-title-([0-9a-f]{8})\.md", name)
    if m is None:
        fail(f"filename should be slug-hash.md, got {name!r}")
    pass_("filename format is slug-shorthash.md")


def test_make_link_falls_back_when_metadata_empty() -> None:
    class DummyDoc:
        citekey = None
        metadata = {"author": "", "title": ""}
        page = 8

        def physical_to_logical_page(self, p=None):
            _ = p
            return "9"

        def _note_title(self):
            return "My PDF"

    got = Document.make_link(DummyDoc())
    expected = "(Unknown, My PDF, 9)"
    if got != expected:
        fail(f"expected fallback link {expected!r}, got {got!r}")
    pass_("make_link fallback avoids empty author/title fields")


def test_resolve_notes_dir_handles_legacy_note_path_directory_with_home_var() -> None:
    old_ctx = get_context()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = os.path.expanduser("~")
            target = os.path.join(tmpdir, "notes-dir")
            # Simulate old NOTE_PATH style config using a shell variable.
            legacy_note_path = (
                target.replace(home, "$HOME") if target.startswith(home) else target
            )

            class DummyConfig:
                _loaded_keys = {"NOTE_PATH"}
                NOTE_PATH = legacy_note_path
                NOTES_DIR = None

            class DummyContext:
                config = DummyConfig()

            set_context(DummyContext())
            notes_dir, err = Document._resolve_notes_dir(object())
            if err is not None:
                fail(f"unexpected notes dir error: {err}")
            if notes_dir != os.path.expanduser(os.path.expandvars(legacy_note_path)):
                fail(f"expected expanded legacy NOTE_PATH dir, got {notes_dir!r}")
            if not os.path.isdir(notes_dir):
                fail("expected resolved notes directory to exist")
            pass_("legacy NOTE_PATH directory with env var resolves correctly")
    finally:
        set_context(old_ctx)


def main() -> int:
    test_slugify_handles_unicode_and_symbols()
    test_short_hash_is_stable_and_short()
    test_build_note_filename_format()
    test_make_link_falls_back_when_metadata_empty()
    test_resolve_notes_dir_handles_legacy_note_path_directory_with_home_var()
    print("SUCCESS: note slug tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
