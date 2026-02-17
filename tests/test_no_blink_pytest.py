"""Pytest unit tests for no-blink rendering contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from pdfcat.renderers import NativeRenderer

REPO_ROOT = Path(__file__).resolve().parents[1]


class FakePixmap:
    width = 100
    height = 80
    alpha = False

    def tobytes(self, fmt: str):
        if fmt != "png":
            raise AssertionError(f"unexpected format request: {fmt}")
        return b"png-bytes"


class FakeScreen:
    cols = 120
    rows = 40

    def set_cursor(self, c, r):
        _ = (c, r)


class FakePageState:
    def __init__(self):
        self.cached_ppm = b"png-bytes"
        self.last_image_id = 123
        self.last_place = (1, 1, 20, 10)


@pytest.mark.unit
def test_timg_atomic_replace() -> None:
    """Test that NativeRenderer deletes old images to prevent flicker."""
    renderer = object.__new__(NativeRenderer)
    renderer_any = cast(Any, renderer)
    renderer.in_tmux = False
    renderer.protocol = "kitty"
    renderer._id_counter = 1000
    renderer._last_displayed_image_id = 123  # Simulate existing global image
    renderer._last_tmux_history_clear = 0.0
    renderer._tmux_history_clear_interval = 1.0

    commands: list[dict] = []
    upload_called = [False]

    def mock_upload(*args, **kwargs):
        upload_called[0] = True

    renderer_any._upload_png = mock_upload
    renderer_any._write_gr_cmd = lambda cmd, payload=None: commands.append(dict(cmd))
    renderer_any._maybe_clear_tmux_history = lambda force=False: None
    renderer_any._append_cols_debug_line = lambda payload: None

    ps = FakePageState()
    ok = renderer.render_pixmap(FakePixmap(), 0, (2, 2, 30, 20), FakeScreen(), ps)
    assert ok

    # NativeRenderer uses direct upload (a=T) instead of separate place (a=p)
    assert upload_called[0], "_upload_png was not called"

    # Check that old global image was deleted
    delete_cmds = [c for c in commands if c.get("a") == "d" and c.get("d") == "i"]
    assert delete_cmds, "missing old-image delete-by-id command"
    deleted_id = delete_cmds[0].get("i")
    assert deleted_id == 123, f"expected delete of image 123, got {deleted_id}"

    # Check page state was updated
    assert ps.last_image_id != 123, "page state image id was not updated"
    assert ps.last_place == (2, 2, 30, 20)


@pytest.mark.unit
def test_display_page_has_clear_capability_gate() -> None:
    text = (REPO_ROOT / "src" / "pdfcat" / "document.py").read_text(encoding="utf-8")
    marker = 'if getattr(state.renderer, "requires_clear_before_render", False):'
    assert marker in text
