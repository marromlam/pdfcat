"""TOC/metadata modal views for document presentation."""

from __future__ import annotations

import sys
from typing import Any

from .ui import shortcuts


class PresenterViews:
    """Render non-link modal views (ToC, metadata)."""

    def __init__(self, presenter: Any) -> None:
        self.presenter = presenter

    @property
    def doc(self) -> Any:
        return self.presenter.doc

    def _screen(self) -> Any:
        return self.presenter._screen()

    def _clean_exit(self) -> None:
        self.presenter._clean_exit()

    def show_toc(self, bar: Any) -> None:
        screen = self._screen()
        if screen is None:
            bar.message = "screen unavailable"
            return

        toc = self.doc.get_toc()
        if not toc:
            bar.message = "No ToC available"
            return

        self.doc.page_states[self.doc.page].stale = True
        self.doc.clear_page(self.doc.page)
        screen.clear()

        toc_rows = []
        for row in toc:
            try:
                level = int(row[0]) if len(row) > 0 else 1
                title = str(row[1]).strip() if len(row) > 1 else ""
                page = int(row[2]) if len(row) > 2 else 1
                if not title:
                    title = "(untitled)"
                toc_rows.append((max(1, level), title, max(1, page)))
            except Exception:
                continue

        if not toc_rows:
            bar.message = "No ToC entries available"
            return

        keys = shortcuts()
        index = self.doc.current_chapter()
        if index < 0:
            index = 0
        if index >= len(toc_rows):
            index = len(toc_rows) - 1
        scroll = 0

        def _render_toc() -> tuple[int, int]:
            screen.clear()
            width = max(1, screen.cols)
            header = " Table of Contents - j/k: move, Enter/right: jump, t/esc: close "
            header = header[:width]
            screen.set_cursor(1, 1)
            sys.stdout.write("\033[1;37;44m" + header.ljust(width) + "\033[0m")

            list_top = 2
            list_bottom = max(2, screen.rows - 1)
            visible_rows = max(1, list_bottom - list_top + 1)
            max_scroll = max(0, len(toc_rows) - visible_rows)
            current_scroll = min(max(0, scroll), max_scroll)

            for i in range(visible_rows):
                row_idx = current_scroll + i
                if row_idx >= len(toc_rows):
                    break
                level, title, page = toc_rows[row_idx]
                indent = "  " * (level - 1)
                line = f"{indent}{title}  [{page}]"
                if len(line) > width:
                    line = line[: max(1, width - 1)]
                row = list_top + i
                screen.set_cursor(1, row)
                if row_idx == index:
                    sys.stdout.write("\033[7m" + line.ljust(width) + "\033[0m")
                else:
                    sys.stdout.write(line.ljust(width))

            footer = f" Section {index + 1}/{len(toc_rows)} "
            footer = footer[:width]
            screen.set_cursor(1, screen.rows)
            sys.stdout.write("\033[1;30;47m" + footer.ljust(width) + "\033[0m")
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()
            return current_scroll, visible_rows

        while True:
            scroll, visible_rows = _render_toc()
            key = screen.kb_input.getch()

            if key in keys.REFRESH:
                screen.get_size()
                continue
            if key in keys.QUIT:
                self._clean_exit()
            if key == 27 or key in keys.SHOW_TOC:
                screen.clear()
                return
            if key in keys.NEXT_PAGE:
                index = min(len(toc_rows) - 1, index + 1)
            elif key in keys.PREV_PAGE:
                index = max(0, index - 1)
            elif key in keys.OPEN:
                screen.clear()
                self.doc.chapter = index
                self.doc.goto_page(toc_rows[index][2] - 1)
                return

            if index < scroll:
                scroll = index
            elif index >= scroll + visible_rows:
                scroll = index - visible_rows + 1

    def show_meta(self, bar: Any) -> None:
        screen = self._screen()
        if screen is None:
            bar.message = "screen unavailable"
            return

        meta = self.doc.metadata
        if not meta:
            bar.message = "No metadata available"
            return

        self.doc.page_states[self.doc.page].stale = True
        self.doc.clear_page(self.doc.page)
        screen.clear()

        def init_pad(metadata: dict[str, Any]) -> tuple[Any, Any, int, int, int, int, list[int]]:
            win, pad = screen.create_text_window(len(meta), "Metadata")
            y, x = win.getbegyx()
            h, w = win.getmaxyx()
            span: list[int] = []
            for i, mkey in enumerate(meta):
                text = f"{mkey}: {meta[mkey]}"
                pad.addstr(i, 0, text)
                span.append(len(text))
            return win, pad, y, x, h, w, span

        _, pad, y, x, h, w, span = init_pad(meta)

        keys = shortcuts()
        index = 0
        j = 0

        while True:
            for i, _ in enumerate(meta):
                attr = 1 if index == i else 0
                pad.chgat(i, 0, span[i], attr)
            pad.refresh(j, 0, y + 3, x + 2, y + h - 2, x + w - 3)
            key = screen.kb_input.getch()

            if key in keys.REFRESH:
                screen.clear()
                screen.get_size()
                screen.init_terminal()
                self.doc.set_layout(self.doc.papersize)
                self.doc.mark_all_pages_stale()
                _, pad, y, x, h, w, span = init_pad(meta)
            elif key in keys.QUIT:
                self._clean_exit()
            elif key == 27 or key in keys.SHOW_META:
                screen.clear()
                return
            elif key in keys.NEXT_PAGE:
                index = min(len(meta) - 1, index + 1)
            elif key in keys.PREV_PAGE:
                index = max(0, index - 1)
            elif key in keys.UPDATE_FROM_BIB:
                self.doc.update_metadata_from_bibtex()
                meta = self.doc.metadata
                _, pad, y, x, h, w, span = init_pad(meta)
            elif key in keys.OPEN:
                pass

            if index > j + (h - 5):
                j += 1
            if index < j:
                j -= 1
