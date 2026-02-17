#!/usr/bin/env python3
"""Input handler action mapping tests."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdfcat.actions import (
    BufferCycleAction,
    NavigateRelativeAction,
    NoAction,
    QuitAction,
    ToggleTintAction,
)
from pdfcat.input_handler import InputHandler


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def pass_(msg: str) -> None:
    print(f"PASS: {msg}")


class DummyDoc:
    page = 5
    pages = 20

    @staticmethod
    def physical_to_logical_page(_p=None):
        return "21"


def test_quit_key_maps_to_quit_action() -> None:
    ih = InputHandler()
    action = ih.handle_key(ord("q"), DummyDoc())
    if not isinstance(action, QuitAction):
        fail(f"expected QuitAction, got {type(action).__name__}")
    pass_("quit maps to QuitAction")


def test_count_then_next_maps_to_navigate_relative() -> None:
    ih = InputHandler()
    a1 = ih.handle_key(ord("3"), DummyDoc())
    if not isinstance(a1, NoAction):
        fail("digit should only update internal count state")
    action = ih.handle_key(ord("j"), DummyDoc())
    if not isinstance(action, NavigateRelativeAction):
        fail(f"expected NavigateRelativeAction, got {type(action).__name__}")
    if action.delta != 3:
        fail(f"expected delta 3, got {action.delta}")
    pass_("count prefix applied to next-page action")


def test_toggle_tint_maps_correctly() -> None:
    ih = InputHandler()
    action = ih.handle_key(ord("d"), DummyDoc())
    if not isinstance(action, ToggleTintAction):
        fail(f"expected ToggleTintAction, got {type(action).__name__}")
    pass_("tint key maps to ToggleTintAction")


def test_buffer_cycle_combo_maps_correctly() -> None:
    ih = InputHandler()
    _ = ih.handle_key(ord("2"), DummyDoc())
    action = ih.handle_key(ord("b"), DummyDoc())
    if not isinstance(action, BufferCycleAction):
        fail(f"expected BufferCycleAction, got {type(action).__name__}")
    if action.offset != 2:
        fail(f"expected buffer cycle offset 2 for 2b, got {action.offset}")
    pass_("2b maps to forward buffer cycle")


def test_buffer_cycle_reverse_maps_correctly() -> None:
    ih = InputHandler()
    _ = ih.handle_key(ord("3"), DummyDoc())
    action = ih.handle_key(ord("B"), DummyDoc())
    if not isinstance(action, BufferCycleAction):
        fail(f"expected BufferCycleAction, got {type(action).__name__}")
    if action.offset != -3:
        fail(f"expected buffer cycle offset -3 for 3B, got {action.offset}")
    pass_("3B maps to reverse buffer cycle")


def main() -> int:
    test_quit_key_maps_to_quit_action()
    test_count_then_next_maps_to_navigate_relative()
    test_toggle_tint_maps_correctly()
    test_buffer_cycle_combo_maps_correctly()
    test_buffer_cycle_reverse_maps_correctly()
    print("SUCCESS: input handler tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
