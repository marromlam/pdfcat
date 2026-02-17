"""Action types for the viewer event loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Action:
    """Base action type."""


@dataclass(frozen=True)
class NoAction(Action):
    """No action should be executed."""


@dataclass(frozen=True)
class QuitAction(Action):
    """Exit the application."""


@dataclass(frozen=True)
class RefreshAction(Action):
    """Reload current document and refresh terminal."""


@dataclass(frozen=True)
class BufferSwitchAction(Action):
    """Switch to a specific buffer index."""

    index: int


@dataclass(frozen=True)
class BufferCloseAction(Action):
    """Close the current buffer."""


@dataclass(frozen=True)
class BufferCycleAction(Action):
    """Cycle buffer list by offset."""

    offset: int


@dataclass(frozen=True)
class ReverseSynctexAction(Action):
    """Run reverse synctex for current page."""


@dataclass(frozen=True)
class NavigateLogicalAction(Action):
    """Navigate by logical page number."""

    logical_page: Any


@dataclass(frozen=True)
class NavigatePhysicalAction(Action):
    """Navigate by physical page number (0-based)."""

    page: int


@dataclass(frozen=True)
class NavigateRelativeAction(Action):
    """Navigate by relative page offset."""

    delta: int


@dataclass(frozen=True)
class GoBackAction(Action):
    """Jump back to previous page."""


@dataclass(frozen=True)
class NavigateChapterAction(Action):
    """Navigate chapter by relative delta."""

    delta: int


@dataclass(frozen=True)
class GotoStartAction(Action):
    """Jump to first page."""


@dataclass(frozen=True)
class RotateAction(Action):
    """Rotate pages by degrees."""

    degrees: int


@dataclass(frozen=True)
class ToggleAutocropAction(Action):
    """Toggle/cycle crop modes."""


@dataclass(frozen=True)
class ToggleAlphaAction(Action):
    """Toggle alpha rendering."""


@dataclass(frozen=True)
class ToggleInvertAction(Action):
    """Toggle invert mode."""


@dataclass(frozen=True)
class ToggleTintAction(Action):
    """Toggle tint mode."""


@dataclass(frozen=True)
class ShowTocAction(Action):
    """Show TOC modal."""


@dataclass(frozen=True)
class ShowMetaAction(Action):
    """Show metadata modal."""


@dataclass(frozen=True)
class ShowLinkHintsAction(Action):
    """Show link hint overlay."""


@dataclass(frozen=True)
class ShowLinksAction(Action):
    """Show links list modal."""


@dataclass(frozen=True)
class ToggleTextModeAction(Action):
    """Enter text mode for the current page."""


@dataclass(frozen=True)
class ChangeLayoutAction(Action):
    """Change document layout index by delta."""

    delta: int


@dataclass(frozen=True)
class VisualModeAction(Action):
    """Enter visual mode."""


@dataclass(frozen=True)
class InsertNoteAction(Action):
    """Open notes editor."""


@dataclass(frozen=True)
class AppendNoteAction(Action):
    """Copy page link and open notes editor."""


@dataclass(frozen=True)
class TogglePresenterAction(Action):
    """Toggle presenter mode."""


@dataclass(frozen=True)
class SetPageLabelAction(Action):
    """Set logical page labels."""

    count: int
    style: str


@dataclass(frozen=True)
class SearchAction(Action):
    """Enter search mode."""


@dataclass(frozen=True)
class ShowHelpAction(Action):
    """Show keybind/help modal."""


@dataclass(frozen=True)
class OpenGuiAction(Action):
    """Open external GUI viewer."""


@dataclass(frozen=True)
class ToggleAutoplayAction(Action):
    """Toggle autoplay mode."""

    count_string: str
    count: int


@dataclass(frozen=True)
class SetAutoplayEndAction(Action):
    """Set autoplay end page."""

    count_string: str
    count: int


@dataclass(frozen=True)
class DebugAction(Action):
    """Debug no-op action."""
