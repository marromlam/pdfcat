# pdfcat Refactoring Plan

**Status**: Draft
**Created**: 2026-02-15
**Target Completion**: 6 weeks
**Owner**: Engineering Team

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 0: Security Fixes (Week 1)](#phase-0-security-fixes-week-1)
3. [Phase 1: Thread Safety & Memory Management (Week 1-2)](#phase-1-thread-safety--memory-management-week-1-2)
4. [Phase 2: Architecture Refactoring (Week 2-4)](#phase-2-architecture-refactoring-week-2-4)
5. [Phase 3: Testing Infrastructure (Week 4-5)](#phase-3-testing-infrastructure-week-4-5)
6. [Phase 4: Documentation & Packaging (Week 5-6)](#phase-4-documentation--packaging-week-5-6)
7. [Appendix: Code Examples](#appendix-code-examples)

---

## Overview

This document provides a comprehensive, step-by-step plan to address critical issues identified in the staff engineer code review. Each phase includes specific tasks, acceptance criteria, and implementation guidance.

### Priority Levels

- **P0 (Critical)**: Security and data integrity issues - must fix before 1.0
- **P1 (High)**: Maintainability and reliability - needed for collaboration
- **P2 (Medium)**: Technical debt - improves long-term health
- **P3 (Low)**: Nice-to-have improvements

### Success Metrics

- ✅ All P0 security vulnerabilities resolved
- ✅ Test coverage >60% for core modules
- ✅ No functions >200 lines
- ✅ All threading issues resolved
- ✅ Memory usage <500MB for 200-page PDFs
- ✅ CI/CD pipeline passing

---

## Phase 0: Security Fixes (Week 1)

**Priority**: P0
**Estimated Effort**: 3-4 days
**Risk**: High if not addressed

### Task 0.1: Fix Command Injection in GUI Viewer

**File**: `src/pdfcat/app.py:303-335`

#### Current Code (Vulnerable)

```python
def open_external_pdf_viewer(doc) -> str | None:
    viewer = str(getattr(state.config, "GUI_VIEWER", "") or "").strip()
    filename = doc.filename

    if viewer and viewer.lower() not in {"system", "default"}:
        cmd = shlex.split(viewer)
        subprocess.run(cmd + [filename], check=False)  # ⚠️ filename not sanitized
```

#### Implementation Steps

1. **Add path validation function** (new file: `src/pdfcat/security.py`):

```python
"""Security utilities for input validation."""

import os
import shlex
from pathlib import Path
from typing import Optional


def sanitize_file_path(path: str) -> Optional[Path]:
    """
    Sanitize and validate a file path.

    Args:
        path: File path to validate

    Returns:
        Validated Path object or None if invalid

    Raises:
        ValueError: If path contains dangerous patterns
    """
    try:
        # Resolve to absolute path
        resolved = Path(path).resolve()

        # Check that file exists
        if not resolved.exists():
            return None

        # Check that it's a file (not a directory or symlink to dangerous location)
        if not resolved.is_file():
            return None

        # Additional checks for suspicious patterns
        path_str = str(resolved)
        dangerous_patterns = [';', '&', '|', '`', '$', '>', '<', '\n', '\r']
        if any(pattern in path_str for pattern in dangerous_patterns):
            raise ValueError(f"Path contains dangerous characters: {path_str}")

        return resolved

    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid file path: {path}") from e


def sanitize_command_args(viewer_cmd: str) -> list[str]:
    """
    Sanitize viewer command arguments.

    Args:
        viewer_cmd: Command string to sanitize

    Returns:
        List of command arguments

    Raises:
        ValueError: If command contains dangerous patterns
    """
    # Use shlex.split for shell-safe parsing
    try:
        parts = shlex.split(viewer_cmd)
    except ValueError as e:
        raise ValueError(f"Invalid command syntax: {viewer_cmd}") from e

    if not parts:
        raise ValueError("Empty command")

    # Validate that the executable exists
    executable = shutil.which(parts[0])
    if executable is None:
        raise ValueError(f"Executable not found: {parts[0]}")

    return parts
```

2. **Update `open_external_pdf_viewer()`**:

```python
import logging
from .security import sanitize_file_path, sanitize_command_args


def open_external_pdf_viewer(doc) -> str | None:
    """Open current document in external system viewer.

    Args:
        doc: Document to open

    Returns:
        Error message if failed, None if successful
    """
    viewer = str(getattr(state.config, "GUI_VIEWER", "") or "").strip()

    try:
        # Sanitize file path first
        safe_path = sanitize_file_path(doc.filename)
        if safe_path is None:
            return f"Invalid or missing file: {doc.filename}"

        filename = str(safe_path)

        if viewer and viewer.lower() not in {"system", "default"}:
            try:
                # Sanitize command arguments
                cmd = sanitize_command_args(viewer)
                # Use subprocess.run with shell=False for safety
                subprocess.run(
                    cmd + [filename],
                    check=False,
                    shell=False,  # ✅ Explicit no shell
                    timeout=10,   # ✅ Add timeout
                )
                return None
            except ValueError as e:
                logging.error(f"Invalid viewer command: {e}")
                return f"Invalid viewer configuration: {e}"
            except subprocess.TimeoutExpired:
                logging.warning(f"Viewer command timed out: {viewer}")
                return "Viewer failed to start (timeout)"

        # Platform-specific openers
        if sys.platform == "darwin":
            subprocess.run(
                ["open", filename],
                check=False,
                shell=False,
                timeout=10,
            )
            return None

        if os.name == "nt":
            os.startfile(filename)  # type: ignore[attr-defined]
            return None

        opener = shutil.which("xdg-open")
        if opener is None:
            return "No system PDF opener found (missing xdg-open)"

        subprocess.run(
            [opener, filename],
            check=False,
            shell=False,
            timeout=10,
        )
        return None

    except Exception as e:
        logging.exception("Failed to open external viewer")
        return f"Failed to open external viewer: {e}"
```

3. **Replace all `os.system()` calls**:

Search for `os.system` in codebase:
```bash
grep -n "os.system" src/pdfcat/*.py
```

Replace at `app.py:1531`:

```python
# BEFORE (DANGEROUS):
os.system("{} {}".format(state.config.KITTYCMD, ncmd))

# AFTER (SAFE):
try:
    kitty_parts = sanitize_command_args(state.config.KITTYCMD)
    subprocess.run(
        kitty_parts + shlex.split(ncmd),
        check=False,
        shell=False,
        timeout=30,
    )
except ValueError as e:
    logging.error(f"Invalid KITTYCMD configuration: {e}")
    raise SystemExit("Invalid KITTYCMD in config") from e
```

#### Testing

Create `tests/test_security.py`:

```python
"""Security validation tests."""

import pytest
from pathlib import Path
from pdfcat.security import sanitize_file_path, sanitize_command_args


def test_sanitize_file_path_normal(tmp_path):
    """Test normal file path sanitization."""
    test_file = tmp_path / "test.pdf"
    test_file.write_text("test")

    result = sanitize_file_path(str(test_file))
    assert result == test_file.resolve()


def test_sanitize_file_path_dangerous_chars():
    """Test that dangerous characters are rejected."""
    with pytest.raises(ValueError, match="dangerous characters"):
        sanitize_file_path("/tmp/test;rm -rf.pdf")


def test_sanitize_file_path_nonexistent():
    """Test that nonexistent paths return None."""
    result = sanitize_file_path("/nonexistent/file.pdf")
    assert result is None


def test_sanitize_command_args_valid():
    """Test valid command parsing."""
    result = sanitize_command_args("evince --page-label=5")
    assert len(result) == 2
    assert result[0].endswith("evince")  # Full path
    assert result[1] == "--page-label=5"


def test_sanitize_command_args_invalid_executable():
    """Test that invalid executables are rejected."""
    with pytest.raises(ValueError, match="Executable not found"):
        sanitize_command_args("nonexistent_command --arg")


def test_sanitize_command_args_empty():
    """Test that empty commands are rejected."""
    with pytest.raises(ValueError, match="Empty command"):
        sanitize_command_args("")
```

#### Acceptance Criteria

- ✅ All `os.system()` calls removed
- ✅ All `subprocess.run()` calls use `shell=False`
- ✅ All file paths validated before use
- ✅ All external commands validated
- ✅ Tests pass with >90% coverage

---

### Task 0.2: Fix Path Traversal in Notes

**File**: `src/pdfcat/document.py:1625-1658`

#### Current Code (Vulnerable)

```python
def _resolve_note_path(self):
    notes_dir, dir_err = self._resolve_notes_dir()
    # ...
    note_filename = _build_note_filename(title, source)
    note_path = os.path.join(notes_dir, note_filename)  # ⚠️ No validation!
```

#### Implementation Steps

1. **Add path traversal protection to `_resolve_note_path()`**:

```python
def _resolve_note_path(self):
    """Resolve the note file path for this document.

    Returns:
        Tuple of (note_path, error_message)

    Raises:
        ValueError: If path validation fails
    """
    notes_dir, dir_err = self._resolve_notes_dir()
    if dir_err:
        return None, dir_err

    title = self._note_title()
    source = self.filename or self.citekey or title
    if source and os.path.exists(str(source)):
        source = os.path.abspath(str(source))

    # Build note filename (already sanitized by _slugify_note_title)
    note_filename = _build_note_filename(title, source)

    # Construct path
    note_path = os.path.join(notes_dir, note_filename)

    # CRITICAL: Validate that resolved path is inside notes_dir
    try:
        resolved_note_path = os.path.abspath(note_path)
        resolved_notes_dir = os.path.abspath(notes_dir)

        # Check that the note path is actually inside notes_dir
        if not resolved_note_path.startswith(resolved_notes_dir + os.sep):
            error_msg = (
                f"Security: Note path escapes notes directory. "
                f"Path: {resolved_note_path}, "
                f"Expected prefix: {resolved_notes_dir}"
            )
            logging.error(error_msg)
            return None, "Invalid note path (security violation)"

        # Additional check: ensure no directory traversal in filename
        if '..' in note_filename or os.sep in note_filename:
            logging.error(f"Note filename contains path separators: {note_filename}")
            return None, "Invalid note filename (security violation)"

        note_path = resolved_note_path

    except (OSError, ValueError) as e:
        logging.error(f"Path validation failed: {e}")
        return None, "Failed to validate note path"

    # Create the note file on first access with an H1 title header.
    try:
        needs_header = (not os.path.exists(note_path)) or os.path.getsize(note_path) == 0
        if needs_header:
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
    except Exception as e:
        logging.error(f"Failed to initialize note file: {e}")
        return None, "Failed to initialize note file"

    return note_path, None
```

2. **Strengthen `_slugify_note_title()`**:

```python
def _slugify_note_title(value):
    """Convert an arbitrary title into a filesystem-friendly slug.

    Args:
        value: Title to slugify

    Returns:
        Safe filename slug (no path separators or dangerous chars)
    """
    text = str(value or "").strip()
    if not text:
        return "untitled"

    # Normalize unicode
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()

    # Remove/replace dangerous characters
    # CRITICAL: Remove path separators and parent directory references
    text = text.replace("..", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace(os.sep, "-")

    # Convert non-alphanumeric to hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")

    # Ensure result doesn't start with . (hidden file)
    if text.startswith("."):
        text = text.lstrip(".")

    return text[:80] or "untitled"  # Limit length for filesystem compatibility
```

3. **Add validation tests**:

Create `tests/test_note_security.py`:

```python
"""Test note path security."""

import os
import pytest
from pathlib import Path
from pdfcat.document import _slugify_note_title, _build_note_filename


def test_slugify_removes_path_separators():
    """Test that path separators are removed."""
    assert "/" not in _slugify_note_title("foo/bar/baz")
    assert "\\" not in _slugify_note_title("foo\\bar\\baz")
    assert ".." not in _slugify_note_title("../etc/passwd")


def test_slugify_handles_unicode():
    """Test unicode normalization."""
    result = _slugify_note_title("Café résumé")
    assert result == "cafe-resume"


def test_slugify_limits_length():
    """Test that slugs are length-limited."""
    long_title = "a" * 200
    result = _slugify_note_title(long_title)
    assert len(result) <= 80


def test_note_filename_no_traversal():
    """Test that note filenames don't allow traversal."""
    filename = _build_note_filename("../../etc/passwd", "/some/source")
    assert ".." not in filename
    assert "/" not in filename


def test_resolve_note_path_validates_containment(tmp_path):
    """Test that note paths are validated to be inside notes_dir."""
    # This test requires mocking a Document instance
    # See full implementation in test suite
    pass
```

#### Acceptance Criteria

- ✅ All note paths validated against directory traversal
- ✅ Slugification removes all dangerous characters
- ✅ Tests confirm paths stay within `notes_dir`
- ✅ Logging for security violations

---

### Task 0.3: Fix Error Handling & Input Validation

**Files**: Multiple files with bare `except` clauses

#### Implementation Steps

1. **Create standardized error types** (`src/pdfcat/exceptions.py`):

```python
"""Custom exceptions for pdfcat."""


class PdfcatError(Exception):
    """Base exception for pdfcat errors."""
    pass


class DocumentError(PdfcatError):
    """Document-related errors."""
    pass


class RenderError(PdfcatError):
    """Rendering-related errors."""
    pass


class ConfigError(PdfcatError):
    """Configuration-related errors."""
    pass


class SecurityError(PdfcatError):
    """Security validation errors."""
    pass


class NoteError(PdfcatError):
    """Note-taking errors."""
    pass


class NeovimBridgeError(PdfcatError):
    """Neovim integration errors."""
    pass
```

2. **Fix bare except in `bib.py:58`**:

```python
# BEFORE:
try:
    paths = bib.entries[citekey].fields["File"]
except:  # noqa
    raise SystemExit("No file for " + citekey)

# AFTER:
try:
    paths = bib.entries[citekey].fields["File"]
except (KeyError, AttributeError) as e:
    logging.error(f"BibTeX entry missing 'File' field for {citekey}: {e}")
    raise SystemExit(f"No file for {citekey}") from e
```

3. **Fix broad exception handling in `app.py:284-300`**:

```python
# BEFORE:
try:
    doc.init_neovim_bridge()
except BaseException:
    bar.message = "Neovim bridge unavailable"

# AFTER:
from .exceptions import NeovimBridgeError

try:
    doc.init_neovim_bridge()
except NeovimBridgeError as e:
    logging.warning(f"Neovim bridge initialization failed: {e}")
    bar.message = "Neovim bridge unavailable"
except Exception as e:
    logging.error(f"Unexpected error in Neovim bridge: {e}")
    bar.message = "Neovim bridge error"
```

4. **Search and fix all bare excepts**:

```bash
# Find all bare excepts
grep -rn "except:" src/pdfcat/

# Fix each one with specific exception types
```

#### Acceptance Criteria

- ✅ Zero bare `except:` clauses in codebase
- ✅ All exceptions logged with appropriate level
- ✅ Custom exception hierarchy in place
- ✅ No `except BaseException` (use specific types)

---

### Task 0.4: Secure Temporary File Handling

**File**: `src/pdfcat/document.py:266-337`

#### Implementation Steps

1. **Create context manager for temp files**:

```python
import atexit
import tempfile
from contextlib import contextmanager
from typing import Generator


class TempFileManager:
    """Manage temporary files with guaranteed cleanup."""

    def __init__(self) -> None:
        self._temp_files: set[str] = set()
        atexit.register(self.cleanup_all)

    @contextmanager
    def temp_file(
        self,
        suffix: str = "",
        prefix: str = "pdfcat-",
        delete: bool = False,
    ) -> Generator[str, None, None]:
        """
        Create a temporary file with guaranteed cleanup.

        Args:
            suffix: File suffix (e.g., ".txt")
            prefix: File prefix
            delete: Whether to delete on context exit (default: False)

        Yields:
            Path to temporary file
        """
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=suffix,
            prefix=prefix,
            delete=False,  # We handle deletion ourselves
        ) as tmp:
            tmp_path = tmp.name

        self._temp_files.add(tmp_path)

        try:
            yield tmp_path
        finally:
            if delete and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                    self._temp_files.discard(tmp_path)
                except OSError as e:
                    logging.warning(f"Failed to delete temp file {tmp_path}: {e}")

    def cleanup_all(self) -> None:
        """Clean up all tracked temporary files."""
        for path in list(self._temp_files):
            try:
                if os.path.exists(path):
                    os.unlink(path)
                    logging.debug(f"Cleaned up temp file: {path}")
            except OSError as e:
                logging.warning(f"Failed to cleanup temp file {path}: {e}")
        self._temp_files.clear()
```

2. **Update `start_live_text_stream()`**:

```python
def start_live_text_stream(self):
    """Start live text extraction stream for search.

    Returns:
        Path to temporary search file
    """
    self.stop_live_text_stream()

    stop_event = threading.Event()
    self._search_stream_stop_event = stop_event
    self._search_stream_done = False

    # Use temp file manager
    if not hasattr(state, 'temp_file_manager'):
        state.temp_file_manager = TempFileManager()

    # Create temp file (will be cleaned up by manager)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".tsv",
        prefix="pdfcat-search-",
        delete=False,
    ) as tmp:
        self._search_stream_path = tmp.name
        state.temp_file_manager._temp_files.add(tmp.name)

    # ... rest of implementation

    return self._search_stream_path
```

3. **Update `stop_live_text_stream()`**:

```python
def stop_live_text_stream(self) -> None:
    """Stop live text extraction and clean up temp file."""
    if self._search_stream_stop_event is not None:
        self._search_stream_stop_event.set()

    if self._search_stream_thread is not None and self._search_stream_thread.is_alive():
        try:
            self._search_stream_thread.join(timeout=0.5)
        except Exception as e:
            logging.warning(f"Error joining search stream thread: {e}")

    self._search_stream_thread = None
    self._search_stream_stop_event = None
    self._search_stream_done = False

    # Proper cleanup with error handling
    if self._search_stream_path is not None:
        try:
            if os.path.exists(self._search_stream_path):
                os.unlink(self._search_stream_path)
                logging.debug(f"Deleted search stream temp file: {self._search_stream_path}")

            # Remove from temp file manager
            if hasattr(state, 'temp_file_manager'):
                state.temp_file_manager._temp_files.discard(self._search_stream_path)

        except OSError as e:
            # Log but don't fail - temp files will be cleaned up at exit
            logging.warning(f"Failed to delete search stream temp file: {e}")
        finally:
            self._search_stream_path = None
```

#### Acceptance Criteria

- ✅ All temp files tracked and cleaned up
- ✅ Cleanup happens even on abnormal exit
- ✅ No temp file leaks in `/tmp`
- ✅ Proper error logging for cleanup failures

---

## Phase 1: Thread Safety & Memory Management (Week 1-2)

**Priority**: P0/P1
**Estimated Effort**: 5-7 days
**Dependencies**: Phase 0 complete

### Task 1.1: Add Thread Synchronization to Page State

**File**: `src/pdfcat/document.py:1709-1723`

#### Current Code (Race Conditions)

```python
class Page_State:
    def __init__(self, p) -> None:
        self.cached_pixmap = None  # ⚠️ No synchronization!
        self.prerendering = False  # ⚠️ Race condition!
```

#### Implementation Steps

1. **Add thread-safe Page_State class**:

```python
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Page_State:
    """Thread-safe page rendering state.

    Attributes:
        number: Page number
        stale: Whether page needs re-rendering
        factor: Zoom factor
        place: Placement coordinates (left, top, right, bottom)
        crop: Crop rectangle
        cached_pixmap: Cached PyMuPDF pixmap
        cached_matrix: Cached transformation matrix
        cached_ppm: Cached encoded PNG bytes
        cached_visual_key: Cache key for visual transformations
        last_image_id: Last rendered image ID
        last_place: Previous placement
        prerendering: Whether currently pre-rendering
    """

    number: int
    stale: bool = True
    factor: tuple = (1, 1)
    place: tuple = (0, 0, 40, 40)
    crop: Optional[object] = None
    cached_pixmap: Optional[object] = None
    cached_matrix: Optional[object] = None
    cached_ppm: Optional[bytes] = None
    cached_visual_key: Optional[tuple] = None
    last_image_id: Optional[int] = None
    last_place: Optional[tuple] = None
    prerendering: bool = False

    # Thread synchronization
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def get_cached_pixmap(self) -> Optional[object]:
        """Thread-safe getter for cached pixmap."""
        with self._lock:
            return self.cached_pixmap

    def set_cached_pixmap(self, pixmap: Optional[object], matrix: Optional[object] = None) -> None:
        """Thread-safe setter for cached pixmap.

        Args:
            pixmap: Pixmap to cache
            matrix: Optional transformation matrix
        """
        with self._lock:
            self.cached_pixmap = pixmap
            if matrix is not None:
                self.cached_matrix = matrix

    def get_cached_ppm(self) -> Optional[bytes]:
        """Thread-safe getter for cached PPM."""
        with self._lock:
            return self.cached_ppm

    def set_cached_ppm(self, ppm: Optional[bytes]) -> None:
        """Thread-safe setter for cached PPM."""
        with self._lock:
            self.cached_ppm = ppm

    def invalidate_cache(self, keep_pixmap: bool = False) -> None:
        """Thread-safe cache invalidation.

        Args:
            keep_pixmap: If True, keep base pixmap but clear transformations
        """
        with self._lock:
            self.cached_ppm = None
            self.cached_visual_key = None
            if not keep_pixmap:
                self.cached_pixmap = None
                self.cached_matrix = None

    def begin_prerender(self) -> bool:
        """Mark as pre-rendering if not already.

        Returns:
            True if we can start pre-rendering, False if already in progress
        """
        with self._lock:
            if self.prerendering:
                return False
            self.prerendering = True
            return True

    def end_prerender(self) -> None:
        """Mark pre-rendering as complete."""
        with self._lock:
            self.prerendering = False
```

2. **Update `prerender_adjacent_pages()` to use locks**:

```python
def prerender_adjacent_pages(doc, current_page) -> None:
    """Pre-render adjacent pages in background for instant navigation.

    Args:
        doc: Document to pre-render pages for
        current_page: Current page number
    """
    if state.shutdown_event.is_set():
        return

    # Pre-render neighboring pages (bias toward forward navigation)
    pages_to_prerender = []
    if current_page < doc.pages:
        pages_to_prerender.append(current_page + 1)
    if current_page + 1 < doc.pages:
        pages_to_prerender.append(current_page + 2)
    if current_page > 0:
        pages_to_prerender.append(current_page - 1)

    for page_num in pages_to_prerender:
        if state.shutdown_event.is_set():
            break

        page_state = doc.page_states[page_num]

        # Thread-safe check: can we start pre-rendering?
        if not page_state.begin_prerender():
            continue  # Already pre-rendering, skip

        # Check if already cached (thread-safe)
        if page_state.get_cached_pixmap() is not None:
            page_state.end_prerender()
            continue

        try:
            # Load the page
            page = doc.load_page(page_num)

            # Apply cropping (same logic as display_page)
            if doc.manualcrop and doc.manualcroprect != [None, None] and doc.is_pdf:
                page.set_cropbox(fitz.Rect(doc.manualcroprect[0], doc.manualcroprect[1]))
            elif doc.autocrop and doc.is_pdf:
                page.set_cropbox(page.mediabox)
                crop = doc.auto_crop(page)
                page.set_cropbox(crop)
            elif doc.is_pdf:
                page.set_cropbox(page.mediabox)

            # Calculate factor (same as display_page)
            dw = state.scr.width
            dh = state.scr.height - state.scr.cell_height

            if doc.rotation in [0, 180]:
                pw = page.bound().width
                ph = page.bound().height
            else:
                pw = page.bound().height
                ph = page.bound().width

            fx = dw / pw
            fy = dh / ph
            factor = min(fx, fy)

            # Generate pixmap
            mat = fitz.Matrix(factor, factor)
            mat = mat.prerotate(doc.rotation)

            pix = page.get_pixmap(matrix=mat, alpha=doc.alpha)

            # Thread-safe cache update
            page_state.set_cached_pixmap(pix, mat)

            # Pre-encode payload in background
            ppm = pix.tobytes("png")
            page_state.set_cached_ppm(ppm)

            logging.debug(f"Pre-rendered page {page_num}")

        except Exception as e:
            logging.debug(f"Pre-render failed for page {page_num}: {e}")
        finally:
            page_state.end_prerender()
```

3. **Update all page state access to use locks**:

Search for direct access patterns:
```bash
grep -n "page_state\.cached_pixmap = " src/pdfcat/*.py
grep -n "page_state\.cached_ppm = " src/pdfcat/*.py
```

Replace with thread-safe methods:
```python
# BEFORE:
page_state.cached_pixmap = pix
page_state.cached_ppm = pix.tobytes("png")

# AFTER:
page_state.set_cached_pixmap(pix, mat)
page_state.set_cached_ppm(pix.tobytes("png"))
```

#### Testing

Create `tests/test_thread_safety.py`:

```python
"""Test thread safety of page state."""

import threading
import time
import pytest
from pdfcat.document import Page_State


def test_concurrent_cache_access():
    """Test that concurrent access to cache is safe."""
    page_state = Page_State(0)
    errors = []

    def writer():
        try:
            for i in range(100):
                page_state.set_cached_pixmap(f"pixmap_{i}")
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for _ in range(100):
                _ = page_state.get_cached_pixmap()
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread safety errors: {errors}"


def test_begin_prerender_exclusive():
    """Test that only one thread can pre-render at a time."""
    page_state = Page_State(0)

    # First thread should succeed
    assert page_state.begin_prerender() is True

    # Second thread should fail
    assert page_state.begin_prerender() is False

    # After ending, should succeed again
    page_state.end_prerender()
    assert page_state.begin_prerender() is True
```

#### Acceptance Criteria

- ✅ All page state access is thread-safe
- ✅ No race conditions in pre-rendering
- ✅ Thread safety tests pass
- ✅ No deadlocks under load

---

### Task 1.2: Implement Bounded Memory Cache

**File**: `src/pdfcat/document.py`

#### Current Code (Unbounded Cache)

```python
# All pages cached indefinitely - can use 4.5GB for 200-page PDF!
page_state.cached_pixmap = pix
page_state.cached_ppm = pix.tobytes("png")
```

#### Implementation Steps

1. **Create LRU cache manager** (`src/pdfcat/cache.py`):

```python
"""Memory-bounded cache for page rendering."""

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class CacheEntry:
    """Single cache entry with size tracking."""

    key: Any
    pixmap: Any
    ppm: Optional[bytes]
    matrix: Any
    size_bytes: int

    def estimate_size(self) -> int:
        """Estimate memory usage of this entry."""
        size = self.size_bytes
        if self.ppm:
            size += len(self.ppm)
        return size


class PageRenderCache:
    """LRU cache for rendered pages with memory limits.

    This cache automatically evicts least-recently-used pages when
    memory limits are reached.

    Attributes:
        max_entries: Maximum number of cached pages
        max_bytes: Maximum memory usage in bytes
    """

    def __init__(
        self,
        max_entries: int = 10,
        max_bytes: int = 500 * 1024 * 1024,  # 500MB default
    ) -> None:
        self._cache: OrderedDict[int, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._current_bytes = 0

        logging.info(
            f"PageRenderCache initialized: max_entries={max_entries}, "
            f"max_bytes={max_bytes / 1024 / 1024:.1f}MB"
        )

    def get(self, page_num: int) -> Optional[CacheEntry]:
        """Get cached entry and mark as recently used.

        Args:
            page_num: Page number to retrieve

        Returns:
            Cached entry or None if not found
        """
        with self._lock:
            if page_num not in self._cache:
                return None

            # Move to end (mark as recently used)
            self._cache.move_to_end(page_num)
            return self._cache[page_num]

    def put(
        self,
        page_num: int,
        pixmap: Any,
        matrix: Any,
        ppm: Optional[bytes] = None,
    ) -> None:
        """Cache a rendered page.

        Args:
            page_num: Page number
            pixmap: Rendered pixmap
            matrix: Transformation matrix
            ppm: Optional pre-encoded PNG bytes
        """
        with self._lock:
            # Estimate size
            if hasattr(pixmap, 'samples'):
                size = len(pixmap.samples)
            else:
                # Fallback estimate: width * height * 4 (RGBA)
                size = getattr(pixmap, 'width', 1000) * getattr(pixmap, 'height', 1000) * 4

            entry = CacheEntry(
                key=page_num,
                pixmap=pixmap,
                ppm=ppm,
                matrix=matrix,
                size_bytes=size,
            )

            # Remove old entry if exists
            if page_num in self._cache:
                old_entry = self._cache.pop(page_num)
                self._current_bytes -= old_entry.estimate_size()

            # Evict until we have room
            while (
                (len(self._cache) >= self._max_entries or
                 self._current_bytes + entry.estimate_size() > self._max_bytes)
                and len(self._cache) > 0
            ):
                self._evict_lru()

            # Add new entry
            self._cache[page_num] = entry
            self._current_bytes += entry.estimate_size()

            logging.debug(
                f"Cached page {page_num}: "
                f"{entry.estimate_size() / 1024:.1f}KB, "
                f"total: {self._current_bytes / 1024 / 1024:.1f}MB"
            )

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Remove first (least recently used)
        page_num, entry = self._cache.popitem(last=False)
        self._current_bytes -= entry.estimate_size()

        logging.debug(
            f"Evicted page {page_num}: "
            f"{entry.estimate_size() / 1024:.1f}KB, "
            f"remaining: {self._current_bytes / 1024 / 1024:.1f}MB"
        )

    def invalidate(self, page_num: int) -> None:
        """Invalidate cached entry.

        Args:
            page_num: Page number to invalidate
        """
        with self._lock:
            if page_num in self._cache:
                entry = self._cache.pop(page_num)
                self._current_bytes -= entry.estimate_size()
                logging.debug(f"Invalidated page {page_num}")

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._current_bytes = 0
            logging.debug("Cache cleared")

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        with self._lock:
            return {
                "entries": len(self._cache),
                "max_entries": self._max_entries,
                "bytes": self._current_bytes,
                "max_bytes": self._max_bytes,
                "utilization": self._current_bytes / self._max_bytes if self._max_bytes > 0 else 0,
            }
```

2. **Integrate cache into Document class**:

```python
class Document(fitz.Document):
    """PDF Document with caching."""

    def __init__(self, filename=None, **kwargs) -> None:
        super().__init__(filename, **kwargs)
        # ... existing init ...

        # Initialize render cache
        max_cache_mb = int(os.environ.get("PDFCAT_CACHE_MB", "500"))
        self._render_cache = PageRenderCache(
            max_entries=10,
            max_bytes=max_cache_mb * 1024 * 1024,
        )

    def mark_all_pages_stale(self, reset_cache=True) -> None:
        """Mark all pages as needing re-render.

        Args:
            reset_cache: If True, clear render cache
        """
        if reset_cache:
            self._render_cache.clear()
            self.page_states = [Page_State(i) for i in range(0, self.pages + 1)]
            return

        for ps in self.page_states:
            ps.stale = True
            # Invalidate in cache
            self._render_cache.invalidate(ps.number)
```

3. **Update `display_page()` to use cache**:

```python
def display_page(self, bar, p, display=True) -> None:
    """Display a page with caching.

    Args:
        bar: Status bar
        p: Page number
        display: Whether to actually display
    """
    page = self.load_page(p)
    page_state = self.page_states[p]

    # ... cropping logic ...

    # Calculate transformation matrix
    mat = fitz.Matrix(factor, factor)
    mat = mat.prerotate(self.rotation)

    # Try to get from cache
    cached = self._render_cache.get(p)

    if cached and cached.matrix == mat:
        # Cache hit!
        pix = cached.pixmap
        logging.debug(f"Cache hit for page {p}")
    else:
        # Cache miss - render
        pix = page.get_pixmap(matrix=mat, alpha=self.alpha)

        # Store in cache (without visual transformations)
        self._render_cache.put(p, pix, mat)
        logging.debug(f"Cache miss for page {p}, rendered and cached")

    # Apply visual transformations (tint/invert)
    # ... visual transformation logic ...

    # Render to screen
    success = state.renderer.render_pixmap(pix, p, place, state.scr, page_state)

    # ... rest of display logic ...
```

#### Testing

Create `tests/test_cache.py`:

```python
"""Test render cache."""

import pytest
from pdfcat.cache import PageRenderCache, CacheEntry


def test_cache_lru_eviction():
    """Test that LRU eviction works."""
    cache = PageRenderCache(max_entries=3, max_bytes=10 * 1024 * 1024)

    # Add 3 entries
    for i in range(3):
        cache.put(i, f"pixmap_{i}", f"matrix_{i}")

    assert len(cache._cache) == 3

    # Add 4th entry, should evict page 0
    cache.put(3, "pixmap_3", "matrix_3")

    assert len(cache._cache) == 3
    assert cache.get(0) is None  # Evicted
    assert cache.get(1) is not None
    assert cache.get(2) is not None
    assert cache.get(3) is not None


def test_cache_memory_limit():
    """Test that memory limit is enforced."""
    # 1KB limit
    cache = PageRenderCache(max_entries=100, max_bytes=1024)

    # Create mock pixmap with known size
    class MockPixmap:
        samples = b"x" * 500  # 500 bytes

    # Add first entry (500 bytes)
    cache.put(0, MockPixmap(), "matrix_0")
    assert len(cache._cache) == 1

    # Add second entry (500 bytes, total 1000)
    cache.put(1, MockPixmap(), "matrix_1")
    assert len(cache._cache) == 2

    # Add third entry (500 bytes, would exceed limit)
    # Should evict first entry
    cache.put(2, MockPixmap(), "matrix_2")
    assert len(cache._cache) == 2
    assert cache.get(0) is None  # Evicted


def test_cache_get_updates_lru():
    """Test that get() updates LRU order."""
    cache = PageRenderCache(max_entries=2, max_bytes=10 * 1024 * 1024)

    cache.put(0, "pixmap_0", "matrix_0")
    cache.put(1, "pixmap_1", "matrix_1")

    # Access page 0 (make it most recent)
    cache.get(0)

    # Add page 2, should evict page 1 (not 0)
    cache.put(2, "pixmap_2", "matrix_2")

    assert cache.get(0) is not None
    assert cache.get(1) is None  # Evicted
    assert cache.get(2) is not None
```

#### Acceptance Criteria

- ✅ Memory usage stays under configured limit
- ✅ LRU eviction works correctly
- ✅ Cache hit/miss logged for debugging
- ✅ Performance improved for navigation
- ✅ Memory usage <500MB for 200-page PDF

---

### Task 1.3: Thread Pool for Background Tasks

**File**: `src/pdfcat/app.py` and `src/pdfcat/document.py`

#### Current Code (Unbounded Thread Creation)

```python
# New thread for every pre-render!
prerender_thread = threading.Thread(
    target=state.prerender_adjacent_pages,
    args=(self, p),
    daemon=True,
)
prerender_thread.start()
```

#### Implementation Steps

1. **Create thread pool manager** (`src/pdfcat/workers.py`):

```python
"""Background worker thread pool."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Optional


class WorkerPool:
    """Thread pool for background tasks.

    Attributes:
        max_workers: Maximum number of concurrent threads
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pdfcat-worker",
        )
        self._active_futures: set[Future] = set()
        self._lock = threading.Lock()
        self._shutdown = False

        logging.info(f"WorkerPool initialized with {max_workers} workers")

    def submit(
        self,
        fn: Callable,
        *args,
        **kwargs,
    ) -> Optional[Future]:
        """Submit a task to the pool.

        Args:
            fn: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Future object or None if shutdown
        """
        with self._lock:
            if self._shutdown:
                logging.warning("WorkerPool is shutdown, ignoring task submission")
                return None

            future = self._executor.submit(fn, *args, **kwargs)
            self._active_futures.add(future)

            # Clean up on completion
            future.add_done_callback(self._on_future_done)

            return future

    def _on_future_done(self, future: Future) -> None:
        """Callback when a future completes.

        Args:
            future: Completed future
        """
        with self._lock:
            self._active_futures.discard(future)

        # Log any exceptions
        try:
            exception = future.exception(timeout=0)
            if exception:
                logging.error(f"Worker task failed: {exception}", exc_info=exception)
        except Exception:
            pass

    def shutdown(self, wait: bool = True, timeout: float = 5.0) -> None:
        """Shutdown the worker pool.

        Args:
            wait: Whether to wait for tasks to complete
            timeout: Maximum time to wait
        """
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True

        logging.info(f"Shutting down WorkerPool (wait={wait}, timeout={timeout})")

        try:
            self._executor.shutdown(wait=wait, cancel_futures=not wait)
        except Exception as e:
            logging.error(f"Error during WorkerPool shutdown: {e}")

    def get_stats(self) -> dict:
        """Get worker pool statistics.

        Returns:
            Dict with pool statistics
        """
        with self._lock:
            return {
                "active_tasks": len(self._active_futures),
                "shutdown": self._shutdown,
            }
```

2. **Initialize worker pool in state**:

```python
# In app.py, after state initialization:

state.config = Config()
state.config.load_user_config()
state.bufs = Buffers()
state.scr = Screen()
state.renderer = None
state.active_threads = []
state.shutdown_event = threading.Event()

# Add worker pool
from .workers import WorkerPool
state.worker_pool = WorkerPool(max_workers=4)
```

3. **Update pre-rendering to use pool**:

```python
# In document.py display_page():

# BEFORE:
prerender_thread = threading.Thread(
    target=state.prerender_adjacent_pages,
    args=(self, p),
    daemon=True,
)
prerender_thread.start()

# AFTER:
if hasattr(state, 'worker_pool'):
    state.worker_pool.submit(state.prerender_adjacent_pages, self, p)
else:
    logging.warning("Worker pool not available, skipping pre-render")
```

4. **Update cleanup to shutdown pool**:

```python
def clean_exit(message="") -> NoReturn:
    """Clean shutdown of application."""
    # Signal all threads to shutdown
    state.shutdown_event.set()

    # Shutdown worker pool
    if hasattr(state, 'worker_pool'):
        state.worker_pool.shutdown(wait=True, timeout=2.0)

    # ... rest of cleanup ...
```

#### Acceptance Criteria

- ✅ No unbounded thread creation
- ✅ Maximum 4 concurrent background tasks
- ✅ Graceful shutdown of worker pool
- ✅ Exception handling in background tasks

---

## Phase 2: Architecture Refactoring (Week 2-4)

**Priority**: P1
**Estimated Effort**: 10-12 days
**Dependencies**: Phase 1 complete

### Task 2.1: Extract View Loop into Smaller Functions

**File**: `src/pdfcat/app.py:1068-1578`

#### Current Code (1,058-line function)

The `view()` function is massive and handles everything. We need to break it down.

#### Implementation Steps

1. **Create action types** (`src/pdfcat/actions.py`):

```python
"""Action types for viewer commands."""

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class Action:
    """Base class for viewer actions."""
    pass


@dataclass
class NoAction(Action):
    """No action needed."""
    pass


@dataclass
class QuitAction(Action):
    """Quit the application."""
    message: str = ""


@dataclass
class NavigateAction(Action):
    """Navigate to a page."""
    page: int
    relative: bool = False  # If True, page is offset from current


@dataclass
class ToggleAction(Action):
    """Toggle a boolean setting."""
    setting: str  # 'tint', 'invert', 'alpha', 'autocrop'


@dataclass
class RotateAction(Action):
    """Rotate the document."""
    degrees: int  # 90, -90, etc.


@dataclass
class ShowModalAction(Action):
    """Show a modal dialog."""
    modal_type: str  # 'toc', 'meta', 'links', 'help'


@dataclass
class RefreshAction(Action):
    """Refresh the display."""
    reload_document: bool = False


@dataclass
class MessageAction(Action):
    """Display a message."""
    message: str


ActionType = Union[
    NoAction,
    QuitAction,
    NavigateAction,
    ToggleAction,
    RotateAction,
    ShowModalAction,
    RefreshAction,
    MessageAction,
]
```

2. **Create input handler** (`src/pdfcat/input_handler.py`):

```python
"""Keyboard input handling."""

import logging
from typing import Optional
from .actions import (
    Action,
    NoAction,
    QuitAction,
    NavigateAction,
    ToggleAction,
    RotateAction,
    ShowModalAction,
    RefreshAction,
)
from .ui import shortcuts


class InputHandler:
    """Handle keyboard input and map to actions."""

    def __init__(self) -> None:
        self.keys = shortcuts()
        self._count_string = ""
        self._key_stack = [0]

    def reset_state(self) -> None:
        """Reset input state."""
        self._count_string = ""
        self._key_stack = [0]

    def get_count(self) -> int:
        """Get current count value."""
        if self._count_string == "":
            return 1
        return int(self._count_string)

    def get_command_string(self) -> str:
        """Get command string for display."""
        return "".join(map(chr, self._key_stack[::-1]))

    def handle_key(self, key: int, doc) -> Action:
        """Handle a key press and return an action.

        Args:
            key: Key code
            doc: Current document

        Returns:
            Action to perform
        """
        # Handle escape (clear state)
        if key == 27:
            self.reset_state()
            return NoAction()

        # Handle numerals (count)
        if key in range(48, 58):  # 0-9
            self._key_stack = [key] + self._key_stack
            self._count_string = self._count_string + chr(key)
            return NoAction()

        count = self.get_count()

        # Quit
        if key in self.keys.QUIT:
            return QuitAction()

        # Navigation
        if key in self.keys.NEXT_PAGE:
            self.reset_state()
            return NavigateAction(page=count, relative=True)

        if key in self.keys.PREV_PAGE:
            self.reset_state()
            return NavigateAction(page=-count, relative=True)

        if key in self.keys.GOTO_PAGE:
            self.reset_state()
            if self._count_string == "":
                # G without count goes to end
                return NavigateAction(page=doc.pages, relative=False)
            return NavigateAction(page=count, relative=False)

        if key in self.keys.GOTO_PAGE_PHYSICAL:
            self.reset_state()
            target = count if self._count_string else doc.page + 1
            return NavigateAction(page=target - 1, relative=False)

        if key in self.keys.GO_BACK:
            self.reset_state()
            return NavigateAction(page=doc.prevpage, relative=False)

        # Toggles
        if key in self.keys.TOGGLE_TINT:
            self.reset_state()
            return ToggleAction(setting="tint")

        if key in self.keys.TOGGLE_INVERT:
            self.reset_state()
            return ToggleAction(setting="invert")

        if key in self.keys.TOGGLE_ALPHA:
            self.reset_state()
            return ToggleAction(setting="alpha")

        if key in self.keys.TOGGLE_AUTOCROP:
            self.reset_state()
            return ToggleAction(setting="autocrop")

        # Rotation
        if key in self.keys.ROTATE_CW:
            self.reset_state()
            return RotateAction(degrees=90 * count)

        if key in self.keys.ROTATE_CCW:
            self.reset_state()
            return RotateAction(degrees=-90 * count)

        # Modals
        if key in self.keys.SHOW_TOC:
            self.reset_state()
            return ShowModalAction(modal_type="toc")

        if key in self.keys.SHOW_META:
            self.reset_state()
            return ShowModalAction(modal_type="meta")

        if key in self.keys.SHOW_LINKS:
            self.reset_state()
            return ShowModalAction(modal_type="links")

        if key in self.keys.SHOW_HELP:
            self.reset_state()
            return ShowModalAction(modal_type="help")

        # Refresh
        if key in self.keys.REFRESH:
            self.reset_state()
            return RefreshAction(reload_document=True)

        # ... handle other keys ...

        # Unknown key - add to stack
        if key in range(48, 257):
            self._key_stack = [key] + self._key_stack

        return NoAction()
```

3. **Create action executor** (`src/pdfcat/executor.py`):

```python
"""Execute viewer actions."""

import logging
from typing import Optional
from .actions import (
    Action,
    NoAction,
    QuitAction,
    NavigateAction,
    ToggleAction,
    RotateAction,
    ShowModalAction,
    RefreshAction,
    MessageAction,
)


class ActionExecutor:
    """Execute viewer actions on document."""

    def __init__(self, state, clean_exit_fn) -> None:
        self.state = state
        self.clean_exit = clean_exit_fn

    def execute(self, action: Action, doc, bar) -> Optional[str]:
        """Execute an action.

        Args:
            action: Action to execute
            doc: Current document
            bar: Status bar

        Returns:
            Optional message to display
        """
        if isinstance(action, NoAction):
            return None

        if isinstance(action, QuitAction):
            self.clean_exit(action.message)

        if isinstance(action, NavigateAction):
            if action.relative:
                if action.page > 0:
                    doc.next_page(action.page)
                else:
                    doc.prev_page(abs(action.page))
            else:
                doc.goto_page(action.page)
            return None

        if isinstance(action, ToggleAction):
            if action.setting == "tint":
                doc.tint = not doc.tint
                doc.mark_all_pages_stale(reset_cache=False)
            elif action.setting == "invert":
                doc.invert = not doc.invert
                doc.mark_all_pages_stale(reset_cache=False)
            elif action.setting == "alpha":
                doc.alpha = not doc.alpha
                doc.mark_all_pages_stale()
            elif action.setting == "autocrop":
                # Cycle through crop modes
                if doc.manualcroprect != [None, None]:
                    if doc.autocrop:
                        doc.autocrop = False
                        doc.manualcrop = True
                    elif doc.manualcrop:
                        doc.autocrop = False
                        doc.manualcrop = False
                    else:
                        doc.autocrop = True
                else:
                    doc.autocrop = not doc.autocrop
                doc.mark_all_pages_stale()
            return None

        if isinstance(action, RotateAction):
            doc.rotation = (doc.rotation + action.degrees) % 360
            doc.mark_all_pages_stale()
            # Invalidate pixmap cache
            if hasattr(doc, '_render_cache'):
                doc._render_cache.clear()
            return None

        if isinstance(action, ShowModalAction):
            if action.modal_type == "toc":
                doc.show_toc(bar)
            elif action.modal_type == "meta":
                doc.show_meta(bar)
            elif action.modal_type == "links":
                doc.show_links_list(bar)
            elif action.modal_type == "help":
                from .app import show_keybinds_modal
                show_keybinds_modal(doc, bar)
            return None

        if isinstance(action, RefreshAction):
            self.state.scr.clear()
            self.state.scr.get_size()
            self.state.scr.init_terminal()
            if action.reload_document:
                from .app import soft_reload_document
                return soft_reload_document(doc)
            return None

        if isinstance(action, MessageAction):
            return action.message

        logging.warning(f"Unknown action type: {type(action)}")
        return None
```

4. **Refactor `view()` function**:

```python
from .input_handler import InputHandler
from .executor import ActionExecutor


def view(file_change, doc) -> None:
    """Main viewer loop - simplified and modular.

    Args:
        file_change: Event for file change detection
        doc: Document to display
    """
    state.scr.get_size()
    state.scr.init_terminal()

    # Initialize renderer
    try:
        state.renderer = create_renderer()
    except SystemExit as e:
        clean_exit(str(e))

    state.scr.drain_input()

    # Initialize components
    bar = status_bar()
    if doc.citekey:
        bar.message = doc.citekey

    input_handler = InputHandler()
    executor = ActionExecutor(state, clean_exit)

    # Main event loop
    while True:
        # Update display
        bar.cmd = input_handler.get_command_string()
        doc.display_page(bar, doc.page, display=False)

        # Check for external updates
        _poll_external_page_command(doc)
        presenter_msg = sync_presenter_mode(doc)
        if presenter_msg:
            bar.message = presenter_msg

        # Get input
        key = state.scr.kb_input.getch(timeout=0.01)

        # Wait for input if nothing pending
        while key == -1 and not file_change.is_set():
            _poll_external_page_command(doc)
            key = state.scr.kb_input.getch(timeout=0.01)

        # Handle file changes
        if file_change.is_set():
            file_change.clear()
            doc = soft_reload_document(doc)
            continue

        # No key pressed
        if key == -1:
            continue

        # Process key
        action = input_handler.handle_key(key, doc)
        result_msg = executor.execute(action, doc, bar)
        if result_msg:
            bar.message = result_msg
```

This refactoring splits the 1,058-line function into:
- `InputHandler`: ~200 lines (keyboard → action mapping)
- `ActionExecutor`: ~150 lines (action → effect)
- `view()`: ~50 lines (event loop orchestration)

#### Acceptance Criteria

- ✅ No function >200 lines
- ✅ Clear separation: input → action → execution
- ✅ Existing functionality preserved
- ✅ All tests pass

---

### Task 2.2: Remove Global State Module

**File**: `src/pdfcat/state.py`

#### Current Code (Global Mutable State)

```python
config: Any = None
bufs: Any = None
scr: Any = None
renderer: Any = None
```

#### Implementation Steps

1. **Create ViewerContext class** (`src/pdfcat/context.py`):

```python
"""Viewer context for dependency injection."""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import Config, Buffers, Screen
    from .renderers import RenderingEngine
    from .workers import WorkerPool
    from .cache import TempFileManager


@dataclass
class ViewerContext:
    """Runtime context for the PDF viewer.

    This replaces the global state module with explicit dependency injection.

    Attributes:
        config: Application configuration
        buffers: Open document buffers
        screen: Terminal screen interface
        renderer: Graphics rendering engine
        worker_pool: Background task executor
        temp_file_manager: Temporary file tracker
        shutdown_event: Shutdown signal
    """

    config: "Config"
    buffers: "Buffers"
    screen: "Screen"
    renderer: Optional["RenderingEngine"] = None
    worker_pool: Optional["WorkerPool"] = None
    temp_file_manager: Optional["TempFileManager"] = None
    shutdown_event: "threading.Event" = field(default_factory=threading.Event)

    def cleanup(self) -> None:
        """Cleanup resources."""
        # Signal shutdown
        self.shutdown_event.set()

        # Shutdown worker pool
        if self.worker_pool:
            self.worker_pool.shutdown(wait=True, timeout=2.0)

        # Cleanup temp files
        if self.temp_file_manager:
            self.temp_file_manager.cleanup_all()

        # Cleanup renderer
        if self.renderer:
            try:
                self.renderer.cleanup()
            except Exception as e:
                logging.error(f"Renderer cleanup failed: {e}")
```

2. **Update function signatures to accept context**:

```python
# BEFORE:
def clean_exit(message="") -> NoReturn:
    state.shutdown_event.set()
    # ...

# AFTER:
def clean_exit(ctx: ViewerContext, message="") -> NoReturn:
    """Clean shutdown of application.

    Args:
        ctx: Viewer context
        message: Optional exit message
    """
    ctx.cleanup()

    # Close documents
    for doc in ctx.buffers.docs:
        try:
            doc.write_state()
            doc.close()
        except Exception as e:
            logging.error(f"Error closing document: {e}")

    # Clear screen
    if ctx.screen and ctx.screen.console:
        ctx.screen.console.clear()

    if message:
        print(message)

    raise SystemExit()
```

3. **Update all functions to use context**:

```bash
# Find all state.* references
grep -rn "state\." src/pdfcat/*.py | wc -l
# ~150+ references to update
```

Example updates:
```python
# BEFORE:
def display_page(self, bar, p, display=True) -> None:
    dw = state.scr.width
    state.renderer.render_pixmap(...)

# AFTER:
def display_page(self, ctx: ViewerContext, bar, p, display=True) -> None:
    dw = ctx.screen.width
    ctx.renderer.render_pixmap(...)
```

4. **Update main() to create and pass context**:

```python
def main(args=None) -> None:
    """Main entry point.

    Args:
        args: Command line arguments
    """
    if args is None:
        args = sys.argv

    paths, opts = parse_cli_args(args)

    # Create context
    config = Config()
    config.load_user_config()
    if not config.URL_BROWSER:
        config.detect_browser_command()

    buffers = Buffers()
    screen = Screen()

    ctx = ViewerContext(
        config=config,
        buffers=buffers,
        screen=screen,
    )

    # Initialize subsystems
    ctx.worker_pool = WorkerPool(max_workers=4)
    ctx.temp_file_manager = TempFileManager()

    # ... load documents into ctx.buffers ...

    # Set up renderer
    try:
        ctx.renderer = create_renderer(ctx.config)
    except SystemExit as e:
        clean_exit(ctx, str(e))

    # Run viewer
    try:
        view(ctx, file_change, doc)
    except KeyboardInterrupt:
        clean_exit(ctx, "Interrupted by user")
    except Exception as e:
        logging.exception("Error in view")
        clean_exit(ctx, f"Error: {e}")
```

5. **Gradual migration strategy**:

Since this is a large change, do it incrementally:

**Step 1**: Add context parameter to functions but keep state module
```python
def display_page(self, ctx: Optional[ViewerContext] = None, bar, p, display=True):
    # Support both old and new ways temporarily
    if ctx is None:
        # Fallback to global state (deprecated)
        import warnings
        warnings.warn("Using global state is deprecated", DeprecationWarning)
        from . import state as ctx
```

**Step 2**: Update all call sites to pass context

**Step 3**: Remove fallback and state module

#### Acceptance Criteria

- ✅ No global state module
- ✅ All functions accept ViewerContext
- ✅ Easier to test (can mock context)
- ✅ All tests pass

---

### Task 2.3: Split Document Class

**File**: `src/pdfcat/document.py`

The Document class is 1,546 lines with too many responsibilities.

#### Implementation Steps

1. **Create DocumentNavigator** (`src/pdfcat/navigator.py`):

```python
"""Document navigation logic."""

import logging


class DocumentNavigator:
    """Handle document navigation operations.

    Attributes:
        doc: Underlying PDF document
    """

    def __init__(self, doc) -> None:
        self.doc = doc

    def goto_page(self, p: int) -> None:
        """Navigate to specific page.

        Args:
            p: Page number (0-based)
        """
        # Store previous page
        self.doc.prevpage = self.doc.page

        # Clamp to valid range
        if p > self.doc.pages:
            self.doc.page = self.doc.pages
        elif p < 0:
            self.doc.page = 0
        else:
            self.doc.page = p

        # Update logical page
        self.doc.logicalpage = self.doc.physical_to_logical_page(self.doc.page)

        # Mark as stale
        self.doc.page_states[self.doc.page].stale = True

    def goto_logical_page(self, p: int) -> None:
        """Navigate to logical page number.

        Args:
            p: Logical page number
        """
        physical = self.doc.logical_to_physical_page(p)
        self.goto_page(physical)

    def next_page(self, count: int = 1) -> None:
        """Navigate forward by count pages.

        Args:
            count: Number of pages to advance
        """
        current = int(self.doc.page) if self.doc.page else 0
        self.goto_page(current + count)

    def prev_page(self, count: int = 1) -> None:
        """Navigate backward by count pages.

        Args:
            count: Number of pages to go back
        """
        current = int(self.doc.page) if self.doc.page else 0
        self.goto_page(current - count)

    def goto_chapter(self, n: int) -> None:
        """Navigate to chapter by index.

        Args:
            n: Chapter index
        """
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

    def next_chapter(self, count: int = 1) -> None:
        """Navigate forward by count chapters.

        Args:
            count: Number of chapters to advance
        """
        self.goto_chapter(self.doc.chapter + count)

    def previous_chapter(self, count: int = 1) -> None:
        """Navigate backward by count chapters.

        Args:
            count: Number of chapters to go back
        """
        self.goto_chapter(self.doc.chapter - count)

    def current_chapter(self) -> int:
        """Get current chapter index.

        Returns:
            Current chapter index
        """
        toc = self.doc.get_toc()
        p = self.doc.page
        for i, ch in enumerate(toc):
            cp = ch[2] - 1
            if cp > p:
                return i - 1
        return len(toc)
```

2. **Create NoteManager** (`src/pdfcat/notes.py`):

```python
"""Note-taking integration."""

import logging
import os
import shlex
import shutil
import subprocess
from typing import Optional, Tuple


class NoteManager:
    """Manage note-taking for documents.

    Attributes:
        doc: Underlying PDF document
        config: Application configuration
    """

    def __init__(self, doc, config) -> None:
        self.doc = doc
        self.config = config

    def resolve_note_path(self) -> Tuple[Optional[str], Optional[str]]:
        """Resolve the note file path for this document.

        Returns:
            Tuple of (note_path, error_message)
        """
        # Implementation from Task 0.2
        # (includes security validation)
        pass

    def open_notes_editor(self) -> Optional[str]:
        """Open notes editor for this document.

        Returns:
            Error message if failed, None if successful
        """
        note_path, err = self.resolve_note_path()
        if err:
            return err

        nvim_bin = shutil.which("nvim")
        if nvim_bin is None:
            return "nvim not found in PATH"

        tmux_bin = shutil.which("tmux")
        in_tmux = bool(os.environ.get("TMUX"))

        proc = None
        try:
            if in_tmux and tmux_bin is not None:
                cmd = f"{shlex.quote(nvim_bin)} {shlex.quote(note_path)}"
                proc = subprocess.run(
                    [tmux_bin, "display-popup", "-E", cmd],
                    check=False,
                )
            else:
                proc = subprocess.run([nvim_bin, note_path], check=False)
        except Exception as e:
            logging.error(f"Failed to open notes editor: {e}")
            return "Failed to open notes editor"

        if proc is not None and proc.returncode not in (0,):
            return "Notes editor exited with errors"
        return None

    def copy_page_link_reference(self) -> Optional[str]:
        """Copy page reference to clipboard.

        Returns:
            Error message if failed, None if successful
        """
        try:
            import pyperclip
            link = self.doc.make_link()
            pyperclip.copy(link)
        except Exception as e:
            logging.error(f"Failed to copy link reference: {e}")
            return "Failed to copy link reference"
        return None

    def append_note(self, text: str) -> Optional[str]:
        """Append text to notes file.

        Args:
            text: Text to append

        Returns:
            Error message if failed, None if successful
        """
        note_path, err = self.resolve_note_path()
        if err:
            return err

        if isinstance(text, list):
            payload = "\n".join(str(t) for t in text)
        else:
            payload = str(text)

        if payload and not payload.endswith("\n"):
            payload += "\n"

        try:
            with open(note_path, "a", encoding="utf-8") as f:
                f.write(payload)
        except Exception as e:
            logging.error(f"Failed to write note: {e}")
            return "Failed to write note"

        return None
```

3. **Create DocumentPresenter** (`src/pdfcat/presenter.py`):

```python
"""UI presentation logic for documents."""

import logging
import sys
from typing import Optional


class DocumentPresenter:
    """Handle UI presentation for documents.

    Attributes:
        doc: Underlying PDF document
        ctx: Viewer context
    """

    def __init__(self, doc, ctx) -> None:
        self.doc = doc
        self.ctx = ctx

    def show_toc(self, bar) -> None:
        """Show table of contents modal.

        Args:
            bar: Status bar
        """
        # Implementation from document.py:810-912
        pass

    def show_meta(self, bar) -> None:
        """Show metadata modal.

        Args:
            bar: Status bar
        """
        # Implementation from document.py:949-1012
        pass

    def show_link_hints(self, bar) -> None:
        """Show link hints overlay.

        Args:
            bar: Status bar
        """
        # Implementation from document.py:1214-1275
        pass

    def show_links_list(self, bar) -> None:
        """Show full links list.

        Args:
            bar: Status bar
        """
        # Implementation from document.py:1379-1453
        pass
```

4. **Update Document class to use composition**:

```python
class Document(fitz.Document):
    """PDF Document with rendering and interaction.

    This class now focuses on core PDF operations and delegates
    specialized concerns to helper classes.
    """

    def __init__(self, filename=None, ctx=None, **kwargs) -> None:
        super().__init__(filename, **kwargs)

        self.ctx = ctx
        self.filename = filename

        # ... core PDF attributes ...

        # Composed helpers
        self.navigator = DocumentNavigator(self)
        if ctx:
            self.note_manager = NoteManager(self, ctx.config)
            self.presenter = DocumentPresenter(self, ctx)

    # Delegate navigation
    def goto_page(self, p: int) -> None:
        """Navigate to page (delegated)."""
        self.navigator.goto_page(p)

    def next_page(self, count: int = 1) -> None:
        """Navigate forward (delegated)."""
        self.navigator.next_page(count)

    # Delegate notes
    def open_notes_editor(self) -> Optional[str]:
        """Open notes editor (delegated)."""
        if self.note_manager:
            return self.note_manager.open_notes_editor()
        return "Note manager not initialized"

    # Delegate presentation
    def show_toc(self, bar) -> None:
        """Show TOC (delegated)."""
        if self.presenter:
            self.presenter.show_toc(bar)
```

#### Acceptance Criteria

- ✅ Document class <500 lines
- ✅ Clear separation: navigation, notes, presentation
- ✅ Easier to test individual components
- ✅ All existing functionality preserved

---

## Phase 3: Testing Infrastructure (Week 4-5)

**Priority**: P1
**Estimated Effort**: 5-7 days
**Dependencies**: Phase 2 complete

### Task 3.1: Set Up Pytest Infrastructure

#### Implementation Steps

1. **Create pytest configuration** (`pyproject.toml`):

```toml
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--strict-markers",
    "--cov=src/pdfcat",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-report=xml",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]

[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/__pycache__/*",
    "*/site-packages/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]
```

2. **Create test fixtures** (`tests/conftest.py`):

```python
"""Pytest fixtures for pdfcat tests."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Make test PDFs available
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_pdf():
    """Provide path to sample PDF for testing."""
    pdf_path = FIXTURES_DIR / "sample.pdf"
    if not pdf_path.exists():
        # Create a minimal PDF for testing
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        FIXTURES_DIR.mkdir(exist_ok=True)
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        c.drawString(100, 750, "Test PDF")
        c.drawString(100, 730, "Page 1")
        c.showPage()
        c.drawString(100, 750, "Page 2")
        c.showPage()
        c.save()

    return str(pdf_path)


@pytest.fixture
def multi_page_pdf():
    """Provide path to multi-page PDF for testing."""
    pdf_path = FIXTURES_DIR / "multi_page.pdf"
    if not pdf_path.exists():
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        FIXTURES_DIR.mkdir(exist_ok=True)
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        for i in range(10):
            c.drawString(100, 750, f"Page {i + 1}")
            c.showPage()
        c.save()

    return str(pdf_path)


@pytest.fixture
def temp_dir():
    """Provide temporary directory that's cleaned up after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config():
    """Provide mock configuration."""
    config = Mock()
    config.BIBTEX = ""
    config.KITTYCMD = "kitty"
    config.TINT_COLOR = "#999999"
    config.URL_BROWSER = "open"
    config.GUI_VIEWER = "system"
    config.AUTOPLAY_FPS = 8
    config.AUTOPLAY_LOOP = True
    config.AUTOPLAY_END_PAGE = None
    config.SHOW_STATUS_BAR = True
    config.NOTES_DIR = "/tmp/pdfcat-test-notes"
    return config


@pytest.fixture
def mock_screen():
    """Provide mock screen interface."""
    screen = Mock()
    screen.rows = 40
    screen.cols = 80
    screen.width = 800
    screen.height = 600
    screen.cell_width = 10
    screen.cell_height = 15
    return screen


@pytest.fixture
def mock_renderer():
    """Provide mock renderer."""
    renderer = Mock()
    renderer.name = "mock"
    renderer.requires_clear_before_render = False
    renderer.render_pixmap = Mock(return_value=True)
    renderer.clear_image = Mock()
    renderer.cleanup = Mock()
    return renderer


@pytest.fixture
def viewer_context(mock_config, mock_screen, mock_renderer):
    """Provide complete viewer context for testing."""
    from pdfcat.context import ViewerContext
    from pdfcat.core import Buffers
    import threading

    ctx = ViewerContext(
        config=mock_config,
        buffers=Buffers(),
        screen=mock_screen,
        renderer=mock_renderer,
        shutdown_event=threading.Event(),
    )
    return ctx
```

3. **Update requirements-dev.txt**:

```txt
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.1
pytest-timeout>=2.1.0
reportlab>=4.0.0  # For creating test PDFs
black>=23.7.0
isort>=5.12.0
mypy>=1.5.0
ruff>=0.0.287
```

#### Acceptance Criteria

- ✅ Pytest runs successfully
- ✅ Test fixtures create sample PDFs
- ✅ Mock objects available for testing
- ✅ Coverage reporting configured

---

### Task 3.2: Write Unit Tests for Core Components

#### Implementation Steps

1. **Test DocumentNavigator** (`tests/test_navigator.py`):

```python
"""Test document navigation."""

import pytest
from pdfcat.navigator import DocumentNavigator
from pdfcat.document import Document


def test_goto_page(sample_pdf):
    """Test basic page navigation."""
    doc = Document(sample_pdf)
    nav = DocumentNavigator(doc)

    assert doc.page == 0

    nav.goto_page(1)
    assert doc.page == 1
    assert doc.prevpage == 0


def test_goto_page_clamping(sample_pdf):
    """Test that page navigation clamps to valid range."""
    doc = Document(sample_pdf)
    nav = DocumentNavigator(doc)

    # Try to go beyond last page
    nav.goto_page(999)
    assert doc.page == doc.pages

    # Try to go before first page
    nav.goto_page(-10)
    assert doc.page == 0


def test_next_prev_page(sample_pdf):
    """Test next/previous page navigation."""
    doc = Document(sample_pdf)
    nav = DocumentNavigator(doc)

    nav.next_page(1)
    assert doc.page == 1

    nav.prev_page(1)
    assert doc.page == 0


def test_next_page_multiple(multi_page_pdf):
    """Test navigating multiple pages at once."""
    doc = Document(multi_page_pdf)
    nav = DocumentNavigator(doc)

    nav.next_page(5)
    assert doc.page == 5

    nav.prev_page(2)
    assert doc.page == 3
```

2. **Test NoteManager** (`tests/test_notes.py`):

```python
"""Test note management."""

import pytest
from pathlib import Path
from pdfcat.notes import NoteManager
from pdfcat.document import Document


def test_resolve_note_path_creates_file(sample_pdf, mock_config, temp_dir):
    """Test that note path resolution creates the note file."""
    mock_config.NOTES_DIR = str(temp_dir)

    doc = Document(sample_pdf)
    note_mgr = NoteManager(doc, mock_config)

    note_path, err = note_mgr.resolve_note_path()

    assert err is None
    assert note_path is not None
    assert Path(note_path).exists()

    # Check that header was written
    content = Path(note_path).read_text()
    assert content.startswith("# ")


def test_resolve_note_path_security(sample_pdf, mock_config, temp_dir):
    """Test that note paths are validated for security."""
    mock_config.NOTES_DIR = str(temp_dir)

    # Mock a malicious title
    doc = Document(sample_pdf)
    doc.metadata = {"title": "../../etc/passwd"}

    note_mgr = NoteManager(doc, mock_config)
    note_path, err = note_mgr.resolve_note_path()

    # Should still succeed but sanitize the path
    assert err is None
    assert note_path is not None

    # Verify path is inside notes_dir
    assert Path(note_path).parent == Path(temp_dir)
    assert ".." not in note_path


def test_append_note(sample_pdf, mock_config, temp_dir):
    """Test appending notes."""
    mock_config.NOTES_DIR = str(temp_dir)

    doc = Document(sample_pdf)
    note_mgr = NoteManager(doc, mock_config)

    # Append a note
    err = note_mgr.append_note("Test note content")
    assert err is None

    # Verify it was written
    note_path, _ = note_mgr.resolve_note_path()
    content = Path(note_path).read_text()
    assert "Test note content" in content
```

3. **Test PageRenderCache** (`tests/test_cache.py`):

```python
"""Test page render cache."""

import pytest
from pdfcat.cache import PageRenderCache


def test_cache_basic_operations():
    """Test basic cache put/get."""
    cache = PageRenderCache(max_entries=5, max_bytes=10 * 1024 * 1024)

    # Put an entry
    cache.put(0, "pixmap_0", "matrix_0")

    # Get it back
    entry = cache.get(0)
    assert entry is not None
    assert entry.pixmap == "pixmap_0"
    assert entry.matrix == "matrix_0"


def test_cache_lru_eviction():
    """Test LRU eviction."""
    cache = PageRenderCache(max_entries=3, max_bytes=10 * 1024 * 1024)

    # Fill cache
    for i in range(3):
        cache.put(i, f"pixmap_{i}", f"matrix_{i}")

    # Add 4th entry, should evict oldest
    cache.put(3, "pixmap_3", "matrix_3")

    assert cache.get(0) is None  # Evicted
    assert cache.get(1) is not None
    assert cache.get(2) is not None
    assert cache.get(3) is not None


def test_cache_get_updates_lru():
    """Test that accessing an entry updates LRU."""
    cache = PageRenderCache(max_entries=2, max_bytes=10 * 1024 * 1024)

    cache.put(0, "pixmap_0", "matrix_0")
    cache.put(1, "pixmap_1", "matrix_1")

    # Access page 0
    cache.get(0)

    # Add page 2, should evict page 1 (not 0)
    cache.put(2, "pixmap_2", "matrix_2")

    assert cache.get(0) is not None
    assert cache.get(1) is None
    assert cache.get(2) is not None


def test_cache_invalidate():
    """Test cache invalidation."""
    cache = PageRenderCache(max_entries=5, max_bytes=10 * 1024 * 1024)

    cache.put(0, "pixmap_0", "matrix_0")
    assert cache.get(0) is not None

    cache.invalidate(0)
    assert cache.get(0) is None
```

4. **Test InputHandler** (`tests/test_input_handler.py`):

```python
"""Test input handling."""

import pytest
from pdfcat.input_handler import InputHandler
from pdfcat.actions import (
    NavigateAction,
    QuitAction,
    ToggleAction,
    NoAction,
)
from pdfcat.document import Document


def test_handle_quit_key(sample_pdf):
    """Test that quit key produces QuitAction."""
    doc = Document(sample_pdf)
    handler = InputHandler()

    action = handler.handle_key(ord('q'), doc)
    assert isinstance(action, QuitAction)


def test_handle_navigation_keys(sample_pdf):
    """Test navigation key handling."""
    doc = Document(sample_pdf)
    handler = InputHandler()

    # Next page
    action = handler.handle_key(ord('j'), doc)
    assert isinstance(action, NavigateAction)
    assert action.page == 1
    assert action.relative is True

    # Previous page
    handler.reset_state()
    action = handler.handle_key(ord('k'), doc)
    assert isinstance(action, NavigateAction)
    assert action.page == -1
    assert action.relative is True


def test_handle_count_prefix(sample_pdf):
    """Test count prefix for commands."""
    doc = Document(sample_pdf)
    handler = InputHandler()

    # Type "5j" (go forward 5 pages)
    action = handler.handle_key(ord('5'), doc)
    assert isinstance(action, NoAction)  # Just storing count

    action = handler.handle_key(ord('j'), doc)
    assert isinstance(action, NavigateAction)
    assert action.page == 5


def test_handle_toggle_keys(sample_pdf):
    """Test toggle key handling."""
    doc = Document(sample_pdf)
    handler = InputHandler()

    action = handler.handle_key(ord('d'), doc)
    assert isinstance(action, ToggleAction)
    assert action.setting == "tint"
```

#### Acceptance Criteria

- ✅ >60% code coverage
- ✅ All core components tested
- ✅ Tests run in <10 seconds
- ✅ All tests pass

---

### Task 3.3: Add Integration Tests

#### Implementation Steps

1. **Create integration test suite** (`tests/integration/test_viewer.py`):

```python
"""Integration tests for viewer."""

import pytest
import threading
import time
from unittest.mock import Mock, patch
from pdfcat.app import view
from pdfcat.document import Document


@pytest.mark.integration
def test_viewer_startup_shutdown(sample_pdf, viewer_context):
    """Test that viewer starts and shuts down cleanly."""
    doc = Document(sample_pdf, ctx=viewer_context)
    viewer_context.buffers.docs.append(doc)

    file_change = threading.Event()

    # Mock keyboard input to quit immediately
    with patch('pdfcat.app.state.scr.kb_input.getch') as mock_getch:
        mock_getch.return_value = ord('q')

        with pytest.raises(SystemExit):
            view(viewer_context, file_change, doc)


@pytest.mark.integration
def test_viewer_navigation(multi_page_pdf, viewer_context):
    """Test navigation through document."""
    doc = Document(multi_page_pdf, ctx=viewer_context)

    # Simulate navigation
    doc.navigator.next_page(5)
    assert doc.page == 5

    doc.navigator.prev_page(2)
    assert doc.page == 3

    doc.navigator.goto_page(0)
    assert doc.page == 0


@pytest.mark.integration
def test_viewer_caching(multi_page_pdf, viewer_context):
    """Test that page caching works during navigation."""
    doc = Document(multi_page_pdf, ctx=viewer_context)

    # Navigate to page 5
    doc.navigator.goto_page(5)

    # Page should be in cache
    cached = doc._render_cache.get(5)
    assert cached is not None

    # Navigate away and back
    doc.navigator.goto_page(0)
    doc.navigator.goto_page(5)

    # Should still be in cache (cache hit)
    cached = doc._render_cache.get(5)
    assert cached is not None
```

2. **Create end-to-end tests** (`tests/integration/test_e2e.py`):

```python
"""End-to-end tests."""

import pytest
import subprocess
import time


@pytest.mark.integration
@pytest.mark.slow
def test_cli_help():
    """Test that CLI help works."""
    result = subprocess.run(
        ["python", "-m", "pdfcat", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout


@pytest.mark.integration
@pytest.mark.slow
def test_cli_version():
    """Test that CLI version works."""
    result = subprocess.run(
        ["python", "-m", "pdfcat", "--version"],
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert "0.1.1" in result.stdout


@pytest.mark.integration
@pytest.mark.slow
def test_open_pdf_and_quit(sample_pdf):
    """Test opening a PDF and quitting."""
    # This requires a PTY for interactive terminal
    # Skipping for now - would need pexpect or similar
    pytest.skip("Requires PTY for interactive testing")
```

#### Acceptance Criteria

- ✅ Integration tests cover main workflows
- ✅ E2E tests verify CLI works
- ✅ Tests can run in CI environment

---

## Phase 4: Documentation & Packaging (Week 5-6)

**Priority**: P2
**Estimated Effort**: 5-7 days
**Dependencies**: Phase 3 complete

### Task 4.1: Modernize Packaging

**Files**: `setup.py`, `pyproject.toml`

#### Implementation Steps

1. **Create complete `pyproject.toml`**:

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pdfcat"
version = "0.1.1"
description = "Keyboard-first PDF reader for terminal workflows"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Marcos Romero Lamas", email = "your-email@example.com"},
]
maintainers = [
    {name = "Marcos Romero Lamas", email = "your-email@example.com"},
]
keywords = ["pdf", "viewer", "terminal", "tui", "kitty"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS :: MacOS X",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Office/Business",
    "Topic :: Utilities",
]

dependencies = [
    "PyMuPDF>=1.23.0,<2.0.0",
    "Pillow>=10.0.0,<11.0.0",
    "pdfrw>=0.4,<1.0",
    "pyperclip>=1.8.0,<2.0.0",
    "pybtex>=0.24.0,<1.0.0",
    "pynvim>=0.5.0,<1.0.0",
    "roman>=4.0,<5.0",
    "pagelabels>=1.2.0,<2.0.0",
    "rich>=13.0.0,<14.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.11.1",
    "pytest-timeout>=2.1.0",
    "reportlab>=4.0.0",
    "black>=23.7.0",
    "isort>=5.12.0",
    "mypy>=1.5.0",
    "ruff>=0.0.287",
]

[project.urls]
Homepage = "https://github.com/marromlam/pdfcat"
Documentation = "https://github.com/marromlam/pdfcat#readme"
Repository = "https://github.com/marromlam/pdfcat"
"Bug Tracker" = "https://github.com/marromlam/pdfcat/issues"

[project.scripts]
pdfcat = "pdfcat.app:run"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.black]
line-length = 100
target-version = ["py311"]
exclude = '''
/(
    \.git
  | \.mypy_cache
  | __pycache__
)/
'''

[tool.isort]
profile = "black"
line_length = 100
src_paths = ["src", "tests"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
disallow_incomplete_defs = false
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_equality = true

[[tool.mypy.overrides]]
module = [
    "fitz",
    "pdfrw",
    "pagelabels",
    "pybtex",
    "roman",
]
ignore_missing_imports = true

[tool.ruff]
line-length = 100
target-version = "py311"
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
]
ignore = [
    "E501",  # line too long (handled by black)
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]
"tests/*" = ["S101"]  # Allow assert in tests
```

2. **Remove `setup.py`** or convert to minimal shim:

```python
"""Minimal setup.py shim for backwards compatibility."""
from setuptools import setup

setup()
```

3. **Create `MANIFEST.in`**:

```
include README.md
include LICENSE
include pyproject.toml
recursive-include src *.py
recursive-include tests *.py
recursive-exclude * __pycache__
recursive-exclude * *.py[co]
```

4. **Create `LICENSE`** file:

```
MIT License

Copyright (c) 2024 Marcos Romero Lamas

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

#### Acceptance Criteria

- ✅ `pip install .` works
- ✅ `pip install -e .[dev]` installs dev dependencies
- ✅ Version number in single location
- ✅ All dependencies pinned with ranges

---

### Task 4.2: Add CI/CD Pipeline

**File**: `.github/workflows/ci.yml`

#### Implementation Steps

1. **Create GitHub Actions workflow**:

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    name: Test on Python ${{ matrix.python-version }}
    runs-on: ${{ matrix.os }}

    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ["3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
        cache: 'pip'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .[dev]

    - name: Lint with ruff
      run: |
        ruff check src/ tests/

    - name: Check formatting with black
      run: |
        black --check src/ tests/

    - name: Type check with mypy
      run: |
        mypy src/pdfcat/
      continue-on-error: true  # Don't fail on type errors initially

    - name: Run tests
      run: |
        pytest -v --cov=src/pdfcat --cov-report=xml --cov-report=term

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
        fail_ci_if_error: false

  security:
    name: Security Scan
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Run Bandit security scan
      run: |
        pip install bandit
        bandit -r src/ -f json -o bandit-report.json
      continue-on-error: true

    - name: Upload Bandit report
      uses: actions/upload-artifact@v3
      with:
        name: bandit-report
        path: bandit-report.json

  build:
    name: Build Distribution
    runs-on: ubuntu-latest
    needs: [test]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"

    - name: Install build dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine

    - name: Build package
      run: python -m build

    - name: Check package
      run: twine check dist/*

    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: dist
        path: dist/
```

2. **Create pre-commit hooks** (`.pre-commit-config.yaml`):

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-toml
      - id: mixed-line-ending

  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.287
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--ignore-missing-imports]
```

3. **Add Makefile for common tasks**:

```makefile
.PHONY: help install dev-install test lint format clean build

help:
	@echo "Available commands:"
	@echo "  install      - Install package"
	@echo "  dev-install  - Install with development dependencies"
	@echo "  test         - Run tests with coverage"
	@echo "  lint         - Run linters"
	@echo "  format       - Format code"
	@echo "  clean        - Clean build artifacts"
	@echo "  build        - Build distribution"

install:
	pip install .

dev-install:
	pip install -e .[dev]
	pre-commit install

test:
	pytest -v --cov=src/pdfcat --cov-report=term-missing --cov-report=html

lint:
	ruff check src/ tests/
	black --check src/ tests/
	mypy src/pdfcat/

format:
	black src/ tests/
	isort src/ tests/
	ruff check --fix src/ tests/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build
```

#### Acceptance Criteria

- ✅ CI runs on every push/PR
- ✅ Tests pass on Ubuntu and macOS
- ✅ Coverage report uploaded to Codecov
- ✅ Pre-commit hooks installed

---

### Task 4.3: Write Architecture Documentation

**File**: `docs/ARCHITECTURE.md`

#### Implementation Steps

1. **Create architecture document**:

```markdown
# pdfcat Architecture

## Overview

pdfcat is a terminal-based PDF viewer designed for keyboard-first workflows. This document describes the high-level architecture and key design decisions.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI (app.py)                         │
│                     Entry point, arg parsing                 │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   ViewerContext (context.py)                 │
│              Dependency injection container                  │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│   Config    │   Screen     │   Renderer   │   WorkerPool    │
└─────────────┴──────────────┴──────────────┴─────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Main Event Loop (app.py)                  │
│                  Input → Action → Execute                    │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│ InputHandler│ ActionExecutor│ StatusBar   │ File Watcher    │
└─────────────┴──────────────┴──────────────┴─────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Document (document.py)                    │
│              PDF abstraction with caching                    │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│ Navigator   │ NoteManager  │ Presenter    │ RenderCache     │
└─────────────┴──────────────┴──────────────┴─────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│               Rendering Layer (renderers.py)                 │
│           Graphics protocol implementations                  │
├──────────────────────────┬──────────────────────────────────┤
│   NativeRenderer         │   KittyRenderer (legacy)         │
│   (Kitty protocol)       │                                  │
└──────────────────────────┴──────────────────────────────────┘
```

## Core Components

### 1. ViewerContext

**Purpose**: Dependency injection container that holds all runtime state.

**Responsibilities**:
- Configuration management
- Screen/terminal interface
- Rendering engine
- Worker thread pool
- Shutdown coordination

**Why**: Eliminates global state, makes testing easier, enables clean shutdown.

### 2. Document

**Purpose**: Abstraction over PyMuPDF with caching and navigation.

**Responsibilities**:
- PDF loading and page access
- Page state management
- Render caching (via PageRenderCache)

**Delegates to**:
- `DocumentNavigator`: Page navigation logic
- `NoteManager`: Note-taking integration
- `DocumentPresenter`: UI presentation (TOC, metadata, links)

### 3. Input Handling

**Flow**: Keyboard → InputHandler → Action → ActionExecutor

**Components**:
- `InputHandler`: Maps keystrokes to Action objects
- `Action` types: Immutable action descriptors
- `ActionExecutor`: Executes actions on document

**Why**: Separation of concerns, testable without terminal, replayable actions.

### 4. Rendering

**Abstraction**: `RenderingEngine` interface with implementations:
- `NativeRenderer`: Direct Kitty graphics protocol
- `KittyRenderer`: Legacy implementation

**Features**:
- Pixmap caching (PageRenderCache)
- LRU eviction with memory limits
- Visual transformations (tint, invert, alpha)
- Pre-rendering adjacent pages

### 5. Background Tasks

**Worker Pool**: `WorkerPool` with bounded thread pool

**Tasks**:
- Pre-rendering adjacent pages
- Live text extraction for search
- File change watching

**Synchronization**: RLock-based protection for Page_State

## Data Flow

### Page Rendering

```
User presses 'j'
    ↓
InputHandler creates NavigateAction(page=+1)
    ↓
ActionExecutor calls doc.navigator.next_page()
    ↓
Navigator updates doc.page
    ↓
Main loop calls doc.display_page()
    ↓
Check PageRenderCache for cached pixmap
    ↓
If cache miss: render with PyMuPDF, store in cache
    ↓
Apply visual transformations (tint/invert)
    ↓
renderer.render_pixmap() sends to terminal
    ↓
Submit pre-render task to WorkerPool
```

### Note Taking

```
User presses 'n'
    ↓
ActionExecutor calls doc.note_manager.open_notes_editor()
    ↓
NoteManager resolves note path (with security validation)
    ↓
Launch nvim in tmux popup or standalone
    ↓
User edits note
    ↓
Return to pdfcat, re-initialize terminal
```

## Security Considerations

### Command Injection

**Mitigations**:
- All subprocess calls use `shell=False`
- External commands validated with `sanitize_command_args()`
- File paths validated with `sanitize_file_path()`

### Path Traversal

**Mitigations**:
- Note paths validated to stay within NOTES_DIR
- Slugification removes `..` and path separators
- Absolute path comparison for containment check

### Memory Safety

**Mitigations**:
- Bounded render cache (default 500MB)
- LRU eviction prevents unbounded growth
- Thread-safe cache operations

## Performance Optimizations

### 1. Render Caching

- Cache base pixmaps (before visual transformations)
- Separate cache for encoded PNG bytes
- Visual transformation cache key

### 2. Pre-rendering

- Background threads pre-render adjacent pages
- Prioritizes forward navigation
- Avoids duplicate pre-renders with locks

### 3. Debounced Navigation

- 50ms debounce window for rapid key presses
- Reduces unnecessary renders during fast scrolling

### 4. Lazy Initialization

- Renderer selected at runtime
- Documents loaded on-demand

## Testing Strategy

### Unit Tests

- Individual component testing
- Mock external dependencies
- Fast (<1s per test)

### Integration Tests

- Component interaction testing
- Real PDF fixtures
- Moderate speed (~5s per test)

### End-to-End Tests

- CLI invocation
- Full workflow validation
- Slow (~30s per test)

## Future Considerations

### Planned Improvements

1. **Plugin System**: Allow custom renderers, key bindings
2. **Annotation Support**: Highlight, comments via PDF annotations
3. **Multi-column Layout**: Side-by-side pages
4. **Incremental Loading**: Stream large PDFs

### Performance Targets

- Startup: <500ms
- Page navigation: <50ms
- Memory: <500MB for 200-page PDF
- Cache hit rate: >80% during normal navigation

## Contributing

See `CONTRIBUTING.md` for development setup and guidelines.
```

2. **Create CONTRIBUTING.md**:

```markdown
# Contributing to pdfcat

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/marromlam/pdfcat.git
cd pdfcat
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
```

3. Install in development mode:
```bash
make dev-install
```

4. Run tests:
```bash
make test
```

## Code Standards

### Style Guide

- Follow PEP 8
- Use Black for formatting (100 char line length)
- Use isort for import sorting
- Type hints required for public functions

### Testing

- Write tests for new features
- Maintain >60% coverage
- Run `make test` before submitting PR

### Documentation

- Add docstrings to public functions
- Update README for user-facing changes
- Update ARCHITECTURE.md for design changes

## Pull Request Process

1. Create feature branch from `main`
2. Make changes with clear commit messages
3. Add tests for new functionality
4. Run `make lint` and fix any issues
5. Submit PR with description of changes

## Commit Messages

Follow conventional commits:

```
feat: add link hints overlay
fix: prevent memory leak in cache
docs: update architecture diagram
test: add integration tests for navigation
refactor: split Document class
```

## Code Review

All PRs require:
- ✅ Tests passing
- ✅ Coverage maintained
- ✅ No linting errors
- ✅ At least one approval
```

#### Acceptance Criteria

- ✅ ARCHITECTURE.md documents system design
- ✅ CONTRIBUTING.md guides new developers
- ✅ Diagrams illustrate key concepts
- ✅ Examples provided for common tasks

---

## Appendix: Code Examples

### Example: Migrating from Global State to Context

**Before**:
```python
def display_page(self, bar, p, display=True):
    dw = state.scr.width
    if state.renderer:
        state.renderer.render_pixmap(pix, p, place, state.scr)
```

**After**:
```python
def display_page(self, ctx: ViewerContext, bar, p, display=True):
    dw = ctx.screen.width
    if ctx.renderer:
        ctx.renderer.render_pixmap(pix, p, place, ctx.screen)
```

### Example: Using Action Pattern

**Before** (direct manipulation):
```python
if key == ord('j'):
    doc.next_page(1)
elif key == ord('k'):
    doc.prev_page(1)
```

**After** (action pattern):
```python
action = input_handler.handle_key(key, doc)
executor.execute(action, doc, bar)
```

### Example: Thread-Safe Page State

**Before** (race condition):
```python
page_state.cached_pixmap = pix  # Multiple threads!
```

**After** (synchronized):
```python
page_state.set_cached_pixmap(pix, matrix)  # Internally locks
```

---

## Success Metrics Summary

Track these metrics to measure refactoring progress:

| Metric | Current | Target | Phase |
|--------|---------|--------|-------|
| Security vulnerabilities | 5 | 0 | P0 |
| Longest function (LOC) | 1,058 | <200 | P1 |
| Test coverage | ~10% | >60% | P1 |
| Memory usage (200pg PDF) | ~4.5GB | <500MB | P1 |
| Thread safety issues | 3 | 0 | P1 |
| Global state usage | 150+ refs | 0 | P1 |
| CI/CD pipeline | None | Full | P2 |
| Architecture docs | None | Complete | P2 |

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | P0: Security | All command injection & path traversal fixed |
| 1-2 | P1: Threading | Page state locks, bounded cache, worker pool |
| 2-4 | P2: Architecture | View loop refactored, state removed, Document split |
| 4-5 | P3: Testing | pytest suite, >60% coverage, integration tests |
| 5-6 | P4: Docs/CI | pyproject.toml, CI/CD, architecture docs |

---

## Questions & Support

For questions about this plan:
1. Open an issue on GitHub
2. Tag with `refactoring` label
3. Reference specific task number (e.g., "Task 2.1")

Good luck! 🚀
