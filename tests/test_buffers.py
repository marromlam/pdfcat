#!/usr/bin/env python3
"""Script tests for core buffer navigation behavior."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.core import Buffers


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


def test_cycle_wraps_forward_and_backward() -> None:
    bufs = Buffers()
    bufs.docs = ["a", "b", "c"]
    bufs.current = 0
    bufs.cycle(1)
    if bufs.current != 1:
        fail(f"expected current=1 after +1, got {bufs.current}")
    bufs.cycle(5)
    if bufs.current != 0:
        fail(f"expected current=0 after +5 wrap, got {bufs.current}")
    bufs.cycle(-1)
    if bufs.current != 2:
        fail(f"expected current=2 after -1 wrap, got {bufs.current}")
    pass_("buffer cycle wraps in both directions")


def main() -> int:
    test_cycle_wraps_forward_and_backward()
    print("SUCCESS: buffer tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
