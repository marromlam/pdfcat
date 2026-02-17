#!/usr/bin/env python3
"""Tests for tint mode and terminal color mapping."""

import os
import sys
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.document import _terminal_theme_rgb, _tint_pixmap_duotone


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


def test_terminal_theme_rgb_from_colorfgbg() -> None:
    old = os.environ.get("COLORFGBG")
    os.environ["COLORFGBG"] = "15;0"
    fg, bg = _terminal_theme_rgb()
    if fg != (255, 255, 255):
        fail(f"expected fg white from COLORFGBG=15;0, got {fg}")
    if bg != (0, 0, 0):
        fail(f"expected bg black from COLORFGBG=15;0, got {bg}")
    pass_("terminal fg/bg color mapping from COLORFGBG works")
    if old is None:
        del os.environ["COLORFGBG"]
    else:
        os.environ["COLORFGBG"] = old


def test_duotone_tint_maps_black_to_fg_and_white_to_bg() -> None:
    # Two RGB pixels: black, white
    src = fitz.Pixmap(fitz.csRGB, 2, 1, bytes([0, 0, 0, 255, 255, 255]), False)
    fg = (240, 240, 240)
    bg = (24, 24, 24)
    out = _tint_pixmap_duotone(src, fg, bg)
    samples = out.samples
    black_mapped = tuple(samples[0:3])
    white_mapped = tuple(samples[3:6])

    if black_mapped != fg:
        fail(f"expected black pixel to map to fg {fg}, got {black_mapped}")
    if white_mapped != bg:
        fail(f"expected white pixel to map to bg {bg}, got {white_mapped}")
    pass_("duotone tint maps luminance endpoints correctly")


def main() -> int:
    test_terminal_theme_rgb_from_colorfgbg()
    test_duotone_tint_maps_black_to_fg_and_white_to_bg()
    print("SUCCESS: tint mode tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
