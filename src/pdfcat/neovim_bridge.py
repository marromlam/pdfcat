"""Neovim/text interaction helpers for documents."""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from time import monotonic, sleep
from typing import Any

from .exceptions import NeovimBridgeError
from .security import sanitize_command_args


class DocumentNeovimBridge:
    """Encapsulate text-view and Neovim bridge operations for a document."""

    @staticmethod
    def view_text(doc: Any) -> str | None:
        page = doc.load_page(doc.page)
        try:
            page_text = page.get_text("text", sort=True)
        except TypeError:
            page_text = page.get_text("text")

        page_text = (page_text or "").strip()
        if page_text == "":
            return "No selectable text on this page"

        nvim_bin = shutil.which("nvim")
        if nvim_bin is None:
            return "nvim not found in PATH"

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".txt",
                prefix="pdfcat-page-",
                delete=False,
            ) as tmp:
                tmp_path = tmp.name
                tmp.write(page_text)
                tmp.write("\n")

            subprocess.run(
                [
                    nvim_bin,
                    "--clean",
                    "-u",
                    "NONE",
                    "-n",
                    "-R",
                    "--cmd",
                    "set clipboard=unnamedplus",
                    tmp_path,
                ],
                check=False,
            )
        except Exception:
            return "Failed to open page text in Neovim"
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        screen = doc._screen() if hasattr(doc, "_screen") else None
        if screen is not None:
            screen.get_size()
            screen.init_terminal()
        doc.mark_all_pages_stale(reset_cache=False)
        return None

    @staticmethod
    def init_neovim_bridge(doc: Any) -> None:
        try:
            from pynvim import attach
        except ImportError:
            raise NeovimBridgeError("pynvim unavailable") from None
        try:
            doc.nvim = attach("socket", path=doc.nvim_listen_address)
        except Exception:
            note_path, note_err = doc._resolve_note_path()
            if note_err:
                raise NeovimBridgeError(note_err) from None
            ncmd = "env NVIM_LISTEN_ADDRESS={} nvim {}".format(
                shlex.quote(doc.nvim_listen_address), shlex.quote(note_path)
            )
            config = doc._config() if hasattr(doc, "_config") else None
            kitty_cmd = str(getattr(config, "KITTYCMD", ""))
            try:
                kitty_parts = sanitize_command_args(kitty_cmd)
                subprocess.run(
                    kitty_parts + shlex.split(ncmd),
                    check=False,
                    shell=False,
                    timeout=30,
                )
            except ValueError as e:
                logging.error(f"Invalid KITTYCMD configuration: {e}")
                raise NeovimBridgeError("Invalid KITTYCMD in config") from e
            except Exception as e:
                raise NeovimBridgeError("unable to open new kitty window") from e

            end = monotonic() + 5
            while monotonic() < end:
                try:
                    doc.nvim = attach("socket", path=doc.nvim_listen_address)
                    break
                except Exception:
                    sleep(0.1)
            if doc.nvim is None:
                raise NeovimBridgeError("timeout waiting for Neovim bridge")

    @staticmethod
    def send_to_neovim(doc: Any, text: Any, append: bool = False) -> None:
        if doc.nvim is None:
            try:
                DocumentNeovimBridge.init_neovim_bridge(doc)
            except NeovimBridgeError:
                return
            if doc.nvim is None:
                return
        try:
            doc.nvim.api.strwidth("testing")
        except Exception:
            try:
                DocumentNeovimBridge.init_neovim_bridge(doc)
            except NeovimBridgeError:
                return
        if not doc.nvim:
            return
        if append:
            line = doc.nvim.funcs.line("$")
            doc.nvim.funcs.append(line, text)
            doc.nvim.funcs.cursor(doc.nvim.funcs.line("$"), 0)
        else:
            line = doc.nvim.funcs.line(".")
            doc.nvim.funcs.append(line, text)
            doc.nvim.funcs.cursor(line + len(text), 0)
