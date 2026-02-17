"""Utilities for generating safe note filenames."""

from __future__ import annotations

import os
import re
import unicodedata
from hashlib import sha1


def slugify_note_title(value: object) -> str:
    """Convert an arbitrary title into a filesystem-safe slug."""
    text = str(value or "").strip()
    if not text:
        return "untitled"

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = text.replace("..", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace(os.sep, "-")
    if os.altsep is not None:
        text = text.replace(os.altsep, "-")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if text.startswith("."):
        text = text.lstrip(".")
    return text[:80] or "untitled"


def short_note_hash(source: object) -> str:
    """Return a stable short hash for disambiguating note filenames."""
    text = str(source or "")
    digest = sha1(text.encode("utf-8")).hexdigest()
    return digest[:8]


def build_note_filename(title: object, source: object) -> str:
    """Build a note filename as '<slug>-<hash>.md'."""
    slug = slugify_note_title(title)[:80].strip("-") or "untitled"
    short = short_note_hash(source)
    return f"{slug}-{short}.md"
