"""Document note-management helpers."""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pyperclip

from .runtime_context import get_context


class NoteManager:
    """Encapsulate note path resolution and note editor interactions."""

    @staticmethod
    def _resolve_notes_dir(doc: Any) -> tuple[str | None, str | None]:
        cfg = doc._config() if hasattr(doc, "_config") else None
        if cfg is None:
            runtime_ctx = get_context()
            if runtime_ctx is not None:
                cfg = getattr(runtime_ctx, "config", None)
        loaded_keys = getattr(cfg, "_loaded_keys", set()) if cfg is not None else set()

        def _norm(path_value: Any) -> str:
            return os.path.expanduser(os.path.expandvars(str(path_value)))

        notes_dir = None
        if cfg is not None:
            notes_dir = getattr(cfg, "NOTES_DIR", None)
        if notes_dir:
            notes_dir = _norm(notes_dir)

        # Backward compatibility:
        # if user configured NOTE_PATH but not NOTES_DIR, derive notes directory from NOTE_PATH.
        if (
            cfg is not None
            and "NOTE_PATH" in loaded_keys
            and "NOTES_DIR" not in loaded_keys
        ):
            legacy_note_path = getattr(cfg, "NOTE_PATH", "")
            legacy_note_path = _norm(legacy_note_path)
            if legacy_note_path:
                if os.path.isdir(legacy_note_path):
                    notes_dir = legacy_note_path
                else:
                    _, ext = os.path.splitext(os.path.basename(legacy_note_path))
                    if ext:
                        notes_dir = os.path.dirname(legacy_note_path)
                    else:
                        notes_dir = legacy_note_path

        if not notes_dir:
            notes_dir = os.path.join(os.path.expanduser("~"), "notes")

        notes_dir = _norm(notes_dir)
        try:
            os.makedirs(notes_dir, exist_ok=True)
        except Exception:
            return None, "Failed to create notes directory"
        return notes_dir, None

    @staticmethod
    def _note_title(doc: Any) -> str:
        meta = doc.metadata if doc.metadata is not None else {}
        title = str(meta.get("title", "")).strip()
        if not title and doc.citekey:
            title = str(doc.citekey).strip()
        if not title and doc.filename:
            title = os.path.splitext(os.path.basename(doc.filename))[0]
        title = " ".join(title.split())
        return title or "Untitled PDF"

    @staticmethod
    def resolve_note_path(doc: Any) -> tuple[str | None, str | None]:
        resolve_dir = getattr(doc, "_resolve_notes_dir", None)
        if callable(resolve_dir):
            notes_dir, dir_err = resolve_dir()
        else:
            notes_dir, dir_err = NoteManager._resolve_notes_dir(doc)
        if dir_err:
            return None, dir_err

        resolve_title = getattr(doc, "_note_title", None)
        title = (
            resolve_title() if callable(resolve_title) else NoteManager._note_title(doc)
        )
        source = doc.filename or doc.citekey or title
        if source and os.path.exists(str(source)):
            source = os.path.abspath(str(source))
        # Late import avoids document<->notes import cycles.
        from . import document as document_module

        note_filename = document_module._build_note_filename(title, source)

        try:
            if ".." in note_filename or "/" in note_filename or "\\" in note_filename:
                logging.error(
                    "Note filename contains path separators: %s", note_filename
                )
                return None, "Invalid note filename (security violation)"

            resolved_notes_dir = Path(notes_dir).resolve()
            resolved_note_path = (resolved_notes_dir / note_filename).resolve()
            resolved_note_path.relative_to(resolved_notes_dir)
            note_path = str(resolved_note_path)
        except (OSError, ValueError) as e:
            logging.error("Path validation failed: %s", e)
            return None, "Failed to validate note path"

        try:
            needs_header = (not os.path.exists(note_path)) or os.path.getsize(
                note_path
            ) == 0
            if needs_header:
                with open(note_path, "w", encoding="utf-8") as f:
                    f.write(f"# {title}\n\n")
        except Exception as e:
            logging.error("Failed to initialize note file: %s", e)
            return None, "Failed to initialize note file"

        return note_path, None

    @staticmethod
    def append_note(doc: Any, text: Any) -> str | None:
        note_path, err = NoteManager.resolve_note_path(doc)
        if err:
            return err

        if isinstance(text, list):
            payload = "\n".join(str(t) for t in text)
        else:
            payload = str(text)

        if payload != "" and not payload.endswith("\n"):
            payload += "\n"

        try:
            with open(note_path, "a", encoding="utf-8") as f:
                f.write(payload)
        except Exception:
            return "Failed to write note"
        return None

    @staticmethod
    def send_to_notes(doc: Any, text: Any) -> str | None:
        return NoteManager.append_note(doc, text)

    @staticmethod
    def open_notes_editor(doc: Any) -> str | None:
        screen = doc._screen() if hasattr(doc, "_screen") else None
        note_path, err = NoteManager.resolve_note_path(doc)
        if err:
            return err

        nvim_bin = shutil.which("nvim")
        if nvim_bin is None:
            return "nvim not found in PATH"

        tmux_bin = shutil.which("tmux")
        in_tmux = bool(os.environ.get("TMUX"))

        proc = None
        try:
            try:
                if screen and screen.kb_input is not None:
                    screen.kb_input.deactivate()
            except Exception:
                pass

            if in_tmux and tmux_bin is not None:
                cmd = f"{shlex.quote(nvim_bin)} {shlex.quote(note_path)}"
                proc = subprocess.run(
                    [tmux_bin, "display-popup", "-E", cmd], check=False
                )
            else:
                proc = subprocess.run([nvim_bin, note_path], check=False)
        except Exception:
            return "Failed to open notes editor"
        finally:
            try:
                if screen is not None:
                    screen.get_size()
                    screen.init_terminal()
            except Exception:
                pass
            doc.mark_all_pages_stale(reset_cache=False)

        if proc is not None and proc.returncode not in (0,):
            return "Notes editor exited with errors"
        return None

    @staticmethod
    def copy_page_link_reference(doc: Any) -> str | None:
        try:
            pyperclip.copy(doc.make_link())
        except Exception:
            return "Failed to copy link reference"
        return None
