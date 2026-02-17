#!/usr/bin/env python3
"""Compatibility checks between native renderer and upstream timg behavior.

Run:
  python3 tests/test_timg_compatibility.py
"""

import re
import sys
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.renderers import NativeRenderer


def fail(msg: str) -> NoReturn:
    print(f"  FAIL: {msg}")
    raise AssertionError(msg)


def pass_(msg: str) -> None:
    print(f"  PASS: {msg}")


def extract_timg_diacritics(source_text: str) -> list[int]:
    match = re.search(
        r"static const char \*const kRowColEncode\[\] = \{(.*?)\}; /\* 297 \*/",
        source_text,
        re.S,
    )
    if not match:
        fail("could not locate kRowColEncode[] in timg source")
    values = re.findall(r'"\\u([0-9A-Fa-f]+)"', match.group(1))
    if len(values) != 297:
        fail(f"expected 297 diacritics in timg source, found {len(values)}")
    return [int(v, 16) for v in values]


def make_renderer(in_tmux: bool, protocol: str):
    # Bypass __init__ so tests are deterministic and don't require a real TTY/tmux.
    renderer = object.__new__(NativeRenderer)
    renderer.in_tmux = in_tmux
    renderer.protocol = protocol
    return renderer


def main() -> int:
    print("=" * 60)
    print("Native Renderer vs timg Compatibility")
    print("=" * 60)

    timg_src = Path.home() / "tmp" / "repos" / "timg" / "src" / "kitty-canvas.cc"
    if not timg_src.exists():
        print(f"SKIP: timg source not found at {timg_src}")
        return 0

    source_text = timg_src.read_text(encoding="utf-8")
    failures = 0

    # 1) Placeholder codepoint compatibility.
    try:
        expected_placeholder = bytes([0xF4, 0x8E, 0xBB, 0xAE]).decode("utf-8")
        if NativeRenderer._PLACEHOLDER != expected_placeholder:
            fail(
                "placeholder mismatch: expected U+10EEEE from timg "
                f"got U+{ord(NativeRenderer._PLACEHOLDER):X}"
            )
        pass_("placeholder codepoint matches timg (U+10EEEE)")
    except AssertionError:
        failures += 1

    # 2) Full diacritic table compatibility.
    try:
        expected = extract_timg_diacritics(source_text)
        actual = NativeRenderer._ROWCOL_DIACRITICS
        if expected != actual:
            fail(
                "row/col diacritic table mismatch against timg "
                f"(expected {len(expected)} values, got {len(actual)})"
            )
        pass_("row/col diacritic table matches timg source")
    except AssertionError:
        failures += 1

    # 3) tmux passthrough wrapping compatibility.
    try:
        renderer = make_renderer(in_tmux=True, protocol="kitty-tmux")
        wrapped = renderer._serialize_gr_command({"a": "d", "d": "a"})
        if not wrapped.startswith(NativeRenderer._TMUX_START):
            fail("tmux-wrapped sequence missing tmux DCS start")
        if not wrapped.endswith(NativeRenderer._TMUX_END):
            fail("tmux-wrapped sequence missing tmux DCS end")
        inner = wrapped[
            len(NativeRenderer._TMUX_START) : -len(NativeRenderer._TMUX_END)
        ]
        unescaped = inner.replace(b"\x1b\x1b", b"\x1b")
        expected_inner = b"\x1b_Ga=d,d=a\x1b\\"
        if unescaped != expected_inner:
            fail("tmux ESC escaping does not round-trip to expected kitty command")
        pass_("tmux passthrough command wrapping matches expected kitty framing")
    except AssertionError:
        failures += 1

    # 4) Placeholder tile encoding contract.
    try:
        renderer = make_renderer(in_tmux=True, protocol="kitty-tmux")
        tile = renderer._tmux_placeholder_tile(1, 2, 3)
        cps = [ord(c) for c in tile]
        if cps[0] != ord(NativeRenderer._PLACEHOLDER):
            fail("tile does not start with placeholder codepoint")
        if cps[1] != NativeRenderer._ROWCOL_DIACRITICS[1]:
            fail("row diacritic mismatch in tile encoding")
        if cps[2] != NativeRenderer._ROWCOL_DIACRITICS[2]:
            fail("col diacritic mismatch in tile encoding")
        if cps[3] != NativeRenderer._ROWCOL_DIACRITICS[3]:
            fail("msb diacritic mismatch in tile encoding")
        pass_("tmux placeholder tile encoding uses expected diacritics")
    except AssertionError:
        failures += 1

    # 5) Ensure we do not shell out to timg anymore.
    try:
        text = (REPO_ROOT / "src" / "pdfcat" / "renderers.py").read_text(
            encoding="utf-8"
        )
        if re.search(r"subprocess\.run\(\[\s*['\"]timg['\"]", text):
            fail("found external timg subprocess call in renderer module")
        pass_("no external timg subprocess calls detected")
    except AssertionError:
        failures += 1

    print("=" * 60)
    if failures:
        print(f"FAILED: {failures} checks failed")
        print("=" * 60)
        return 1
    print("SUCCESS: all compatibility checks passed")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
