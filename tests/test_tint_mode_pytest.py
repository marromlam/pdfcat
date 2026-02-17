"""Pytest unit tests for tint mode color mapping."""

from __future__ import annotations

import os

import fitz
import pytest

from pdfcat.document import _terminal_theme_rgb, _tint_pixmap_duotone


@pytest.mark.unit
def test_terminal_theme_rgb_from_colorfgbg() -> None:
    old = os.environ.get("COLORFGBG")
    os.environ["COLORFGBG"] = "15;0"
    fg, bg = _terminal_theme_rgb()
    assert fg == (255, 255, 255)
    assert bg == (0, 0, 0)
    if old is None:
        del os.environ["COLORFGBG"]
    else:
        os.environ["COLORFGBG"] = old


@pytest.mark.unit
def test_duotone_tint_maps_black_to_fg_and_white_to_bg() -> None:
    src = fitz.Pixmap(fitz.csRGB, 2, 1, bytes([0, 0, 0, 255, 255, 255]), False)
    fg = (240, 240, 240)
    bg = (24, 24, 24)
    out = _tint_pixmap_duotone(src, fg, bg)
    samples = out.samples
    assert tuple(samples[0:3]) == fg
    assert tuple(samples[3:6]) == bg
