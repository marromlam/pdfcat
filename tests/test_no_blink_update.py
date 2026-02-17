#!/usr/bin/env python3
"""No-blink rendering contract tests."""

import sys
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.renderers import NativeRenderer


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


class FakePixmap:
    width = 100
    height = 80
    alpha = False

    def tobytes(self, fmt: str):
        if fmt != "png":
            fail(f"unexpected format request: {fmt}")
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
    upload_called = False

    def mock_upload(*args, **kwargs):
        nonlocal upload_called
        upload_called = True

    renderer_any._upload_png = mock_upload
    renderer_any._write_gr_cmd = lambda cmd, payload=None: commands.append(dict(cmd))
    renderer_any._maybe_clear_tmux_history = lambda force=False: None
    renderer_any._append_cols_debug_line = lambda payload: None

    ps = FakePageState()
    ok = renderer.render_pixmap(FakePixmap(), 0, (2, 2, 30, 20), FakeScreen(), ps)
    if not ok:
        fail("render_pixmap returned False")

    # NativeRenderer uses direct upload (a=T) instead of separate place (a=p)
    if not upload_called:
        fail("_upload_png was not called")

    # Check that old global image was deleted
    delete_cmds = [c for c in commands if c.get("a") == "d" and c.get("d") == "i"]
    if not delete_cmds:
        fail("missing old-image delete-by-id command")
    if delete_cmds[0].get("i") != 123:
        fail(f"expected delete of image 123, got {delete_cmds[0].get('i')}")

    # Check page state was updated
    if ps.last_image_id == 123:
        fail("page state image id was not updated")
    if ps.last_place != (2, 2, 30, 20):
        fail("page state placement was not updated")

    pass_("atomic image replacement deletes old global image to prevent flicker")


def test_display_page_no_unconditional_clear() -> None:
    text = (REPO_ROOT / "src" / "pdfcat" / "document.py").read_text(encoding="utf-8")
    marker = 'if getattr(state.renderer, "requires_clear_before_render", False):'
    if marker not in text:
        fail("display_page missing renderer capability gate before clear")
    pass_("display_page uses capability-gated clear instead of unconditional clear")


def main() -> int:
    test_timg_atomic_replace()
    test_display_page_no_unconditional_clear()
    print("SUCCESS: no-blink contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
