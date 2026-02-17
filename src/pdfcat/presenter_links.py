"""Link navigation and hint/list UI for document presentation."""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any

import fitz

from .ui import shortcuts


class PresenterLinks:
    """Render and act on document links."""

    def __init__(self, presenter: Any) -> None:
        self.presenter = presenter

    @property
    def doc(self) -> Any:
        return self.presenter.doc

    def _screen(self) -> Any:
        return self.presenter._screen()

    def _config(self) -> Any:
        return self.presenter._config()

    def _renderer(self) -> Any:
        return self.presenter._renderer()

    def _clean_exit(self) -> None:
        self.presenter._clean_exit()

    def goto_link(self, link: dict[str, Any]) -> str:
        config = self._config()
        browser = str(getattr(config, "URL_BROWSER", "")) if config is not None else ""
        if not browser:
            return "No URL browser configured"

        kind = int(link.get("kind", 0))
        if kind == 0:
            return "Link has no destination"
        if kind == 1:
            page = link.get("page")
            if isinstance(page, int) and page >= 0:
                self.doc.goto_page(page)
                return f"jumped to p.{page + 1}"
            return "Internal link destination unavailable"
        if kind == 2:
            uri = link.get("uri", "")
            if not uri:
                return "URI link missing target"
            subprocess.run([browser, uri], check=True)
            return "opened URI link"
        if kind == 3:
            path = link.get("file") or link.get("fileSpec")
            if path:
                subprocess.run([browser, path], check=False)
                return "opened launch link"
            return "Launch link target unavailable"
        if kind == 4:
            name = (
                link.get("name")
                or link.get("nameddest")
                or link.get("dest")
                or link.get("uri")
                or ""
            )
            page = link.get("page")
            if isinstance(page, int) and page >= 0:
                self.doc.goto_page(page)
                return f"jumped to p.{page + 1}"

            action = str(name).strip().lower()
            if action in {"nextpage", "next"}:
                self.doc.next_page(1)
                return f"jumped to p.{self.doc.page + 1}"
            if action in {"prevpage", "previouspage", "prev", "previous"}:
                self.doc.prev_page(1)
                return f"jumped to p.{self.doc.page + 1}"
            if action in {"firstpage", "first"}:
                self.doc.goto_page(0)
                return "jumped to p.1"
            if action in {"lastpage", "last"}:
                self.doc.goto_page(self.doc.pages)
                return f"jumped to p.{self.doc.pages + 1}"
            if action in {"goback"}:
                self.doc.goto_page(self.doc.prevpage)
                return f"jumped to p.{self.doc.page + 1}"
            if action in {"goforward"}:
                return "GoForward action not supported"
            if action:
                return f"Named link action not supported: {name}"
            return "Named link destination unavailable"
        if kind == 5:
            path = link.get("fileSpec", "")
            if path:
                subprocess.run([browser, path], check=False)
                return "opened external PDF link"
            page = link.get("page")
            if isinstance(page, int) and page >= 0:
                self.doc.goto_page(page)
                return f"jumped to p.{page + 1}"
            return "External PDF link target unavailable"

        page = link.get("page")
        if isinstance(page, int) and page >= 0:
            self.doc.goto_page(page)
            return f"jumped to p.{page + 1}"
        uri = link.get("uri", "")
        if uri:
            subprocess.run([browser, uri], check=True)
            return "opened URI link"
        return f"Unsupported link type ({kind})"

    def _hint_token(self, index: int, alphabet: str) -> str:
        base = len(alphabet)
        n = index + 1
        chars: list[str] = []
        while n > 0:
            n, rem = divmod(n - 1, base)
            chars.append(alphabet[rem])
        return "".join(reversed(chars))

    def _get_actionable_links(self) -> list[dict[str, Any]]:
        links = self.doc[self.doc.page].get_links()
        return [
            link
            for link in links
            if link.get("kind", 0) > 0 and link.get("from") is not None
        ]

    def _get_hintable_links(self) -> list[dict[str, Any]]:
        screen = self._screen()
        config = self._config()
        if screen is None:
            return []

        links = self._get_actionable_links()
        if not links:
            return []

        page = self.doc.load_page(self.doc.page)
        if (
            self.doc.manualcrop
            and self.doc.manualcroprect != [None, None]
            and self.doc.is_pdf
        ):
            page.set_cropbox(
                fitz.Rect(self.doc.manualcroprect[0], self.doc.manualcroprect[1])
            )
        elif self.doc.autocrop and self.doc.is_pdf:
            page.set_cropbox(page.mediabox)
            crop = self.doc.auto_crop(page)
            page.set_cropbox(crop)
        elif self.doc.is_pdf:
            page.set_cropbox(page.mediabox)

        page_state = self.doc.page_states[self.doc.page]
        factor = page_state.factor
        mat = fitz.Matrix(factor, factor).prerotate(self.doc.rotation)

        page_px_rect = page.rect * mat
        offset_x = -page_px_rect.x0
        offset_y = -page_px_rect.y0

        l_col, t_row, r_col, b_row = page_state.place
        page_cell_rect = fitz.Rect(l_col, t_row, r_col, b_row)

        status_rows = 1 if bool(getattr(config, "SHOW_STATUS_BAR", True)) else 0
        max_rows = max(1, screen.rows - status_rows)
        max_cols = max(1, screen.cols)
        max_hint_col = min(max_cols, max(1, int(page_cell_rect.x1) - 1))
        max_hint_row = min(max_rows, max(1, int(page_cell_rect.y1) - 1))

        visible: list[dict[str, Any]] = []
        for link in links:
            try:
                src = fitz.Rect(link["from"])
                if src.is_empty:
                    continue

                rect_px = src * mat
                rect_px = fitz.Rect(
                    rect_px.x0 + offset_x,
                    rect_px.y0 + offset_y,
                    rect_px.x1 + offset_x,
                    rect_px.y1 + offset_y,
                )

                x0_px, x1_px = sorted((rect_px.x0, rect_px.x1))
                y0_px, y1_px = sorted((rect_px.y0, rect_px.y1))
                x0 = int((x0_px + l_col * screen.cell_width) / screen.cell_width)
                x1 = int((x1_px + l_col * screen.cell_width) / screen.cell_width)
                y0 = int((y0_px + t_row * screen.cell_height) / screen.cell_height)
                y1 = int((y1_px + t_row * screen.cell_height) / screen.cell_height)
                if x0 == x1:
                    x1 += 1
                if y0 == y1:
                    y1 += 1
                link_cell_rect = fitz.Rect(x0, y0, x1, y1)
                if link_cell_rect.is_empty:
                    continue

                hint_col = min(max(1, int(link_cell_rect.x0)), max_hint_col)
                hint_row = min(max(1, int(link_cell_rect.y0)), max_hint_row)
                visible.append(
                    {
                        "link": link,
                        "col": hint_col,
                        "row": hint_row,
                        "confidence": 1.0,
                    }
                )
            except Exception:
                continue

        visible.sort(key=lambda entry: (entry["row"], entry["col"]))
        return visible

    def _draw_hint_badges(self, entries: list[dict[str, Any]], query: str) -> int:
        screen = self._screen()
        if screen is None:
            return 0

        shown = 0
        for entry in entries:
            hint = entry["hint"]
            if query and not hint.startswith(query):
                continue
            shown += 1
            screen.set_cursor(entry["col"], entry["row"])
            sys.stdout.write("\033[1;30;43m" + hint + "\033[0m")
        if shown > 0:
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()
        return shown

    def show_link_hints(self, bar: Any) -> None:
        screen = self._screen()
        renderer = self._renderer()
        if screen is None or renderer is None:
            bar.message = "screen/renderer unavailable"
            return

        renderer_name = str(getattr(renderer, "name", "")).lower()
        renderer_protocol = str(getattr(renderer, "protocol", "")).lower()
        is_kitty_proto = renderer_protocol in {"kitty", "kitty-tmux"}
        is_supported_name = renderer_name in {"kitty", "native"}
        if not (is_kitty_proto or is_supported_name):
            bar.message = (
                "Link hints require kitty/tmux+kitty renderer; use F for full list"
            )
            return

        entries = self._get_hintable_links()
        if not entries:
            bar.message = "No hintable links on page (use F for full list)"
            return

        alphabet = "ASDFGHJKL"
        for i, entry in enumerate(entries):
            entry["hint"] = self._hint_token(i, alphabet)

        self.doc.page_states[self.doc.page].stale = True
        self.doc.display_page(bar, self.doc.page, display=False)
        self._draw_hint_badges(entries, "")

        query = ""
        keys = shortcuts()

        while True:
            shown = len([entry for entry in entries if entry["hint"].startswith(query)])
            bar.message = f"Hint: {query or '_'} ({shown} links)"
            bar.update(self.doc)

            matches = [entry for entry in entries if entry["hint"].startswith(query)]
            if query and len(matches) == 1:
                msg = self.goto_link(matches[0]["link"])
                if msg:
                    bar.message = msg
                screen.clear()
                if 0 <= self.doc.page <= self.doc.pages:
                    self.doc.page_states[self.doc.page].stale = True
                return

            key = screen.kb_input.getch()

            if key in keys.QUIT:
                self._clean_exit()
            elif key == 27 or key in keys.SHOW_LINK_HINTS or key in keys.SHOW_LINKS:
                screen.clear()
                self.doc.page_states[self.doc.page].stale = True
                return
            elif key in (127, 8, "KEY_BACKSPACE"):
                if query:
                    query = query[:-1]
            elif isinstance(key, int):
                ch = chr(key).upper()
                if ch in alphabet:
                    new_query = query + ch
                    if any(entry["hint"].startswith(new_query) for entry in entries):
                        query = new_query

    def _format_link_target(self, link: dict[str, Any]) -> str:
        kind = int(link.get("kind", 0))
        if kind == 2:
            return link.get("uri", "")
        if kind == 1:
            page = link.get("page")
            if isinstance(page, int):
                return f"page {page + 1}"
            return "page ?"
        if kind == 3:
            return f"launch {link.get('file', link.get('fileSpec', ''))}".strip()
        if kind == 5:
            return (
                f"external {link.get('fileSpec', '')}#{link.get('page', '?')}".strip()
            )
        if kind == 4:
            return str(
                link.get("name")
                or link.get("nameddest")
                or link.get("dest")
                or "named action"
            )
        return str(link)

    @staticmethod
    def _fzf_clean(text: Any) -> str:
        return " ".join(str(text or "").replace("\t", " ").split())

    def _show_links_fzf(self, links: list[dict[str, Any]], bar: Any) -> bool:
        screen = self._screen()
        if screen is None:
            return False

        fzf_bin = shutil.which("fzf")
        if fzf_bin is None:
            return False

        rows: list[str] = []
        for i, link in enumerate(links):
            anchor_text = self.doc.get_text_intersecting_rect(link["from"])
            anchor_text = anchor_text[0] if len(anchor_text) > 0 else ""
            kind = int(link.get("kind", 0))
            kind_label = {1: "INT", 2: "URL", 3: "LAUNCH", 5: "EXTPDF"}.get(
                kind, f"K{kind}"
            )
            target = self._format_link_target(link)
            rows.append(
                f"{i}\t{kind_label}\t{self._fzf_clean(anchor_text)}\t{self._fzf_clean(target)}"
            )

        selection = ""
        try:
            try:
                screen.kb_input.deactivate()
            except Exception:
                pass

            proc = subprocess.run(
                [
                    fzf_bin,
                    "--height=100%",
                    "--prompt",
                    "links> ",
                    "--header",
                    "╱ ENTER open ╱ ESC cancel ╱",
                    "--delimiter",
                    "\t",
                    "--with-nth",
                    "2..",
                ],
                input="\n".join(rows) + "\n",
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0:
                selection = (proc.stdout or "").strip()
        finally:
            try:
                screen.get_size()
                screen.init_terminal()
            except Exception:
                pass
            if 0 <= self.doc.page <= self.doc.pages:
                self.doc.page_states[self.doc.page].stale = True

        if not selection:
            return True

        chosen = selection.splitlines()[0]
        fields = chosen.split("\t", 1)
        if len(fields) < 2:
            bar.message = "Invalid link selection"
            return True

        try:
            index = int(fields[0])
        except Exception:
            bar.message = "Invalid link index"
            return True

        if index < 0 or index >= len(links):
            bar.message = "Selected link out of range"
            return True

        msg = self.goto_link(links[index])
        if msg:
            bar.message = msg
        return True

    def show_links_list(self, bar: Any) -> None:
        screen = self._screen()
        if screen is None:
            bar.message = "screen unavailable"
            return

        links = self.doc[self.doc.page].get_links()
        actionable_links = [link for link in links if link.get("kind", 0) > 0]

        if not actionable_links:
            bar.message = "No links on page"
            return

        if self._show_links_fzf(actionable_links, bar):
            return

        self.doc.page_states[self.doc.page].stale = True
        self.doc.clear_page(self.doc.page)
        screen.clear()

        def init_pad(
            url_links: list[dict[str, Any]],
        ) -> tuple[Any, Any, int, int, int, int, list[int]]:
            win, pad = screen.create_text_window(len(url_links), "URLs")
            y, x = win.getbegyx()
            h, w = win.getmaxyx()
            span: list[int] = []
            for i, url in enumerate(url_links):
                anchor_text = self.doc.get_text_intersecting_rect(url["from"])
                anchor_text = anchor_text[0] if len(anchor_text) > 0 else ""
                link_text = self._format_link_target(url)

                text = f"{anchor_text}: {link_text}"
                pad.addstr(i, 0, text)
                span.append(len(text))
            return win, pad, y, x, h, w, span

        _, pad, y, x, h, w, span = init_pad(actionable_links)

        keys = shortcuts()
        index = 0
        j = 0

        while True:
            for i, _ in enumerate(actionable_links):
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
                _, pad, y, x, h, w, span = init_pad(actionable_links)
            elif key in keys.QUIT:
                self._clean_exit()
            elif key == 27 or key in keys.SHOW_LINKS:
                screen.clear()
                return
            elif key in keys.NEXT_PAGE:
                index = min(len(actionable_links) - 1, index + 1)
            elif key in keys.PREV_PAGE:
                index = max(0, index - 1)
            elif key in keys.OPEN:
                msg = self.goto_link(actionable_links[index])
                if msg:
                    bar.message = msg
                screen.clear()
                return

            if index > j + (h - 5):
                j += 1
            if index < j:
                j -= 1

    def show_links(self, bar: Any) -> None:
        self.show_links_list(bar)
