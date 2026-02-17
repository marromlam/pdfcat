"""Keyboard input mapping for the viewer loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .actions import (
    Action,
    AppendNoteAction,
    BufferCloseAction,
    BufferCycleAction,
    BufferSwitchAction,
    ChangeLayoutAction,
    DebugAction,
    GoBackAction,
    GotoStartAction,
    InsertNoteAction,
    NavigateChapterAction,
    NavigateLogicalAction,
    NavigatePhysicalAction,
    NavigateRelativeAction,
    NoAction,
    OpenGuiAction,
    QuitAction,
    RefreshAction,
    ReverseSynctexAction,
    RotateAction,
    SearchAction,
    SetAutoplayEndAction,
    SetPageLabelAction,
    ShowHelpAction,
    ShowLinkHintsAction,
    ShowLinksAction,
    ShowMetaAction,
    ShowTocAction,
    ToggleAlphaAction,
    ToggleAutocropAction,
    ToggleAutoplayAction,
    ToggleInvertAction,
    TogglePresenterAction,
    ToggleTextModeAction,
    ToggleTintAction,
    VisualModeAction,
)
from .ui import shortcuts


@dataclass
class InputHandler:
    """Translate raw keys into high-level actions."""

    keys: shortcuts = field(default_factory=shortcuts)
    count_string: str = ""
    stack: list[int] = field(default_factory=lambda: [0])

    def reset_state(self) -> None:
        self.count_string = ""
        self.stack = [0]

    def get_count(self) -> int:
        if self.count_string == "":
            return 1
        return int(self.count_string)

    def get_command_string(self) -> str:
        return "".join(map(chr, self.stack[::-1]))

    def _push_printable(self, key: int) -> None:
        self.stack = [key] + self.stack

    def _is_digit(self, key: int) -> bool:
        return 48 <= key <= 57

    def handle_key(self, key: int, doc: Any) -> Action:
        count = self.get_count()

        if key == 27:
            self.reset_state()
            return NoAction()

        if self.stack[0] in self.keys.BUFFER_CYCLE and self._is_digit(key):
            self.reset_state()
            return BufferSwitchAction(index=int(chr(key)) - 1)

        if self.stack[0] in self.keys.BUFFER_CYCLE and key == ord("d"):
            self.reset_state()
            return BufferCloseAction()

        if self.stack[0] in self.keys.BUFFER_CYCLE and key in self.keys.BUFFER_CYCLE:
            self.reset_state()
            return BufferCycleAction(offset=count)

        if key in self.keys.BUFFER_CYCLE_REV:
            self.reset_state()
            return BufferCycleAction(offset=-count)

        if self._is_digit(key):
            self._push_printable(key)
            self.count_string += chr(key)
            return NoAction()

        if key in self.keys.QUIT:
            self.reset_state()
            return QuitAction()

        if key in self.keys.REFRESH:
            self.reset_state()
            return RefreshAction()

        if key in self.keys.REVERSE_SYNCTEX:
            self.reset_state()
            return ReverseSynctexAction()

        if key in self.keys.TOGGLE_AUTOPLAY:
            action = ToggleAutoplayAction(count_string=self.count_string, count=count)
            self.reset_state()
            return action

        if key in self.keys.SET_AUTOPLAY_END:
            action = SetAutoplayEndAction(count_string=self.count_string, count=count)
            self.reset_state()
            return action

        if key in self.keys.GOTO_PAGE:
            if self.count_string == "":
                logical = doc.physical_to_logical_page(doc.pages)
            else:
                logical = count
            self.reset_state()
            return NavigateLogicalAction(logical_page=logical)

        if key in self.keys.GOTO_PAGE_PHYSICAL:
            if self.count_string == "":
                physical = doc.page
            else:
                physical = max(0, count - 1)
            self.reset_state()
            return NavigatePhysicalAction(page=physical)

        if key in self.keys.NEXT_PAGE:
            self.reset_state()
            return NavigateRelativeAction(delta=count)

        if key in self.keys.PREV_PAGE:
            self.reset_state()
            return NavigateRelativeAction(delta=-count)

        if key in self.keys.GO_BACK:
            self.reset_state()
            return GoBackAction()

        if key in self.keys.NEXT_CHAP:
            self.reset_state()
            return NavigateChapterAction(delta=count)

        if key in self.keys.PREV_CHAP:
            self.reset_state()
            return NavigateChapterAction(delta=-count)

        if self.stack[0] in self.keys.GOTO and key in self.keys.GOTO:
            self.reset_state()
            return GotoStartAction()

        if key in self.keys.ROTATE_CW:
            self.reset_state()
            return RotateAction(degrees=90 * count)

        if key in self.keys.ROTATE_CCW:
            self.reset_state()
            return RotateAction(degrees=-90 * count)

        if key in self.keys.TOGGLE_AUTOCROP:
            self.reset_state()
            return ToggleAutocropAction()

        if key in self.keys.TOGGLE_ALPHA:
            self.reset_state()
            return ToggleAlphaAction()

        if key in self.keys.TOGGLE_INVERT:
            self.reset_state()
            return ToggleInvertAction()

        if key in self.keys.TOGGLE_TINT:
            self.reset_state()
            return ToggleTintAction()

        if key in self.keys.SHOW_TOC:
            self.reset_state()
            return ShowTocAction()

        if key in self.keys.SHOW_META:
            self.reset_state()
            return ShowMetaAction()

        if key in self.keys.SHOW_LINK_HINTS:
            self.reset_state()
            return ShowLinkHintsAction()

        if key in self.keys.SHOW_LINKS:
            self.reset_state()
            return ShowLinksAction()

        if key in self.keys.TOGGLE_TEXT_MODE:
            self.reset_state()
            return ToggleTextModeAction()

        if key in self.keys.INC_FONT:
            self.reset_state()
            return ChangeLayoutAction(delta=-count)

        if key in self.keys.DEC_FONT:
            self.reset_state()
            return ChangeLayoutAction(delta=count)

        if key in self.keys.VISUAL_MODE:
            self.reset_state()
            return VisualModeAction()

        if key in self.keys.INSERT_NOTE:
            self.reset_state()
            return InsertNoteAction()

        if key in self.keys.APPEND_NOTE:
            self.reset_state()
            return AppendNoteAction()

        if key in self.keys.TOGGLE_PRESENTER and self.count_string == "":
            self.reset_state()
            return TogglePresenterAction()

        if key in self.keys.SET_PAGE_LABEL and self.count_string != "":
            self.reset_state()
            return SetPageLabelAction(count=count, style="arabic")

        if key in self.keys.SET_PAGE_ALT:
            self.reset_state()
            return SetPageLabelAction(count=count, style="roman lowercase")

        if key == ord("/"):
            return SearchAction()

        if key in self.keys.SHOW_HELP:
            self.reset_state()
            return ShowHelpAction()

        if key in self.keys.OPEN_GUI:
            return OpenGuiAction()

        if key in self.keys.DEBUG:
            return DebugAction()

        if 48 <= key <= 256:
            self._push_printable(key)

        return NoAction()
