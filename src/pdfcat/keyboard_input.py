#!/usr/bin/env python3
"""
Keyboard input handler for terminal applications.
Replacement for curses input handling.
"""

from __future__ import annotations

import select
import sys
import termios
import tty
from types import TracebackType
from typing import Any


class KeyboardInput:
    """Handle keyboard input in raw terminal mode"""

    # Key constants (compatible with old curses key codes)
    KEY_UP = "KEY_UP"
    KEY_DOWN = "KEY_DOWN"
    KEY_LEFT = "KEY_LEFT"
    KEY_RIGHT = "KEY_RIGHT"
    KEY_HOME = "KEY_HOME"
    KEY_END = "KEY_END"
    KEY_PPAGE = "KEY_PPAGE"  # Page Up
    KEY_NPAGE = "KEY_NPAGE"  # Page Down
    KEY_ENTER = 10
    KEY_RESIZE = "KEY_RESIZE"

    def __init__(self) -> None:
        self.fd = sys.stdin.fileno()
        self.old_settings: list[Any] | None = None
        self._active = False

    def activate(self) -> None:
        """Enter raw terminal mode"""
        if self._active:
            return

        self.old_settings = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)
        self._active = True

        # Hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def deactivate(self) -> None:
        """Restore terminal to normal mode"""
        if not self._active:
            return

        if self.old_settings:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

        # Show cursor
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

        self._active = False

    def __enter__(self) -> KeyboardInput:
        """Context manager entry"""
        self.activate()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Context manager exit"""
        self.deactivate()

    def getch(self, timeout: float | None = None) -> int | str:
        """
        Read a character with optional timeout

        Args:
            timeout: seconds to wait (float), None for blocking, 0 for non-blocking

        Returns:
            int: character code (e.g., ord('j'))
            str: special key name (KEY_UP, KEY_DOWN, etc.)
            -1: timeout/no input available
        """
        # Check if input is available
        if timeout is not None:
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            if not ready:
                return -1

        # Read first character
        ch = sys.stdin.read(1)
        if not ch:
            return -1

        # Handle escape sequences (special keys)
        if ch == "\033":
            # This could be ESC key or the start of an escape sequence
            # Wait briefly to see if more characters follow
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)

            if not ready:
                # Just ESC key pressed
                return 27

            # Read the next character
            ch2 = sys.stdin.read(1)

            if ch2 == "[":
                # CSI sequence (most special keys)
                ch3 = sys.stdin.read(1)

                # Single-character CSI sequences
                if ch3 == "A":
                    return self.KEY_UP
                elif ch3 == "B":
                    return self.KEY_DOWN
                elif ch3 == "C":
                    return self.KEY_RIGHT
                elif ch3 == "D":
                    return self.KEY_LEFT
                elif ch3 == "H":
                    return self.KEY_HOME
                elif ch3 == "F":
                    return self.KEY_END

                # Multi-character CSI sequences
                elif ch3 in "0123456789":
                    # Read until we get a letter or ~
                    seq = ch3
                    while True:
                        ch4 = sys.stdin.read(1)
                        seq += ch4
                        if ch4.isalpha() or ch4 == "~":
                            break

                    # Parse the sequence
                    if seq == "5~":
                        return self.KEY_PPAGE  # Page Up
                    elif seq == "6~":
                        return self.KEY_NPAGE  # Page Down
                    elif seq == "1~" or seq == "7~":
                        return self.KEY_HOME
                    elif seq == "4~" or seq == "8~":
                        return self.KEY_END

                # Unknown CSI sequence
                return -1

            elif ch2 == "O":
                # SS3 sequence (alternate special keys)
                ch3 = sys.stdin.read(1)
                if ch3 == "H":
                    return self.KEY_HOME
                elif ch3 == "F":
                    return self.KEY_END
                return -1

            # Unknown escape sequence
            return 27

        # Handle special characters
        if ch == "\r" or ch == "\n":
            return self.KEY_ENTER

        # Regular character
        return ord(ch)
