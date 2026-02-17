#!/usr/bin/env python3
"""Script tests for native renderer protocol selection."""

from __future__ import annotations

import os
import sys
from pathlib import Path

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


def _clear_renderer_env() -> None:
    for key in ["TMUX", "TERM", "TERM_PROGRAM", "KITTY_WINDOW_ID", "KITTY_PID"]:
        os.environ.pop(key, None)


def test_no_tmux_uses_direct_kitty_protocol() -> None:
    _clear_renderer_env()
    os.environ["TERM"] = "xterm-kitty"
    renderer = NativeRenderer()
    if renderer.in_tmux:
        fail("renderer should not detect tmux when TMUX is unset")
    if renderer.protocol != "kitty":
        fail(f"expected direct kitty protocol, got {renderer.protocol!r}")
    pass_("no TMUX -> direct kitty protocol")


def test_tmux_with_kitty_env_uses_tmux_protocol() -> None:
    _clear_renderer_env()
    os.environ["TMUX"] = "/tmp/tmux-1000/default,123,0"
    os.environ["KITTY_WINDOW_ID"] = "9"
    renderer = NativeRenderer()
    if not renderer.in_tmux:
        fail("renderer should detect tmux when TMUX is set")
    if renderer.protocol != "kitty-tmux":
        fail(f"expected kitty-tmux protocol, got {renderer.protocol!r}")
    pass_("TMUX + kitty env -> kitty-tmux protocol")


def test_term_program_kitty_without_tmux() -> None:
    _clear_renderer_env()
    os.environ["TERM"] = "xterm-256color"
    os.environ["TERM_PROGRAM"] = "kitty"
    renderer = NativeRenderer()
    if renderer.protocol != "kitty":
        fail(
            f"expected kitty protocol for TERM_PROGRAM=kitty, got {renderer.protocol!r}"
        )
    pass_("TERM_PROGRAM=kitty -> direct kitty protocol")


def main() -> int:
    old_env = dict(os.environ)
    try:
        test_no_tmux_uses_direct_kitty_protocol()
        test_tmux_with_kitty_env_uses_tmux_protocol()
        test_term_program_kitty_without_tmux()
        print("SUCCESS: renderer protocol detection tests passed")
        return 0
    finally:
        os.environ.clear()
        os.environ.update(old_env)


if __name__ == "__main__":
    raise SystemExit(main())
