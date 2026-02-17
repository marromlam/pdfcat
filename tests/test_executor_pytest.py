"""Pytest unit tests for action executor visual toggle behavior."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pdfcat.actions import ToggleAlphaAction, ToggleInvertAction, ToggleTintAction
from pdfcat.executor import ActionExecutor


@dataclass
class _DummyDoc:
    alpha: bool = False
    invert: bool = False
    tint: bool = False
    force_tinted: bool = False
    force_original: bool = False
    mark_calls: list[bool] = field(default_factory=list)

    def mark_all_pages_stale(self, reset_cache: bool = True) -> None:
        self.mark_calls.append(reset_cache)


@dataclass
class _DummyBar:
    message: str = ""


@dataclass
class _DummyBuffers:
    docs: list[object] = field(default_factory=list)
    current: int = 0

    def cycle(self, _offset: int) -> None:
        return None


def _build_executor() -> ActionExecutor:
    return ActionExecutor(
        clean_exit_fn=lambda: None,
        refresh_doc_fn=lambda doc: doc,
        reverse_synctex_fn=lambda _doc, _bar: None,
        toggle_presenter_fn=lambda _doc: None,
        show_help_fn=lambda _doc, _bar: None,
        open_external_viewer_fn=lambda _doc: None,
        search_mode_fn=lambda _doc, _bar: None,
        run_visual_mode_fn=lambda _doc, _bar: None,
        buffers=_DummyBuffers(),
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("action", "attr", "initial"),
    [
        (ToggleAlphaAction(), "alpha", True),
        (ToggleInvertAction(), "invert", True),
        (ToggleTintAction(), "tint", True),
    ],
)
def test_visual_toggles_are_blocked_in_force_tinted_mode(
    action: object, attr: str, initial: bool
) -> None:
    executor = _build_executor()
    doc = _DummyDoc(alpha=True, invert=True, tint=True, force_tinted=True)
    bar = _DummyBar()

    out = executor.execute(action, doc, bar)

    assert out is doc
    assert getattr(doc, attr) is initial
    assert doc.mark_calls == []
    assert bar.message == "visual mode locked (tinted)"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("action", "attr"),
    [
        (ToggleAlphaAction(), "alpha"),
        (ToggleInvertAction(), "invert"),
        (ToggleTintAction(), "tint"),
    ],
)
def test_visual_toggles_are_blocked_in_force_original_mode(
    action: object, attr: str
) -> None:
    executor = _build_executor()
    doc = _DummyDoc(alpha=False, invert=False, tint=False, force_original=True)
    bar = _DummyBar()

    out = executor.execute(action, doc, bar)

    assert out is doc
    assert getattr(doc, attr) is False
    assert doc.mark_calls == []
    assert bar.message == "visual mode locked (original)"


@pytest.mark.unit
def test_visual_toggle_still_works_without_forced_mode() -> None:
    executor = _build_executor()
    doc = _DummyDoc(alpha=False, invert=False, tint=False)
    bar = _DummyBar()

    executor.execute(ToggleAlphaAction(), doc, bar)
    executor.execute(ToggleInvertAction(), doc, bar)
    executor.execute(ToggleTintAction(), doc, bar)

    assert doc.alpha is True
    assert doc.invert is True
    assert doc.tint is True
    assert doc.mark_calls == [True, False, False]
