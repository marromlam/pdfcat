"""Core runtime objects: config, buffers, screen, and cache helpers."""

from __future__ import annotations

import array
import fcntl
import hashlib
import json
import os
import shutil
import sys
import termios
from time import monotonic, sleep
from typing import Any

from rich.console import Console

from .keyboard_input import KeyboardInput


class Config:
    def __init__(self) -> None:
        self._loaded_keys: set[str] = set()
        self.BIBTEX = ""
        self.KITTYCMD = (
            "kitty --single-instance --instance-group=1"  # open notes in a new OS window
        )
        # self.KITTYCMD = 'kitty @ new-window' # open notes in split kitty window
        self.TINT_COLOR = "#999999"
        self.URL_BROWSER_LIST = [
            "gnome-open",
            "gvfs-open",
            "xdg-open",
            "kde-open",
            "firefox",
            "w3m",
            "elinks",
            "lynx",
        ]
        self.URL_BROWSER: str | None = None
        self.GUI_VIEWER = "system"
        self.AUTOPLAY_FPS = 8
        self.AUTOPLAY_LOOP = True
        self.AUTOPLAY_END_PAGE = None  # 1-based page; None means end of document
        self.SHOW_STATUS_BAR = True
        home_dir = os.getenv("HOME") or os.path.expanduser("~")
        self.NOTES_DIR = os.path.join(home_dir, "notes")
        self.NOTE_PATH = os.path.join(home_dir, "inbox.org")

    def detect_browser_command(self) -> None:
        if sys.platform == "darwin":
            self.URL_BROWSER = "open"
        else:
            for i in self.URL_BROWSER_LIST:
                if shutil.which(i) is not None:
                    self.URL_BROWSER = i
                    break

    def load_user_config(self) -> None:
        config_file = os.path.join(
            os.environ["HOME"],
            ".config",
            "pdfcat",
            "config",
        )
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                prefs = json.load(f)
            for key in prefs:
                setattr(self, key, prefs[key])
                self._loaded_keys.add(key)


class Buffers:
    def __init__(self) -> None:
        self.docs: list[Any] = []
        self.current = 0
        self.on_empty: Any = None

    def switch_to_buffer(self, n: int) -> None:
        _n = min(len(self.docs), n)
        _n = max(0, _n)
        self.current = _n

    def cycle(self, count: int) -> None:
        # self.current = (self.current + count) % len(self.docs)
        len_buffers = len(self.docs) - 1
        _c = max(0, self.current + count)
        self.current = 0 if _c > len_buffers else _c

    def close_buffer(self, n: int) -> None:
        del self.docs[n]
        if self.current == n:
            self.current = max(0, n - 1)
        if len(self.docs) == 0 and callable(self.on_empty):
            self.on_empty()


class Screen:
    def __init__(self) -> None:
        self.rows = 0
        self.cols = 0
        self.width = 0
        self.height = 0
        self.cell_width = 0
        self.cell_height = 0
        self.kb_input: KeyboardInput | None = None
        self.console: Console | None = None

    def get_size(self) -> None:
        fd = sys.stdout
        buf = array.array("H", [0, 0, 0, 0])
        fcntl.ioctl(fd, termios.TIOCGWINSZ, buf)
        r, c, w, h = tuple(buf)
        cw = w // (c or 1)
        ch = h // (r or 1)
        self.rows = r
        self.cols = c
        self.width = w
        self.height = h
        self.cell_width = cw
        self.cell_height = ch

    def init_terminal(self) -> None:
        """Initialize terminal (replaces init_curses)"""
        os.environ.setdefault("ESCDELAY", "25")

        # Initialize keyboard input handler
        self.kb_input = KeyboardInput()
        self.kb_input.activate()

        # Initialize Rich console
        self.console = Console()

        # Clear screen using ANSI (don't use console.clear() as it might interfere with graphics)
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.write("\033[?25l")  # Hide cursor
        sys.stdout.flush()

        # Swallow any initial keypresses
        if self.kb_input is not None:
            self.kb_input.getch(timeout=0.1)

    def create_text_window(self, length: int, header: str) -> tuple[Any, Any]:
        """Create a text window (simplified for Rich)"""
        # Clear the screen using ANSI
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

        # Create a simple window object with position/size info
        # This replaces ncurses window for compatibility
        class SimpleWindow:
            def __init__(self, rows: int, cols: int) -> None:
                self.rows = rows
                self.cols = cols
                self.y = 0
                self.x = 0

            def getbegyx(self) -> tuple[int, int]:
                return (self.y, self.x)

            def getmaxyx(self) -> tuple[int, int]:
                return (self.rows, self.cols)

            def addstr(self, y: int, x: int, text: str) -> None:
                # Print text at position (simplified)
                sys.stdout.write(f"\033[{y + 1};{x + 1}H{text}")
                sys.stdout.flush()

            def chgat(self, y: int, x: int, length: int, attr: int) -> None:
                # Change attributes (ignored for now)
                pass

            def refresh(self, *args: Any) -> None:
                # Refresh (no-op for now)
                pass

        # Create window and pad (same object for simplicity)
        win = SimpleWindow(self.rows - 2, self.cols - 4)
        pad = win  # Reuse same object as pad

        return win, pad

    def drain_input(self) -> None:
        """Consume any pending keyboard input"""
        if self.kb_input is None:
            return
        end = monotonic() + 0.1
        while monotonic() < end:
            self.kb_input.getch(timeout=0)
            sleep(0.01)

    def clear(self) -> None:
        sys.stdout.buffer.write("\033[2J".encode("ascii"))
        sys.stdout.buffer.write("\033[?25l".encode("ascii"))  # Hide cursor
        sys.stdout.flush()

    def set_cursor(self, c: int, r: int) -> None:
        if c > self.cols:
            c = self.cols
        elif c < 1:
            c = 1
        if r > self.rows:
            r = self.rows
        elif r < 1:
            r = 1
        sys.stdout.buffer.write("\033[{};{}f".format(r, c).encode("ascii"))
        sys.stdout.flush()

    def write_text_at(self, c: int, r: int, string: str) -> None:
        self.set_cursor(c, r)
        sys.stdout.write(string)
        sys.stdout.flush()


def get_filehash(path: str) -> str:
    blocksize = 65536
    hasher = hashlib.md5()
    with open(path, "rb") as afile:
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
    return hasher.hexdigest()


def get_cachefile(path: str) -> str:
    filehash = get_filehash(path)
    cachedir = os.path.expanduser(os.path.join(os.getenv("XDG_CACHE_HOME", "~/.cache"), "pdfcat"))
    os.makedirs(cachedir, exist_ok=True)
    cachefile = os.path.join(cachedir, filehash)
    return cachefile
