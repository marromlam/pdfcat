"""Pytest fixtures for pdfcat tests."""

from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import Mock

import fitz
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.context import ViewerContext
from pdfcat.core import Buffers

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _create_pdf(path: Path, pages: int) -> None:
    """Create a small PDF fixture with deterministic text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"pdfcat fixture page {i + 1}")
    doc.save(path)
    doc.close()


@pytest.fixture
def sample_pdf() -> str:
    """Path to a minimal sample PDF."""
    pdf_path = FIXTURES_DIR / "sample.pdf"
    if not pdf_path.exists():
        _create_pdf(pdf_path, pages=2)
    return str(pdf_path)


@pytest.fixture
def multi_page_pdf() -> str:
    """Path to a 10-page sample PDF."""
    pdf_path = FIXTURES_DIR / "multi_page.pdf"
    if not pdf_path.exists():
        _create_pdf(pdf_path, pages=10)
    return str(pdf_path)


@pytest.fixture
def temp_dir() -> Path:
    """Temporary directory for filesystem tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config() -> Mock:
    """Application config stub for unit tests."""
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
    config._loaded_keys = set()
    return config


@pytest.fixture
def mock_screen() -> Mock:
    """Screen stub with basic terminal metrics."""
    screen = Mock()
    screen.rows = 40
    screen.cols = 80
    screen.width = 800
    screen.height = 600
    screen.cell_width = 10
    screen.cell_height = 15
    screen.kb_input = Mock()
    return screen


@pytest.fixture
def mock_renderer() -> Mock:
    """Renderer stub for display-path tests."""
    renderer = Mock()
    renderer.name = "mock"
    renderer.requires_clear_before_render = False
    renderer.render_pixmap = Mock(return_value=True)
    renderer.clear_image = Mock()
    renderer.cleanup = Mock()
    return renderer


@pytest.fixture
def viewer_context(
    mock_config: Mock, mock_screen: Mock, mock_renderer: Mock
) -> ViewerContext:
    """Fully wired context instance for context-aware unit tests."""
    return ViewerContext(
        config=mock_config,
        buffers=Buffers(),
        screen=mock_screen,
        renderer=mock_renderer,
        shutdown_event=threading.Event(),
    )
