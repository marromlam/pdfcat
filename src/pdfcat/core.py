"""Core runtime objects: config, buffers, screen, and cache helpers."""

from __future__ import annotations

import array
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
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
        # open notes in a new OS window
        self.KITTYCMD = "kitty --single-instance --instance-group=1"
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

    def cycle(self, count: int) -> None:
        if not self.docs:
            self.current = 0
            return
        self.current = (self.current + count) % len(self.docs)


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

    def _kitty_window_size_override(self) -> tuple[int, int, int, int] | None:
        """Try to get active kitty window size from kitty remote control.

        Returns:
            tuple(rows, cols, width_px, height_px) or None when unavailable.
        """
        if os.environ.get("TMUX"):
            return None
        kitty_window_id = os.environ.get("KITTY_WINDOW_ID")
        if not kitty_window_id:
            return None
        kitty_bin = shutil.which("kitty")
        if kitty_bin is None:
            return None

        def _extract_size(node: Any) -> tuple[int, int, int, int] | None:
            if isinstance(node, dict):
                node_id = node.get("id") or node.get("window_id")
                if str(node_id) == str(kitty_window_id):
                    cols = node.get("columns") or node.get("cols")
                    rows = node.get("lines") or node.get("rows")
                    width = node.get("width")
                    height = node.get("height")

                    geom = node.get("window_geometry") or node.get("geometry") or {}
                    if (width is None or height is None) and isinstance(geom, dict):
                        left = geom.get("left")
                        right = geom.get("right")
                        top = geom.get("top")
                        bottom = geom.get("bottom")
                        if all(isinstance(v, int) for v in [left, right, top, bottom]):
                            width = max(0, right - left)
                            height = max(0, bottom - top)

                    if all(
                        isinstance(v, int) and v > 0
                        for v in [rows, cols, width, height]
                    ):
                        return (rows, cols, width, height)

                for value in node.values():
                    found = _extract_size(value)
                    if found is not None:
                        return found
            elif isinstance(node, list):
                for item in node:
                    found = _extract_size(item)
                    if found is not None:
                        return found
            return None

        commands = [
            [kitty_bin, "@", "ls", "--self"],
            [kitty_bin, "@", "ls"],
        ]
        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                if result.returncode != 0:
                    continue
                payload = (result.stdout or "").strip()
                if payload == "":
                    continue
                data = json.loads(payload)
                found = _extract_size(data)
                if found is not None:
                    return found
            except Exception:
                continue
        return None

    def get_size(self) -> None:
        fd = sys.stdout
        buf = array.array("H", [0, 0, 0, 0])
        fcntl.ioctl(fd, termios.TIOCGWINSZ, buf)
        r, c, w, h = tuple(buf)
        kitty_size = self._kitty_window_size_override()
        if kitty_size is not None:
            r, c, w, h = kitty_size
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
    cachedir = os.path.expanduser(
        os.path.join(os.getenv("XDG_CACHE_HOME", "~/.cache"), "pdfcat")
    )
    os.makedirs(cachedir, exist_ok=True)
    cachefile = os.path.join(cachedir, filehash)
    return cachefile
