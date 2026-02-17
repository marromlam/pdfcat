"""Tint/invert helpers for pixmap rendering."""

from __future__ import annotations

import os
import re
from typing import Any

import fitz

Image: Any = None
ImageOps: Any = None
try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover - optional dependency
    pass

_ANSI_16_RGB = [
    (0, 0, 0),
    (205, 49, 49),
    (13, 188, 121),
    (229, 229, 16),
    (36, 114, 200),
    (188, 63, 188),
    (17, 168, 205),
    (229, 229, 229),
    (102, 102, 102),
    (241, 76, 76),
    (35, 209, 139),
    (245, 245, 67),
    (59, 142, 234),
    (214, 112, 214),
    (41, 184, 219),
    (255, 255, 255),
]


def xterm_color_to_rgb(idx: int) -> tuple[int, int, int]:
    """Convert xterm-256 color index to RGB."""
    if idx < 0:
        idx = 0
    if idx <= 15:
        return _ANSI_16_RGB[idx]
    if idx <= 231:
        i = idx - 16
        levels = [0, 95, 135, 175, 215, 255]
        r = levels[i // 36]
        g = levels[(i % 36) // 6]
        b = levels[i % 6]
        return (r, g, b)
    if idx <= 255:
        v = 8 + (idx - 232) * 10
        return (v, v, v)
    return (255, 255, 255)


def terminal_theme_rgb() -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Best-effort foreground/background RGB from terminal environment."""
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        parts = [p for p in re.split(r"[:;]", colorfgbg) if re.fullmatch(r"\d+", p)]
        if len(parts) >= 2:
            fg_idx = int(parts[0])
            bg_idx = int(parts[-1])
            return xterm_color_to_rgb(fg_idx), xterm_color_to_rgb(bg_idx)

    # Fallback: dark terminal defaults.
    return (220, 220, 220), (28, 28, 28)


def tint_pixmap_duotone_fallback(
    pix: fitz.Pixmap,
    fg_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int],
) -> fitz.Pixmap:
    """Pure Python fallback when Pillow is unavailable."""
    if pix.n < 3:
        return pix

    samples = bytearray(pix.samples)
    step = pix.n
    fg_r, fg_g, fg_b = (int(fg_rgb[0]), int(fg_rgb[1]), int(fg_rgb[2]))
    bg_r, bg_g, bg_b = (int(bg_rgb[0]), int(bg_rgb[1]), int(bg_rgb[2]))

    for i in range(0, len(samples), step):
        r = samples[i]
        g = samples[i + 1]
        b = samples[i + 2]
        lum = (299 * r + 587 * g + 114 * b) // 1000
        inv = 255 - lum
        samples[i] = (fg_r * inv + bg_r * lum) // 255
        samples[i + 1] = (fg_g * inv + bg_g * lum) // 255
        samples[i + 2] = (fg_b * inv + bg_b * lum) // 255

    return fitz.Pixmap(pix.colorspace, pix.width, pix.height, bytes(samples), pix.alpha)


def tint_pixmap_duotone(
    pix: fitz.Pixmap,
    fg_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int],
) -> fitz.Pixmap:
    """Map black->fg and white->bg with a fast Pillow path."""
    if Image is None or ImageOps is None:
        return tint_pixmap_duotone_fallback(pix, fg_rgb, bg_rgb)

    mode = "RGBA" if pix.alpha else "RGB"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)

    if mode == "RGBA":
        alpha = img.getchannel("A")
        img = img.convert("RGB")

    fg = (int(fg_rgb[0]), int(fg_rgb[1]), int(fg_rgb[2]))
    bg = (int(bg_rgb[0]), int(bg_rgb[1]), int(bg_rgb[2]))
    gray = ImageOps.grayscale(img)
    colorized = ImageOps.colorize(gray, black=fg, white=bg)

    if mode == "RGBA":
        colorized.putalpha(alpha)
        return fitz.Pixmap(fitz.csRGB, pix.width, pix.height, colorized.tobytes(), True)
    return fitz.Pixmap(fitz.csRGB, pix.width, pix.height, colorized.tobytes(), False)
