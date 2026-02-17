"""Action execution for the viewer loop."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from .actions import (
    Action,
    AppendNoteAction,
    BufferCycleAction,
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
    SetPageLabelAction,
    ShowHelpAction,
    ShowLinkHintsAction,
    ShowLinksAction,
    ShowMetaAction,
    ShowTocAction,
    ToggleAlphaAction,
    ToggleAutocropAction,
    ToggleInvertAction,
    TogglePresenterAction,
    ToggleTextModeAction,
    ToggleTintAction,
    VisualModeAction,
)


@dataclass
class ActionExecutor:
    """Execute actions on the active document."""

    clean_exit_fn: Callable[[], None]
    refresh_doc_fn: Callable[[Any], Any]
    reverse_synctex_fn: Callable[[Any, Any], None]
    toggle_presenter_fn: Callable[[Any], str | None]
    show_help_fn: Callable[[Any, Any], None]
    open_external_viewer_fn: Callable[[Any], str | None]
    search_mode_fn: Callable[[Any, Any], None]
    run_visual_mode_fn: Callable[[Any, Any], None]
    buffers: Any

    @staticmethod
    def _forced_visual_mode(doc: Any) -> str | None:
        """Return the active forced visual mode, if any."""
        if bool(getattr(doc, "force_original", False)):
            return "original"
        if bool(getattr(doc, "force_tinted", False)):
            return "tinted"
        return None

    @staticmethod
    def _visual_toggle_blocked(doc: Any, bar: Any) -> bool:
        """Block visual toggles when forced visual mode is active."""
        mode = ActionExecutor._forced_visual_mode(doc)
        if mode is None:
            return False
        bar.message = f"visual mode locked ({mode})"
        return True

    def _activate_doc(self, doc: Any, bar: Any) -> Any:
        doc.goto_logical_page(doc.logicalpage)
        doc.set_layout(doc.papersize, adjustpage=False)
        doc.mark_all_pages_stale()
        total_buffers = len(self.buffers.docs)
        current_buffer = self.buffers.current + 1
        label = doc.citekey or os.path.basename(doc.filename)
        if total_buffers > 0:
            bar.message = f"[{current_buffer}/{total_buffers}] {label}"
        else:
            bar.message = str(label)
        return doc

    def execute(self, action: Action, doc: Any, bar: Any) -> Any:
        if isinstance(action, NoAction):
            return doc

        if isinstance(action, QuitAction):
            self.clean_exit_fn()
            return doc

        if isinstance(action, RefreshAction):
            return self.refresh_doc_fn(doc)

        if isinstance(action, BufferCycleAction):
            self.buffers.cycle(action.offset)
            doc = self.buffers.docs[self.buffers.current]
            return self._activate_doc(doc, bar)

        if isinstance(action, ReverseSynctexAction):
            self.reverse_synctex_fn(doc, bar)
            return doc

        if isinstance(action, NavigateLogicalAction):
            doc.goto_logical_page(action.logical_page)
            return doc

        if isinstance(action, NavigatePhysicalAction):
            doc.goto_page(max(0, int(action.page)))
            return doc

        if isinstance(action, NavigateRelativeAction):
            if action.delta >= 0:
                doc.next_page(action.delta)
            else:
                doc.prev_page(abs(action.delta))
            return doc

        if isinstance(action, GoBackAction):
            doc.goto_page(doc.prevpage)
            return doc

        if isinstance(action, NavigateChapterAction):
            if action.delta >= 0:
                doc.next_chapter(action.delta)
            else:
                doc.previous_chapter(abs(action.delta))
            return doc

        if isinstance(action, GotoStartAction):
            doc.goto_page(0)
            return doc

        if isinstance(action, RotateAction):
            doc.rotation = (doc.rotation + action.degrees) % 360
            doc.mark_all_pages_stale()
            return doc

        if isinstance(action, ToggleAutocropAction):
            if doc.manualcroprect != [None, None]:
                if doc.autocrop:
                    doc.autocrop = False
                    doc.manualcrop = True
                elif doc.manualcrop:
                    doc.autocrop = False
                    doc.manualcrop = False
                else:
                    doc.autocrop = True
            else:
                doc.autocrop = not doc.autocrop
            doc.mark_all_pages_stale()
            return doc

        if isinstance(action, ToggleAlphaAction):
            if self._visual_toggle_blocked(doc, bar):
                return doc
            doc.alpha = not doc.alpha
            doc.mark_all_pages_stale()
            return doc

        if isinstance(action, ToggleInvertAction):
            if self._visual_toggle_blocked(doc, bar):
                return doc
            doc.invert = not doc.invert
            doc.mark_all_pages_stale(reset_cache=False)
            return doc

        if isinstance(action, ToggleTintAction):
            if self._visual_toggle_blocked(doc, bar):
                return doc
            doc.tint = not doc.tint
            doc.mark_all_pages_stale(reset_cache=False)
            return doc

        if isinstance(action, ShowTocAction):
            doc.show_toc(bar)
            return doc

        if isinstance(action, ShowMetaAction):
            doc.show_meta(bar)
            return doc

        if isinstance(action, ShowLinkHintsAction):
            doc.show_link_hints(bar)
            return doc

        if isinstance(action, ShowLinksAction):
            doc.show_links_list(bar)
            return doc

        if isinstance(action, ToggleTextModeAction):
            message = doc.view_text()
            if message:
                bar.message = message
            return doc

        if isinstance(action, ChangeLayoutAction):
            doc.set_layout(doc.papersize + action.delta)
            doc.mark_all_pages_stale()
            return doc

        if isinstance(action, VisualModeAction):
            self.run_visual_mode_fn(doc, bar)
            return doc

        if isinstance(action, InsertNoteAction):
            msg = doc.open_notes_editor()
            bar.message = msg if msg else "opened notes"
            return doc

        if isinstance(action, AppendNoteAction):
            copy_msg = doc.copy_page_link_reference()
            open_msg = doc.open_notes_editor()
            if copy_msg and open_msg:
                bar.message = copy_msg + "; " + open_msg
            elif copy_msg:
                bar.message = copy_msg
            elif open_msg:
                bar.message = open_msg
            else:
                bar.message = "copied link and opened notes"
            return doc

        if isinstance(action, TogglePresenterAction):
            msg = self.toggle_presenter_fn(doc)
            if msg:
                bar.message = msg
            return doc

        if isinstance(action, SetPageLabelAction):
            if doc.is_pdf:
                style = "arabic" if action.style == "arabic" else "roman lowercase"
                doc.set_page_label(action.count, style)
            else:
                doc.first_page_offset = action.count - doc.page
            doc.build_logical_pages()
            return doc

        if isinstance(action, SearchAction):
            self.search_mode_fn(doc, bar)
            return doc

        if isinstance(action, ShowHelpAction):
            self.show_help_fn(doc, bar)
            return doc

        if isinstance(action, OpenGuiAction):
            msg = self.open_external_viewer_fn(doc)
            if msg:
                bar.message = msg
            else:
                bar.message = "opened external viewer"
            return doc

        if isinstance(action, DebugAction):
            return doc

        return doc
