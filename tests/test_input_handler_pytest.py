"""Pytest unit tests for input handler mappings."""

from __future__ import annotations

import pytest

from pdfcat.actions import (
    BufferCycleAction,
    NavigateRelativeAction,
    NoAction,
    QuitAction,
    ToggleTintAction,
)
from pdfcat.input_handler import InputHandler


class DummyDoc:
    page = 5
    pages = 20

    @staticmethod
    def physical_to_logical_page(_p=None):
        return "21"


@pytest.mark.unit
def test_quit_key_maps_to_quit_action() -> None:
    ih = InputHandler()
    action = ih.handle_key(ord("q"), DummyDoc())
    assert isinstance(action, QuitAction)


@pytest.mark.unit
def test_count_then_next_maps_to_navigate_relative() -> None:
    ih = InputHandler()
    first = ih.handle_key(ord("3"), DummyDoc())
    assert isinstance(first, NoAction)
    action = ih.handle_key(ord("j"), DummyDoc())
    assert isinstance(action, NavigateRelativeAction)
    assert action.delta == 3


@pytest.mark.unit
def test_toggle_tint_maps_correctly() -> None:
    ih = InputHandler()
    action = ih.handle_key(ord("d"), DummyDoc())
    assert isinstance(action, ToggleTintAction)


@pytest.mark.unit
def test_buffer_cycle_combo_maps_correctly() -> None:
    ih = InputHandler()
    _ = ih.handle_key(ord("2"), DummyDoc())
    action = ih.handle_key(ord("b"), DummyDoc())
    assert isinstance(action, BufferCycleAction)
    assert action.offset == 2


@pytest.mark.unit
def test_buffer_cycle_reverse_maps_correctly() -> None:
    ih = InputHandler()
    _ = ih.handle_key(ord("3"), DummyDoc())
    action = ih.handle_key(ord("B"), DummyDoc())
    assert isinstance(action, BufferCycleAction)
    assert action.offset == -3
