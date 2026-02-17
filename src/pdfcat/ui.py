"""User interface helpers: status bar, key maps, and visual mode."""

from __future__ import annotations

import curses
import sys
from typing import Any

import fitz
import pyperclip
from rich.console import Console
from rich.text import Text


class status_bar:
    """Status bar using Rich for beautiful formatting"""

    def __init__(self) -> None:
        self.cols = 40
        self.rows = 1
        self.cmd = " "
        self.message = " "
        self.counter = " "
        self._render_console: Console | None = None
        self._last_rendered: tuple[Any, ...] | None = None  # Cache last rendered output

    def update(self, doc: Any) -> None:
        """Update and render status bar with Rich styling"""
        config = doc._config() if hasattr(doc, "_config") else None
        screen = doc._screen() if hasattr(doc, "_screen") else None
        renderer = doc._renderer() if hasattr(doc, "_renderer") else None
        if screen is None:
            return

        if not bool(getattr(config, "SHOW_STATUS_BAR", True)):
            if self._last_rendered != ("hidden",):
                sys.stdout.write(f"\033[{screen.rows};1H")
                sys.stdout.write("\033[K")
                sys.stdout.flush()
                self._last_rendered = ("hidden",)
            return

        # Get page info
        p = doc.physical_to_logical_page()
        pc = doc.physical_to_logical_page(doc.pages)
        self.counter = f"[{p}/{pc}]"

        # Get terminal width
        w = self.cols = screen.cols
        renderer_name = getattr(renderer, "name", "") or "unknown"
        renderer_protocol = getattr(renderer, "protocol", None)
        if renderer_protocol:
            renderer_label = f"[{renderer_name}:{renderer_protocol}]"
        else:
            renderer_label = f"[{renderer_name}]"

        # Create cache key to check if status bar changed
        cache_key = (self.cmd, self.message, self.counter, renderer_label, w)
        if self._last_rendered == cache_key:
            return  # No change, skip rendering
        self._last_rendered = cache_key

        # Layout: [cmd on left] [message in middle] [renderer] [counter]
        cm_w = len(self.cmd)
        co_w = len(self.counter)
        re_w = len(renderer_label)

        # Drop renderer label on very narrow terminals first.
        if w < (cm_w + co_w + re_w + 6):
            renderer_label = ""
            re_w = 0
        renderer_gap = 1 if renderer_label else 0

        # Reserve room for right-aligned renderer+counter.
        max_message_width = max(0, w - cm_w - co_w - re_w - renderer_gap - 4)
        message = self.message
        if max_message_width == 0:
            message = ""
        elif len(message) > max_message_width:
            if max_message_width == 1:
                message = "…"
            else:
                message = message[: max_message_width - 1] + "…"
        me_w = len(message)

        # Build Rich text with styling
        # Background color: #121212 (dark gray)
        text = Text()

        # Left: command
        text.append(self.cmd, style="bold cyan on #121212")
        text.append("  ", style="on #121212")

        # Middle: message
        text.append(message, style="yellow on #121212")
        current_pos = cm_w + 2 + me_w
        right_block_width = co_w + re_w + renderer_gap
        padding = max(1, w - current_pos - right_block_width)
        text.append(" " * padding, style="on #121212")

        # Right: renderer indicator + page counter
        if renderer_label:
            text.append(renderer_label, style="bright_black on #121212")
            text.append(" ", style="on #121212")

        text.append(self.counter, style="yellow on #121212")

        # Fill rest of line with background
        remaining = w - len(text.plain)
        if remaining > 0:
            text.append(" " * remaining, style="on #121212")

        # Render the status bar using Rich to get ANSI color codes
        from io import StringIO

        # Create a string buffer to capture Rich's output
        string_buffer = StringIO()

        # Create or reuse render console
        if self._render_console is None:
            self._render_console = Console(
                file=string_buffer, force_terminal=True, width=w, legacy_windows=False
            )
        else:
            # Update the file buffer
            self._render_console = Console(
                file=string_buffer, force_terminal=True, width=w, legacy_windows=False
            )

        # Render the Rich text to the buffer
        self._render_console.print(text, end="", overflow="crop", highlight=False)
        rendered_text = string_buffer.getvalue()

        # Position cursor at bottom row and write
        sys.stdout.write(f"\033[{screen.rows};1H")
        sys.stdout.write(rendered_text)
        sys.stdout.write("\033[K")  # Clear to end of line
        sys.stdout.write("\033[?25l")  # Hide cursor
        sys.stdout.flush()


def get_selected_text_rows(
    doc: Any, left: int, right: int, selection: list[int]
) -> str:
    left_col, top_row, _, _ = doc.page_states[doc.page].place
    top = (left_col + left, top_row + selection[0] - 1)
    bottom = (left_col + right, top_row + selection[1])
    top_pix, bottom_pix = doc.cell_coords_to_pixels(top, bottom)
    rect = fitz.Rect(top_pix, bottom_pix)
    select_text = doc.get_text_in_rect(rect)
    link = doc.make_link()
    select_text = select_text + [link]
    return " ".join(select_text)


def apply_crop_from_selection(
    doc: Any, left: int, right: int, selection: list[int]
) -> None:
    left_col, top_row, _, _ = doc.page_states[doc.page].place
    top = (left_col + left, top_row + selection[0] - 1)
    bottom = (left_col + right, top_row + selection[1])
    top_pix, bottom_pix = doc.cell_coords_to_pixels(top, bottom)
    doc.manualcrop = True
    doc.manualcroprect = [top_pix, bottom_pix]


# Viewer functions


def run_visual_mode(doc: Any, bar: status_bar) -> None:
    screen = doc._screen() if hasattr(doc, "_screen") else None
    clean_exit_cb = doc._clean_exit if hasattr(doc, "_clean_exit") else None
    if screen is None:
        return

    left_col, top_row, right_col, bottom_row = doc.page_states[doc.page].place

    width = (right_col - left_col) + 1

    def highlight_row(
        row: int, left: int, right: int, fill: str = "▒", color: str = "yellow"
    ) -> None:
        if color == "yellow":
            cc = 33
        elif color == "blue":
            cc = 34
        elif color == "none":
            cc = 0

        fill = fill[0] * (right - left)

        screen.set_cursor(left_col + left, row)
        sys.stdout.buffer.write("\033[{}m".format(cc).encode("ascii"))
        # sys.stdout.buffer.write('\033[{}m'.format(cc + 10).encode('ascii'))
        sys.stdout.write(fill)
        sys.stdout.flush()
        sys.stdout.buffer.write(b"\033[0m")
        sys.stdout.flush()

    def unhighlight_row(row: int) -> None:
        # screen.set_cursor(l,row)
        # sys.stdout.write(' ' * width)
        # sys.stdout.flush()
        highlight_row(row, 0, width, fill=" ", color="none")

    def highlight_selection(
        selection: list[int],
        left: int,
        right: int,
        fill: str = "▒",
        color: str = "blue",
    ) -> None:
        a = min(selection)
        b = max(selection)
        for r in range(a, b + 1):
            highlight_row(r, left, right, fill, color)

    def unhighlight_selection(selection: list[int]) -> None:
        highlight_selection(selection, 0, width, fill=" ", color="none")

    current_row = top_row
    left = 0
    right = width
    select = False
    selection = [current_row, current_row]
    count_string = ""

    while True:
        bar.cmd = count_string
        bar.update(doc)
        unhighlight_selection([top_row, bottom_row])
        if select:
            highlight_selection(selection, left, right, color="blue")
        else:
            highlight_selection(selection, left, right, color="yellow")

        if count_string == "":
            count = 1
        else:
            count = int(count_string)

        keys = shortcuts()
        key = screen.kb_input.getch()

        if key in range(48, 58):  # numerals
            count_string = count_string + chr(key)

        elif key in keys.QUIT:
            if callable(clean_exit_cb):
                clean_exit_cb()

        elif key == 27 or key in keys.VISUAL_MODE:
            unhighlight_selection([top_row, bottom_row])
            return

        elif key in keys.SELECT:
            if select:
                select = False
            else:
                select = True
            selection = [current_row, current_row]
            count_string = ""

        elif key in keys.NEXT_PAGE:
            current_row += count
            current_row = min(current_row, bottom_row)
            if select:
                selection[1] = current_row
            else:
                selection = [current_row, current_row]
            count_string = ""

        elif key in keys.PREV_PAGE:
            current_row -= count
            current_row = max(current_row, top_row)
            if select:
                selection[1] = current_row
            else:
                selection = [current_row, current_row]
            count_string = ""

        elif key in keys.NEXT_CHAP:
            right = min(width, right + count)
            count_string = ""

        elif key in {ord("L"), curses.KEY_SRIGHT}:
            right = max(left + 1, right - count)
            count_string = ""

        elif key in keys.PREV_CHAP:
            left = max(0, left - count)
            count_string = ""

        elif key in {ord("H"), curses.KEY_SLEFT}:
            left = min(left + count, right - 1)
            count_string = ""

        elif key in keys.GOTO_PAGE:
            current_row = bottom_row
            if select:
                selection[1] = current_row
            else:
                selection = [current_row, current_row]
            count_string = ""

        elif key in keys.GOTO:
            current_row = top_row
            if select:
                selection[1] = current_row
            else:
                selection = [current_row, current_row]
            count_string = ""

        elif key in keys.YANK:
            if selection == [None, None]:
                selection = [current_row, current_row]
            selection.sort()
            select_text = get_selected_text_rows(doc, left, right, selection)
            select_text = "> " + select_text
            pyperclip.copy(select_text)
            unhighlight_selection([top_row, bottom_row])
            bar.message = "copied"
            return

        elif key in keys.INSERT_NOTE:
            msg = doc.open_notes_editor()
            if msg:
                bar.message = msg
            else:
                bar.message = "opened notes"
            unhighlight_selection([top_row, bottom_row])
            return

        elif key in keys.APPEND_NOTE:
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
            unhighlight_selection([top_row, bottom_row])
            return

        elif key in keys.TOGGLE_AUTOCROP and selection != [None, None]:
            apply_crop_from_selection(doc, left, right, selection)
            unhighlight_selection([top_row, bottom_row])
            doc.mark_all_pages_stale()
            return


class shortcuts:
    def __init__(self) -> None:
        self.GOTO_PAGE = [ord("G")]
        self.GOTO_PAGE_PHYSICAL = [ord("J")]
        self.GOTO = [ord("g")]
        self.NEXT_PAGE = [ord("j"), "KEY_DOWN", ord(" ")]
        self.PREV_PAGE = [ord("k"), "KEY_UP"]
        self.GO_BACK = [ord("p")]
        self.NEXT_CHAP = [ord("l"), "KEY_RIGHT"]
        self.PREV_CHAP = [ord("h"), "KEY_LEFT"]
        self.BUFFER_NEXT = [ord("b")]
        self.BUFFER_PREV = [ord("B")]
        self.HINTS = [ord("f")]
        self.OPEN = [10, "KEY_RIGHT"]  # Enter, Right arrow
        self.SHOW_TOC = [ord("t")]
        self.SHOW_META = [ord("M")]
        self.UPDATE_FROM_BIB = [ord("b")]
        self.SHOW_LINK_HINTS = [ord("f")]
        self.SHOW_LINKS = [ord("F")]
        self.TOGGLE_TEXT_MODE = [ord("s"), ord("T")]
        self.ROTATE_CW = [ord("r")]
        self.ROTATE_CCW = [ord("R")]
        self.VISUAL_MODE = [ord("S")]
        self.SELECT = [ord("v")]
        self.YANK = [ord("y")]
        self.INSERT_NOTE = [ord("n")]
        self.APPEND_NOTE = [ord("a")]
        self.TOGGLE_AUTOCROP = [ord("c")]
        self.TOGGLE_ALPHA = [ord("A")]
        self.TOGGLE_INVERT = [ord("i")]
        self.TOGGLE_TINT = [ord("d")]
        self.TOGGLE_AUTOPLAY = [ord("z")]
        self.SET_AUTOPLAY_END = [ord("E")]
        self.TOGGLE_PRESENTER = [ord("P")]
        self.SET_PAGE_LABEL = [ord("P")]
        self.SET_PAGE_ALT = [ord("I")]
        self.INC_FONT = [ord("=")]
        self.DEC_FONT = [ord("-")]
        self.OPEN_GUI = [ord("O"), ord("X")]
        self.REFRESH = [18, "KEY_RESIZE"]  # CTRL-R
        self.REVERSE_SYNCTEX = [19]  # CTRL-S
        self.SHOW_HELP = [ord("?")]
        self.QUIT = [3, ord("q")]
        self.DEBUG = [ord("D")]
