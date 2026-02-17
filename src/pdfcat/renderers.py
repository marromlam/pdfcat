"""Terminal graphics renderers and renderer factory."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import zlib
from abc import ABC, abstractmethod
from base64 import standard_b64encode
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any

from .runtime_context import get_context


def _show_status_bar() -> bool:
    ctx = get_context()
    if ctx is not None:
        config = getattr(ctx, "config", None)
        return bool(getattr(config, "SHOW_STATUS_BAR", True))
    return True


class RendererUnavailableError(Exception):
    """Raised when a renderer is not available"""

    pass


class RenderingEngine(ABC):
    """Abstract base class for rendering engines"""

    @abstractmethod
    def detect_support(self) -> bool:
        """Check if this rendering engine is supported"""
        pass

    @abstractmethod
    def render_pixmap(
        self,
        pixmap: Any,
        page_num: int,
        placement: tuple[int, int, int, int],
        screen: Any,
        page_state: Any | None = None,
    ) -> bool:
        """Render a pixmap to the terminal at given placement"""
        pass

    @abstractmethod
    def clear_image(self, page_num: int) -> None:
        """Clear a previously rendered image"""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources (temp files, etc.)"""
        pass


class KittyRenderer(RenderingEngine):
    """Native Kitty protocol renderer"""

    def __init__(self) -> None:
        self.name = "kitty"
        self.requires_clear_before_render = False

    def detect_support(self) -> bool:
        """Check if Kitty protocol is supported via environment."""
        term = (os.environ.get("TERM") or "").lower()
        term_program = (os.environ.get("TERM_PROGRAM") or "").lower()
        kitty_env = bool(
            os.environ.get("KITTY_WINDOW_ID") or os.environ.get("KITTY_PID")
        )

        if "kitty" in term or kitty_env or term_program in {"kitty", "wezterm"}:
            logging.debug("Kitty protocol detected via environment")
            return True
        return False

    def _serialize_gr_command(
        self, cmd: dict[str, Any], payload: bytes | None = None
    ) -> bytes:
        """Serialize a graphics command"""
        cmd_str = ",".join("{}={}".format(k, v) for k, v in cmd.items())
        ans: list[bytes] = []
        w = ans.append
        w(b"\033_G"), w(cmd_str.encode("ascii"))
        if payload:
            w(b";")
            w(payload)
        w(b"\033\\")
        return b"".join(ans)

    def _write_gr_cmd(self, cmd: dict[str, Any], payload: bytes | None = None) -> None:
        """Write a graphics command to stdout"""
        sys.stdout.buffer.write(self._serialize_gr_command(cmd, payload))
        sys.stdout.flush()

    def _write_chunked(self, cmd: dict[str, Any], data: bytes) -> None:
        """Write data in chunks"""
        if cmd["f"] != 100:
            data = zlib.compress(data)
            cmd["o"] = "z"
        data = standard_b64encode(data)
        while data:
            chunk, data = data[:4096], data[4096:]
            m = 1 if data else 0
            cmd["m"] = m
            self._write_gr_cmd(cmd, chunk)
            cmd.clear()

    def render_pixmap(
        self,
        pixmap: Any,
        page_num: int,
        placement: tuple[int, int, int, int],
        screen: Any,
        page_state: Any | None = None,
    ) -> bool:
        """Render a pixmap using Kitty protocol"""
        # Build command to send to kitty
        cmd = {"i": page_num + 1, "t": "d", "s": pixmap.width, "v": pixmap.height}

        if pixmap.alpha:
            cmd["f"] = 32
        else:
            cmd["f"] = 24

        # Transfer the image
        self._write_chunked(cmd, pixmap.samples)

        # Display the image
        cmd = {"a": "p", "i": page_num + 1, "z": -1}
        self._write_gr_cmd(cmd)
        return True

    def clear_image(self, page_num: int) -> None:
        """Clear a previously rendered image"""
        cmd = {"a": "d", "d": "a", "i": page_num + 1}
        self._write_gr_cmd(cmd)

    def cleanup(self) -> None:
        """Cleanup resources"""
        pass


class NativeRenderer(RenderingEngine):
    """Native Kitty renderer that replaces the external timg binary."""

    _MAX_CHUNK = 4096
    _TMUX_START = b"\033Ptmux;"
    _TMUX_END = b"\033\\"
    # Kitty/tmux unicode placeholder codepoint used by timg:
    # UTF-8 bytes F4 8E BB AE -> U+10EEEE
    _PLACEHOLDER = "\U0010eeee"
    _ROWCOL_DIACRITICS = [
        0x0305,
        0x030D,
        0x030E,
        0x0310,
        0x0312,
        0x033D,
        0x033E,
        0x033F,
        0x0346,
        0x034A,
        0x034B,
        0x034C,
        0x0350,
        0x0351,
        0x0352,
        0x0357,
        0x035B,
        0x0363,
        0x0364,
        0x0365,
        0x0366,
        0x0367,
        0x0368,
        0x0369,
        0x036A,
        0x036B,
        0x036C,
        0x036D,
        0x036E,
        0x036F,
        0x0483,
        0x0484,
        0x0485,
        0x0486,
        0x0487,
        0x0592,
        0x0593,
        0x0594,
        0x0595,
        0x0597,
        0x0598,
        0x0599,
        0x059C,
        0x059D,
        0x059E,
        0x059F,
        0x05A0,
        0x05A1,
        0x05A8,
        0x05A9,
        0x05AB,
        0x05AC,
        0x05AF,
        0x05C4,
        0x0610,
        0x0611,
        0x0612,
        0x0613,
        0x0614,
        0x0615,
        0x0616,
        0x0617,
        0x0657,
        0x0658,
        0x0659,
        0x065A,
        0x065B,
        0x065D,
        0x065E,
        0x06D6,
        0x06D7,
        0x06D8,
        0x06D9,
        0x06DA,
        0x06DB,
        0x06DC,
        0x06DF,
        0x06E0,
        0x06E1,
        0x06E2,
        0x06E4,
        0x06E7,
        0x06E8,
        0x06EB,
        0x06EC,
        0x0730,
        0x0732,
        0x0733,
        0x0735,
        0x0736,
        0x073A,
        0x073D,
        0x073F,
        0x0740,
        0x0741,
        0x0743,
        0x0745,
        0x0747,
        0x0749,
        0x074A,
        0x07EB,
        0x07EC,
        0x07ED,
        0x07EE,
        0x07EF,
        0x07F0,
        0x07F1,
        0x07F3,
        0x0816,
        0x0817,
        0x0818,
        0x0819,
        0x081B,
        0x081C,
        0x081D,
        0x081E,
        0x081F,
        0x0820,
        0x0821,
        0x0822,
        0x0823,
        0x0825,
        0x0826,
        0x0827,
        0x0829,
        0x082A,
        0x082B,
        0x082C,
        0x082D,
        0x0951,
        0x0953,
        0x0954,
        0x0F82,
        0x0F83,
        0x0F86,
        0x0F87,
        0x135D,
        0x135E,
        0x135F,
        0x17DD,
        0x193A,
        0x1A17,
        0x1A75,
        0x1A76,
        0x1A77,
        0x1A78,
        0x1A79,
        0x1A7A,
        0x1A7B,
        0x1A7C,
        0x1B6B,
        0x1B6D,
        0x1B6E,
        0x1B6F,
        0x1B70,
        0x1B71,
        0x1B72,
        0x1B73,
        0x1CD0,
        0x1CD1,
        0x1CD2,
        0x1CDA,
        0x1CDB,
        0x1CE0,
        0x1DC0,
        0x1DC1,
        0x1DC3,
        0x1DC4,
        0x1DC5,
        0x1DC6,
        0x1DC7,
        0x1DC8,
        0x1DC9,
        0x1DCB,
        0x1DCC,
        0x1DD1,
        0x1DD2,
        0x1DD3,
        0x1DD4,
        0x1DD5,
        0x1DD6,
        0x1DD7,
        0x1DD8,
        0x1DD9,
        0x1DDA,
        0x1DDB,
        0x1DDC,
        0x1DDD,
        0x1DDE,
        0x1DDF,
        0x1DE0,
        0x1DE1,
        0x1DE2,
        0x1DE3,
        0x1DE4,
        0x1DE5,
        0x1DE6,
        0x1DFE,
        0x20D0,
        0x20D1,
        0x20D4,
        0x20D5,
        0x20D6,
        0x20D7,
        0x20DB,
        0x20DC,
        0x20E1,
        0x20E7,
        0x20E9,
        0x20F0,
        0x2CEF,
        0x2CF0,
        0x2CF1,
        0x2DE0,
        0x2DE1,
        0x2DE2,
        0x2DE3,
        0x2DE4,
        0x2DE5,
        0x2DE6,
        0x2DE7,
        0x2DE8,
        0x2DE9,
        0x2DEA,
        0x2DEB,
        0x2DEC,
        0x2DED,
        0x2DEE,
        0x2DEF,
        0x2DF0,
        0x2DF1,
        0x2DF2,
        0x2DF3,
        0x2DF4,
        0x2DF5,
        0x2DF6,
        0x2DF7,
        0x2DF8,
        0x2DF9,
        0x2DFA,
        0x2DFB,
        0x2DFC,
        0x2DFD,
        0x2DFE,
        0x2DFF,
        0xA66F,
        0xA67C,
        0xA67D,
        0xA6F0,
        0xA6F1,
        0xA8E0,
        0xA8E1,
        0xA8E2,
        0xA8E3,
        0xA8E4,
        0xA8E5,
        0xA8E6,
        0xA8E7,
        0xA8E8,
        0xA8E9,
        0xA8EA,
        0xA8EB,
        0xA8EC,
        0xA8ED,
        0xA8EE,
        0xA8EF,
        0xA8F0,
        0xA8F1,
        0xAAB0,
        0xAAB2,
        0xAAB3,
        0xAAB7,
        0xAAB8,
        0xAABE,
        0xAABF,
        0xAAC1,
        0xFE20,
        0xFE21,
        0xFE22,
        0xFE23,
        0xFE24,
        0xFE25,
        0xFE26,
        0x10A0F,
        0x10A38,
        0x1D185,
        0x1D186,
        0x1D187,
        0x1D188,
        0x1D189,
        0x1D1AA,
        0x1D1AB,
        0x1D1AC,
        0x1D1AD,
        0x1D242,
        0x1D243,
        0x1D244,
    ]

    def __init__(self) -> None:
        self.name = "native"
        self.requires_clear_before_render = False
        self._term = (os.environ.get("TERM") or "").lower()
        self._term_program = (os.environ.get("TERM_PROGRAM") or "").lower()
        self._kitty_env = bool(
            os.environ.get("KITTY_WINDOW_ID") or os.environ.get("KITTY_PID")
        )
        self.in_tmux = bool(os.environ.get("TMUX"))
        self.protocol = self._detect_graphics_protocol()
        self._id_counter = ((os.getpid() & 0xFFFF) << 8) & 0xFFFFFFFF
        self._last_displayed_image_id: int | None = None
        self._last_tmux_history_clear = 0.0
        self._tmux_history_clear_interval = 1.0  # seconds
        if self.in_tmux and self.protocol == "kitty-tmux":
            self._enable_tmux_passthrough()

    def detect_support(self) -> bool:
        """Check if native Kitty protocol is available."""
        if self.protocol not in ("kitty", "kitty-tmux"):
            raise RendererUnavailableError("kitty protocol unavailable")
        return True

    def _tmux_client_termname(self) -> str:
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#{client_termname}"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return (result.stdout or "").strip().lower()
        except Exception:
            return ""

    def _detect_graphics_protocol(self) -> str:
        term = self._term
        term_program = self._term_program
        kitty_env = self._kitty_env

        if self.in_tmux:
            tmux_client_term = self._tmux_client_termname()
            if ("kitty" in tmux_client_term) or kitty_env:
                return "kitty-tmux"
            raise RendererUnavailableError(
                "tmux detected but kitty-compatible client terminal not found"
            )

        if "kitty" in term or kitty_env:
            return "kitty"
        if term_program in {"kitty", "wezterm"}:
            return "kitty"

        raise RendererUnavailableError("kitty protocol unavailable in this terminal")

    def _enable_tmux_passthrough(self) -> None:
        try:
            subprocess.run(
                ["tmux", "set", "-p", "allow-passthrough", "on"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def _next_image_id(self) -> int:
        self._id_counter = (self._id_counter + 1) & 0xFFFFFFFF
        return self._id_counter or 1

    def _serialize_gr_command(
        self, cmd: dict[str, Any], payload: bytes | None = None
    ) -> bytes:
        cmd_str = ",".join(f"{k}={v}" for k, v in cmd.items()).encode("ascii")
        parts = [b"\033_G", cmd_str]
        if payload is not None:
            parts.extend([b";", payload])
        parts.append(b"\033\\")
        data = b"".join(parts)
        if self.in_tmux and self.protocol == "kitty-tmux":
            # tmux passthrough requires escaping ESC as ESC ESC.
            data = (
                self._TMUX_START + data.replace(b"\033", b"\033\033") + self._TMUX_END
            )
        return data

    def _write_gr_cmd(self, cmd: dict[str, Any], payload: bytes | None = None) -> None:
        sys.stdout.buffer.write(self._serialize_gr_command(cmd, payload))

    def _delete_image(self, image_id: int | None) -> None:
        if image_id is None:
            return
        self._write_gr_cmd({"a": "d", "d": "i", "i": image_id})

    def _clear_tmux_stale_placeholder_margins(
        self,
        old_place: tuple[int, int, int, int] | None,
        new_place: tuple[int, int, int, int] | None,
        screen: Any,
    ) -> None:
        """Clear leftover placeholder glyphs when placement shrinks/moves in tmux mode."""
        if not old_place or not new_place:
            return

        old_l, old_t, old_r, old_b = old_place
        new_l, new_t, new_r, new_b = new_place

        old_l = max(1, int(old_l))
        old_t = max(1, int(old_t))
        old_w = max(1, int(old_r) - int(old_l))
        old_h = max(1, int(old_b) - int(old_t))
        old_r = min(screen.cols, old_l + old_w - 1)
        old_b = min(max(1, screen.rows - 1), old_t + old_h - 1)

        new_l = max(1, int(new_l))
        new_t = max(1, int(new_t))
        new_w = max(1, int(new_r) - int(new_l))
        new_h = max(1, int(new_b) - int(new_t))
        new_r = min(screen.cols, new_l + new_w - 1)
        new_b = min(max(1, screen.rows - 1), new_t + new_h - 1)

        if old_l == new_l and old_t == new_t and old_r == new_r and old_b == new_b:
            return

        out = []
        for row in range(old_t, old_b + 1):
            if row < new_t or row > new_b:
                out.append(f"\033[{row};{old_l}f".encode("ascii"))
                out.append(b" " * max(1, old_r - old_l + 1))
                continue

            if old_l < new_l:
                left_len = new_l - old_l
                if left_len > 0:
                    out.append(f"\033[{row};{old_l}f".encode("ascii"))
                    out.append(b" " * left_len)
            if old_r > new_r:
                right_start = new_r + 1
                right_len = old_r - new_r
                if right_len > 0 and right_start <= screen.cols:
                    out.append(f"\033[{row};{right_start}f".encode("ascii"))
                    out.append(b" " * right_len)

        if out:
            sys.stdout.buffer.write(b"".join(out))

    def _upload_png(
        self,
        image_id: int,
        png_data: bytes,
        width_cells: int,
        height_cells: int,
        use_unicode_placeholders: bool,
    ) -> None:
        b64 = standard_b64encode(png_data)
        first_chunk = True
        packets = []
        while b64:
            chunk, b64 = b64[: self._MAX_CHUNK], b64[self._MAX_CHUNK :]
            if first_chunk:
                cmd = {"a": "T", "i": image_id, "q": 2, "f": 100, "m": 1 if b64 else 0}
                if use_unicode_placeholders:
                    cmd["U"] = 1
                    cmd["c"] = width_cells
                    cmd["r"] = height_cells
                first_chunk = False
            else:
                cmd = {"q": 2, "m": 1 if b64 else 0}
            packets.append(self._serialize_gr_command(cmd, chunk))
        if packets:
            sys.stdout.buffer.write(b"".join(packets))

    def _diacritic(self, value: int) -> str:
        if 0 <= value < len(self._ROWCOL_DIACRITICS):
            return chr(self._ROWCOL_DIACRITICS[value])
        return ""

    def _tmux_placeholder_tile(self, row: int, col: int, msb: int) -> str:
        return (
            self._PLACEHOLDER
            + self._diacritic(row)
            + self._diacritic(col)
            + (self._diacritic(msb) if msb else "")
        )

    def _append_cols_debug_line(self, payload: dict[str, Any]) -> None:
        """Append non-tmux native renderer diagnostics to cols.txt."""
        if self.in_tmux or self.protocol != "kitty":
            return
        try:
            now = datetime.now().isoformat(timespec="milliseconds")
            parts = [f"{k}={v}" for k, v in payload.items()]
            with Path("cols.txt").open("a", encoding="utf-8") as debug_file:
                debug_file.write(f"{now} {' '.join(parts)}\n")
        except Exception:
            return

    def _emit_tmux_placeholders(
        self, image_id: int, indent_cols: int, rows: int, cols: int
    ) -> None:
        r = (image_id >> 16) & 0xFF
        g = (image_id >> 8) & 0xFF
        b = image_id & 0xFF
        msb = (image_id >> 24) & 0xFF

        out = []
        for row in range(rows):
            line = "\r"
            if indent_cols > 0:
                line += f"\033[{indent_cols}C"
            line += f"\033[38:2:{r}:{g}:{b}m"
            for col in range(cols):
                line += self._tmux_placeholder_tile(row, col, msb)
            line += "\033[39m\n\r"
            out.append(line)
        # IMPORTANT: write placeholders through the binary stream to avoid
        # text/binary buffering reordering that breaks kitty escape handling.
        sys.stdout.buffer.write("".join(out).encode("utf-8"))

    def _maybe_clear_tmux_history(self, force: bool = False) -> None:
        if not self.in_tmux:
            return
        now = monotonic()
        if (
            not force
            and (now - self._last_tmux_history_clear)
            < self._tmux_history_clear_interval
        ):
            return
        self._last_tmux_history_clear = now
        try:
            subprocess.run(
                ["tmux", "clear-history"], check=False, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    def render_pixmap(
        self,
        pixmap: Any,
        page_num: int,
        placement: tuple[int, int, int, int],
        screen: Any,
        page_state: Any | None = None,
    ) -> bool:
        """Render a pixmap using native Kitty protocol."""
        l_col, t_row, r_col, b_row = placement
        width_cells = max(1, r_col - l_col)
        height_cells = max(1, b_row - t_row)

        status_rows = 1 if _show_status_bar() else 0
        max_bottom_row = screen.rows - status_rows
        # Placement uses [top, bottom) in 1-based terminal rows.
        max_exclusive_bottom = max_bottom_row + 1
        if b_row > max_exclusive_bottom:
            height_cells = max(1, max_bottom_row - t_row + 1)
        # Keep placeholders strictly for tmux+kitty path.
        use_unicode_placeholders = self.in_tmux and self.protocol == "kitty-tmux"

        # Cache PNG payload for this page state.
        if page_state and callable(getattr(page_state, "get_cached_ppm", None)):
            png_data = page_state.get_cached_ppm()
        elif page_state:
            png_data = page_state.cached_ppm
        else:
            png_data = None

        if png_data is None:
            png_data = pixmap.tobytes("png")
            if page_state and callable(getattr(page_state, "set_cached_ppm", None)):
                page_state.set_cached_ppm(png_data)
            elif page_state:
                page_state.cached_ppm = png_data

        # Positioning: tmux path uses placeholder indent; native path uses cursor.
        if self.in_tmux and self.protocol == "kitty-tmux":
            # Placeholder rendering emits newline-delimited rows, which can grow tmux
            # scrollback quickly during autoplay loops and cause visual instability.
            # Periodically clear history to keep rendering stable over time.
            self._maybe_clear_tmux_history(force=False)
            screen.set_cursor(1, t_row)
            indent_cols = max(0, l_col - 1)
        elif use_unicode_placeholders:
            screen.set_cursor(1, t_row)
            indent_cols = max(0, l_col - 1)
        else:
            screen.set_cursor(l_col, t_row)
            indent_cols = 0

        self._append_cols_debug_line(
            {
                "kind": "render",
                "page": page_num + 1,
                "protocol": self.protocol,
                "in_tmux": self.in_tmux,
                "l_col": l_col,
                "t_row": t_row,
                "r_col": r_col,
                "b_row": b_row,
                "width_cells": width_cells,
                "height_cells": height_cells,
                "use_placeholders": use_unicode_placeholders,
                "direct_upload_only": not use_unicode_placeholders,
                "screen_cols": screen.cols,
                "screen_rows": screen.rows,
                "pix_w_px": getattr(pixmap, "width", None),
                "pix_h_px": getattr(pixmap, "height", None),
            }
        )

        image_id = self._next_image_id()
        old_global_image_id = self._last_displayed_image_id
        if page_state and callable(getattr(page_state, "get_last_image", None)):
            old_image_id, old_place = page_state.get_last_image()
        else:
            old_image_id = page_state.last_image_id if page_state else None
            old_place = page_state.last_place if page_state else None

        try:
            self._upload_png(
                image_id,
                png_data,
                width_cells,
                height_cells,
                use_unicode_placeholders=use_unicode_placeholders,
            )
            if use_unicode_placeholders:
                self._emit_tmux_placeholders(
                    image_id, indent_cols, height_cells, width_cells
                )
            else:
                # Direct kitty mode: display-at-cursor via a=T upload command
                # (no separate a=p place command), matching external timg behavior.
                if old_global_image_id is not None and old_global_image_id != image_id:
                    self._delete_image(old_global_image_id)
                self._last_displayed_image_id = image_id
            if old_image_id is not None and old_image_id != image_id:
                self._delete_image(old_image_id)
            if self.in_tmux and self.protocol == "kitty-tmux" and old_place:
                self._clear_tmux_stale_placeholder_margins(old_place, placement, screen)
            if page_state and callable(getattr(page_state, "set_last_image", None)):
                page_state.set_last_image(image_id, placement)
            elif page_state:
                page_state.last_image_id = image_id
                page_state.last_place = placement
            success = True
        except Exception as e:
            logging.warning(f"native kitty renderer failed: {e}")
            success = False

        # Keep cursor at a safe row and hidden.
        screen.set_cursor(1, screen.rows)
        sys.stdout.buffer.write(b"\033[?25l")
        sys.stdout.flush()
        return success

    def clear_image(self, page_num: int) -> None:
        """Clear previously rendered images and reset screen."""
        self._maybe_clear_tmux_history(force=False)

        self._write_gr_cmd({"a": "d", "d": "a"})
        self._last_displayed_image_id = None
        sys.stdout.buffer.write(b"\033[2J")
        sys.stdout.buffer.write(b"\033[H")
        sys.stdout.buffer.write(b"\033[?25l")
        sys.stdout.flush()

    def cleanup(self) -> None:
        """Cleanup resources."""
        pass


def create_renderer(config: Any = None) -> RenderingEngine:
    """Factory to create renderer based on config and availability"""

    # Priority order: native kitty renderer > legacy kitty renderer
    renderers_to_try = [
        ("native", NativeRenderer),
        ("kitty", KittyRenderer),
    ]

    for name, renderer_class in renderers_to_try:
        try:
            renderer = renderer_class()
            if renderer.detect_support():
                logging.info(f"Using renderer: {name}")
                return renderer
        except RendererUnavailableError as e:
            logging.debug(f"Renderer {name} unavailable: {e}")
            continue
        except Exception as e:
            logging.warning(f"Error checking renderer {name}: {e}")
            continue

    # Hard requirement: exit if no renderer available
    raise SystemExit(
        "No graphics renderer available.\n"
        "Use a Kitty-compatible terminal (kitty, tmux+kitty, or wezterm)."
    )
