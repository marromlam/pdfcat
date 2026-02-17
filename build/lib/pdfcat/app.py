"""pdfcat CLI and viewer loop."""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from time import sleep
from typing import Any, NoReturn, Sequence

import fitz

from .actions import SetAutoplayEndAction, ToggleAutoplayAction
from .bib import citekey_from_path, path_from_citekey
from .constants import (
    USAGE,
    VIEWER_SHORTCUTS,
    __author__,
    __copyright__,
    __license__,
    __url__,
    __version__,
)
from .context import ViewerContext
from .core import Buffers, Config, Screen, get_cachefile
from .document import Document
from .exceptions import NeovimBridgeError
from .executor import ActionExecutor
from .input_handler import InputHandler
from .renderers import create_renderer
from .runtime_context import get_context, set_context
from .security import sanitize_command_args, sanitize_file_path
from .ui import run_visual_mode, shortcuts, status_bar
from .workers import WorkerPool

_ctx: ViewerContext | None = None


def print_cli_version() -> NoReturn:
    print(__version__)
    print(__license__, "License")
    print(__copyright__, __author__)
    print(__url__)
    raise SystemExit


def print_cli_help() -> NoReturn:
    print(USAGE.rstrip())
    print()
    print(VIEWER_SHORTCUTS)
    raise SystemExit()


def parse_cli_args(args: Sequence[str]) -> tuple[list[str], dict[str, Any]]:
    args_list = list(args)
    files: list[str] = []
    opts: dict[str, Any] = {
        "ignore_cache": False,
        "force_tinted": False,
        "force_original": False,
        "hide_status_bar": False,
    }
    if len(args_list) == 1:
        args_list = args_list + ["-h"]

    args_list = args_list[1:]

    if len({"-h", "--help"} & set(args_list)) != 0:
        print_cli_help()
    elif len({"-v", "--version"} & set(args_list)) != 0:
        print_cli_version()

    skip = False
    for i, arg in enumerate(args_list):
        if skip:
            skip = not skip
        elif arg in {"-p", "--page-number"}:
            try:
                page_number = int(args_list[i + 1])
                if page_number < 1:
                    raise ValueError
                opts["cli_page_number"] = page_number
                skip = True
            except (IndexError, ValueError):
                raise SystemExit("No valid page number specified")
        elif arg in {"-f", "--first-page"}:
            try:
                opts["first_page_offset"] = int(args_list[i + 1])
                skip = True
            except (IndexError, ValueError):
                raise SystemExit("No valid first page specified")
        elif arg in {"--nvim-listen-address"}:
            try:
                opts["nvim_listen_address"] = args_list[i + 1]
                skip = True
            except IndexError:
                raise SystemExit("No address specified")
        elif arg in {"--citekey"}:
            try:
                opts["citekey"] = args_list[i + 1]
                skip = True
            except IndexError:
                raise SystemExit("No citekey specified")
        elif arg in {"-o", "--open"}:
            try:
                citekey = args_list[i + 1]
            except IndexError:
                raise SystemExit("No citekey specified")
            opts["citekey"] = citekey
            path = path_from_citekey(citekey)
            if path:
                if path[-5:] == ".html":
                    config = _config()
                    browser = str(getattr(config, "URL_BROWSER", ""))
                    if browser == "":
                        raise SystemExit("No URL browser configured")
                    subprocess.run([browser, path], check=True)
                    print("Opening html file in browser")
                elif path[-5:] == ".docx":
                    # TODO: support for docx files
                    raise SystemExit("Cannot open " + path)
                else:
                    files += [path]
            else:
                raise SystemExit("No file for " + citekey)
            skip = True
        elif arg in {"--ignore-cache"}:
            opts["ignore_cache"] = True
        elif arg in {"--force-tinted"}:
            opts["force_tinted"] = True
            opts["force_original"] = False
        elif arg in {"--force-original"}:
            opts["force_original"] = True
            opts["force_tinted"] = False
        elif arg in {"--hide-status-bar"}:
            opts["hide_status_bar"] = True
        elif os.path.isfile(arg):
            files = files + [arg]
        elif os.path.isfile(arg.strip('"')):
            files = files + [arg.strip('"')]
        elif os.path.isfile(arg.strip("'")):
            files = files + [arg.strip("'")]
        elif re.match("^-", arg):
            raise SystemExit("Unknown option: " + arg)
        else:
            raise SystemExit("Can't open file: " + arg)

    if len(files) == 0:
        raise SystemExit("No file to open")

    return files, opts


def _get_ctx() -> ViewerContext | None:
    ctx = get_context()
    if isinstance(ctx, ViewerContext):
        return ctx
    return _ctx


def _config() -> Any:
    ctx = _get_ctx()
    if ctx is not None:
        return ctx.config
    return None


def _buffers() -> Any:
    ctx = _get_ctx()
    if ctx is not None:
        return ctx.buffers
    return None


def _screen() -> Any:
    ctx = _get_ctx()
    if ctx is not None:
        return ctx.screen
    return None


def _renderer() -> Any:
    ctx = _get_ctx()
    if ctx is not None:
        return getattr(ctx, "renderer", None)
    return None


def _shutdown_event() -> Any:
    ctx = _get_ctx()
    if ctx is not None:
        return ctx.shutdown_event
    return None


def apply_forced_visual_mode(doc: Document) -> None:
    if getattr(doc, "force_original", False):
        doc.alpha = False
        doc.invert = False
        doc.tint = False
    elif getattr(doc, "force_tinted", False):
        doc.alpha = True
        doc.invert = True
        doc.tint = True


def apply_cached_state(
    doc: Document, cached_state: dict[str, Any], ignore_visual_state: bool = False
) -> None:
    for key, value in cached_state.items():
        if ignore_visual_state and key in {"alpha", "invert", "tint"}:
            continue
        setattr(doc, key, value)


def clean_exit(message: str = "") -> NoReturn:
    screen = _screen()
    buffers = _buffers()
    renderer = _renderer()
    shutdown_event = _shutdown_event()

    # Signal all threads to shutdown
    if shutdown_event is not None:
        shutdown_event.set()
    ctx = _get_ctx()

    # Deactivate keyboard input handler
    try:
        if screen is not None and screen.kb_input is not None:
            screen.kb_input.deactivate()
    except Exception:
        pass

    # Shut down presenter mode (if active)
    try:
        _presenter_disable(silent=True)
    except Exception:
        pass

    # Save document state and close documents
    if buffers is not None:
        for doc in buffers.docs:
            try:
                if hasattr(doc, "stop_live_text_stream"):
                    doc.stop_live_text_stream()
                doc.write_state()
                doc.close()
            except Exception:
                pass

    # Shutdown pooled background workers.
    if ctx is not None:
        try:
            ctx.cleanup()
        except Exception:
            pass

    # Cleanup renderer for contexts not wired into cleanup yet
    if renderer:
        try:
            renderer.cleanup()
        except Exception:
            pass

    # Wait briefly for background threads (file watcher) to finish
    # These are daemon threads and don't touch stdin, so they're safe
    active_threads = getattr(ctx, "active_threads", None) if ctx is not None else []
    if active_threads is None:
        active_threads = []
    for thread in active_threads:
        if thread.is_alive():
            try:
                thread.join(timeout=0.2)
            except Exception:
                pass

    # Clear screen and show cursor
    if screen and screen.console:
        screen.console.clear()

    # Print exit message if any
    if message:
        print(message)

    raise SystemExit()


def watch_file_changes(file_change: threading.Event, path: str) -> None:
    timestamp = os.path.getmtime(path)
    shutdown_event = _shutdown_event()
    while shutdown_event is None or not shutdown_event.is_set():
        sleep(0.5)
        try:
            nts = os.path.getmtime(path)
            if nts != timestamp:
                timestamp = nts
                logging.debug("file changed")
                file_change.set()
        except OSError:
            # File might be deleted or inaccessible
            break


def run_reverse_synctex_to_neovim(doc: Document, bar: status_bar) -> None:
    page = int(getattr(doc, "page", 0)) + 1
    synctex_target = f"{page}:1:1:{doc.filename}"

    try:
        proc = subprocess.run(
            ["synctex", "edit", "-o", synctex_target],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        bar.message = "synctex not found"
        return

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    input_path = None
    line_no = None
    col_no = 1

    for raw in output.splitlines():
        if raw.startswith("Input:"):
            input_path = raw[len("Input:") :].strip()
        elif raw.startswith("Line:"):
            try:
                line_no = int(raw[len("Line:") :].strip())
            except ValueError:
                line_no = None
        elif raw.startswith("Column:"):
            try:
                col_no = int(raw[len("Column:") :].strip())
            except ValueError:
                col_no = 1

    if not input_path or line_no is None:
        bar.message = "SyncTeX mapping not found"
        return

    if not os.path.isabs(input_path):
        input_path = os.path.abspath(os.path.join(os.path.dirname(doc.filename), input_path))

    if not os.path.exists(input_path):
        bar.message = "SyncTeX target file not found"
        return

    line_no = max(1, line_no)
    col_no = max(1, col_no)

    try:
        doc.init_neovim_bridge()
    except NeovimBridgeError as e:
        logging.warning(f"Neovim bridge initialization failed: {e}")
        bar.message = "Neovim bridge unavailable"
        return
    except Exception as e:
        logging.error(f"Unexpected error in Neovim bridge: {e}")
        bar.message = "Neovim bridge error"
        return

    if not doc.nvim:
        bar.message = "Neovim bridge unavailable"
        return

    try:
        escaped = doc.nvim.funcs.fnameescape(input_path)
        doc.nvim.command("drop " + escaped)
        doc.nvim.funcs.cursor(line_no, col_no)
        doc.nvim.command("normal! zz")
        bar.message = f"{os.path.basename(input_path)}:{line_no}"
    except Exception as e:
        logging.error("Failed reverse SyncTeX jump: %s", e)
        bar.message = "Failed to jump in Neovim"


def open_external_pdf_viewer(doc: Document) -> str | None:
    """Open current document in external system viewer.

    If GUI_VIEWER is configured to a command, use it. Otherwise, use the
    platform default opener.
    """
    config = _config()
    viewer = str(getattr(config, "GUI_VIEWER", "") or "").strip()

    try:
        safe_path = sanitize_file_path(doc.filename)
        if safe_path is None:
            return f"Invalid or missing file: {doc.filename}"
        filename = str(safe_path)

        if viewer and viewer.lower() not in {"system", "default"}:
            try:
                cmd = sanitize_command_args(viewer)
                subprocess.run(
                    cmd + [filename],
                    check=False,
                    shell=False,
                    timeout=10,
                )
                return None
            except ValueError as e:
                logging.error(f"Invalid viewer command: {e}")
                return f"Invalid viewer configuration: {e}"
            except subprocess.TimeoutExpired:
                logging.warning(f"Viewer command timed out: {viewer}")
                return "Viewer failed to start (timeout)"

        if sys.platform == "darwin":
            subprocess.run(
                ["open", filename],
                check=False,
                shell=False,
                timeout=10,
            )
            return None

        if os.name == "nt":
            startfile = getattr(os, "startfile", None)
            if callable(startfile):
                startfile(filename)
                return None

        opener = shutil.which("xdg-open")
        if opener is None:
            return "No system PDF opener found (missing xdg-open)"
        subprocess.run(
            [opener, filename],
            check=False,
            shell=False,
            timeout=10,
        )
        return None
    except Exception as e:
        logging.exception("Failed to open external viewer")
        return f"Failed to open external viewer: {e}"


def _presenter_default_state() -> dict[str, Any]:
    return {
        "session": "",
        "window": "",
        "pane": "",
        "filename": "",
        "page": None,
        "last_check": 0.0,
        "control_file": "",
    }


presenter_state = _presenter_default_state()


def _presenter_reset_state() -> None:
    presenter_state.update(_presenter_default_state())


def _tmux_send_command(pane_id: str, cmd: str) -> bool:
    if not pane_id:
        return False
    r1 = subprocess.run(["tmux", "send-keys", "-t", pane_id, "C-c"], check=False)
    r2 = subprocess.run(["tmux", "send-keys", "-t", pane_id, "-l", cmd], check=False)
    r3 = subprocess.run(["tmux", "send-keys", "-t", pane_id, "C-m"], check=False)
    return (r1.returncode == 0) and (r2.returncode == 0) and (r3.returncode == 0)


def _tmux_pane_running_pdfcat(pane_id: str) -> bool:
    if not pane_id:
        return False
    probe = subprocess.run(
        ["tmux", "display-message", "-p", "-t", pane_id, "#{pane_current_command}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return False
    cmd = (probe.stdout or "").strip().lower()
    # pdfcat runs as python via console entrypoint in this setup
    return cmd.startswith("python") or (cmd == "pdfcat")


def _build_pdfcat_command(
    doc: Document,
    page_1based: int,
    control_file: str | None = None,
    force_original: bool = False,
    hide_status_bar: bool = False,
) -> str:
    exe = shutil.which("pdfcat")
    if exe is not None:
        argv = [exe]
    else:
        argv = [sys.executable, "-m", "pdfcat"]

    argv.extend(["--ignore-cache", "-p", str(max(1, int(page_1based)))])
    if force_original:
        argv.append("--force-original")
    elif bool(getattr(doc, "force_tinted", False)):
        argv.append("--force-tinted")
    if hide_status_bar:
        argv.append("--hide-status-bar")
    argv.append(doc.filename)

    if control_file:
        env_prefix = ["env", f"PDFCAT_CONTROL_FILE={control_file}"]
        argv = env_prefix + argv

    return " ".join(shlex.quote(str(x)) for x in argv)


_control_sync_state = {"path": "", "last_raw": "", "fallback_path": ""}


def _same_file_path(a: str, b: str) -> bool:
    try:
        if os.path.realpath(str(a)) == os.path.realpath(str(b)):
            return True
    except Exception:
        pass
    try:
        return os.path.samefile(str(a), str(b))
    except Exception:
        return False


def _presenter_control_file_for_session(session_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(session_name or "presenter"))
    return os.path.join("/tmp", f"pdfcat_{safe}.control.json")


def _write_presenter_control_command(
    control_file: str | None, doc: Document, page_1based: int
) -> bool:
    if not control_file:
        return False
    payload = {
        "filename": os.path.abspath(doc.filename),
        "page": int(max(1, page_1based)),
    }
    tmp = control_file + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
            f.write("\n")
        os.replace(tmp, control_file)
        return True
    except Exception:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass
        return False


def _poll_external_page_command(doc: Document) -> None:
    path = os.environ.get("PDFCAT_CONTROL_FILE", "").strip()

    # Fallback: if env var is missing, derive control file from tmux session.
    if not path and os.environ.get("TMUX"):
        cached = str(_control_sync_state.get("fallback_path") or "")
        if cached:
            path = cached
        else:
            probe = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                check=False,
            )
            if probe.returncode == 0:
                session_name = (probe.stdout or "").strip()
                if session_name.startswith("pdfcat_presenter_"):
                    path = _presenter_control_file_for_session(session_name)
                    _control_sync_state["fallback_path"] = path

    if not path:
        return None

    if _control_sync_state.get("path") != path:
        _control_sync_state["path"] = path
        _control_sync_state["last_raw"] = ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
    except FileNotFoundError:
        return None
    except Exception:
        return None

    if not raw:
        return None
    if raw == _control_sync_state.get("last_raw"):
        return None

    _control_sync_state["last_raw"] = raw

    try:
        payload = json.loads(raw)
    except Exception:
        return None

    target_file = os.path.abspath(str(payload.get("filename") or doc.filename))
    if not _same_file_path(target_file, doc.filename):
        return None

    try:
        target_page = int(payload.get("page"))
    except Exception:
        return None

    target_page = max(1, target_page)
    if int(doc.page) + 1 != target_page:
        doc.goto_page(target_page - 1)

    return None


def _presenter_disable(silent: bool = False) -> str | None:
    session = str(presenter_state.get("session") or "")
    control_file = str(presenter_state.get("control_file") or "")
    if session:
        subprocess.run(["tmux", "kill-session", "-t", session], check=False)
    if control_file:
        try:
            if os.path.exists(control_file):
                os.unlink(control_file)
        except Exception:
            pass
    _presenter_reset_state()
    if silent:
        return None
    return "presenter mode disabled"


def _presenter_enable(doc: Document) -> str:
    if not os.environ.get("TMUX"):
        return "presenter mode requires tmux"

    tmux_bin = shutil.which("tmux")
    if tmux_bin is None:
        return "tmux not found in PATH"

    kitty_bin = shutil.which("kitty")
    if kitty_bin is None:
        return "kitty not found in PATH"

    session_name = f"pdfcat_presenter_{os.getpid()}_{int(time.time())}"
    create = subprocess.run(
        [
            tmux_bin,
            "new-session",
            "-d",
            "-P",
            "-F",
            "#{session_name} #{window_id} #{pane_id}",
            "-s",
            session_name,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if create.returncode != 0:
        return "failed to create presenter session"

    fields = (create.stdout or "").strip().split()
    if len(fields) < 3:
        return "failed to initialize presenter session"

    session, window_id, pane_id = fields[0], fields[1], fields[2]
    subprocess.run([tmux_bin, "set-option", "-t", session, "status", "off"], check=False)

    control_file = _presenter_control_file_for_session(session)
    cmd = _build_pdfcat_command(
        doc,
        doc.page + 1,
        control_file=control_file,
        force_original=True,
        hide_status_bar=True,
    )
    if not _tmux_send_command(pane_id, cmd):
        subprocess.run([tmux_bin, "kill-session", "-t", session], check=False)
        return "failed to start presenter viewer"

    attach_cmd = f"{shlex.quote(tmux_bin)} attach-session -t {shlex.quote(session)}"
    launch = subprocess.run(
        [
            kitty_bin,
            "--single-instance",
            "--instance-group=1",
            "sh",
            "-lc",
            attach_cmd,
        ],
        check=False,
    )
    if launch.returncode != 0:
        subprocess.run([tmux_bin, "kill-session", "-t", session], check=False)
        return "failed to open presenter window"

    presenter_state.update(
        {
            "session": session,
            "window": window_id,
            "pane": pane_id,
            "filename": os.path.abspath(doc.filename),
            "page": int(doc.page) + 1,
            "last_check": time.monotonic(),
            "control_file": control_file,
        }
    )
    return "presenter mode enabled"


def toggle_presenter_mode(doc: Document) -> str | None:
    if presenter_state.get("session"):
        return _presenter_disable(silent=False)
    return _presenter_enable(doc)


def sync_presenter_mode(doc: Document) -> str | None:
    session = str(presenter_state.get("session") or "")
    if not session:
        return None

    now = time.monotonic()
    last_check = float(presenter_state.get("last_check") or 0.0)
    if (now - last_check) >= 1.0:
        has = subprocess.run(["tmux", "has-session", "-t", session], check=False)
        presenter_state["last_check"] = now
        if has.returncode != 0:
            _presenter_reset_state()
            return "presenter mode ended"

    pane_id = str(presenter_state.get("pane") or "")
    if not pane_id:
        _presenter_reset_state()
        return "presenter mode ended"

    current_file = os.path.abspath(doc.filename)
    current_page = int(doc.page) + 1
    last_file = str(presenter_state.get("filename") or "")
    last_page = presenter_state.get("page")

    control_file = str(presenter_state.get("control_file") or "")
    if not control_file:
        control_file = _presenter_control_file_for_session(session)
        presenter_state["control_file"] = control_file
        cmd = _build_pdfcat_command(
            doc,
            current_page,
            control_file=control_file,
            force_original=True,
            hide_status_bar=True,
        )
        started = _tmux_send_command(pane_id, cmd)
        if not started:
            _presenter_reset_state()
            return "presenter mode ended"
        presenter_state["filename"] = current_file
        presenter_state["page"] = current_page
        return None

    if not _tmux_pane_running_pdfcat(pane_id):
        cmd = _build_pdfcat_command(
            doc,
            current_page,
            control_file=control_file,
            force_original=True,
            hide_status_bar=True,
        )
        started = _tmux_send_command(pane_id, cmd)
        if not started:
            _presenter_reset_state()
            return "presenter mode ended"
        presenter_state["filename"] = current_file
        presenter_state["page"] = current_page
        return None

    if last_file != current_file:
        cmd = _build_pdfcat_command(
            doc,
            current_page,
            control_file=control_file,
            force_original=True,
            hide_status_bar=True,
        )
        started = _tmux_send_command(pane_id, cmd)
        if not started:
            _presenter_reset_state()
            return "presenter mode ended"
        presenter_state["filename"] = current_file
        presenter_state["page"] = current_page
        return None

    if last_page != current_page:
        synced = _write_presenter_control_command(control_file, doc, current_page)
        if not synced:
            cmd = _build_pdfcat_command(
                doc,
                current_page,
                control_file=control_file,
                force_original=True,
                hide_status_bar=True,
            )
            started = _tmux_send_command(pane_id, cmd)
            if not started:
                _presenter_reset_state()
                return "presenter mode ended"
        presenter_state["page"] = current_page

    return None


def _coerce_autoplay_fps(value: Any, default: float = 8.0) -> float:
    """Normalize autoplay FPS to a safe numeric range."""
    try:
        fps = float(value)
    except Exception:
        return float(default)
    if fps <= 0:
        return float(default)
    return max(0.2, min(60.0, fps))


def parse_pdfcat_anim_segments(doc: Document) -> list[dict[str, Any]]:
    """Parse pdfkeywords animation segments.

    Expected form (semicolon-separated):
    pdfcat:anim=<name>@<start>-<end>@<fps>@<loop>
    where <loop> is 1/0/true/false.
    """
    meta = getattr(doc, "metadata", None) or {}
    keywords = str(meta.get("keywords", "") or "")
    if not keywords:
        return []

    pattern = re.compile(
        r"pdfcat:anim=([A-Za-z0-9_-]+)@(\d+)-(\d+)@([0-9]+(?:\.[0-9]+)?)@(1|0|true|false)",
        re.IGNORECASE,
    )
    segments = []
    for m in pattern.finditer(keywords):
        name = m.group(1)
        start = int(m.group(2))
        end = int(m.group(3))
        fps = float(m.group(4))
        loop_raw = m.group(5).lower()
        loop = loop_raw in {"1", "true"}
        if start < 1 or end < 1:
            continue
        if end < start:
            start, end = end, start
        # Store as 0-based page indices.
        segments.append(
            {
                "name": name,
                "start": start - 1,
                "end": end - 1,
                "fps": fps,
                "loop": loop,
            }
        )
    return segments


def find_anim_segment_for_page(
    segments: list[dict[str, Any]], page_idx: int
) -> dict[str, Any] | None:
    """Return the first segment containing page_idx (0-based), else None."""
    for seg in segments:
        if seg["start"] <= page_idx <= seg["end"]:
            return seg
    return None


def advance_autoplay(
    doc: Document,
    loop_enabled: bool,
    loop_start_page: int = 0,
    loop_end_page: int | None = None,
) -> tuple[bool, str | None]:
    """Advance one frame for autoplay within [start, end] inclusive."""
    start = max(0, min(int(loop_start_page), int(doc.pages)))
    if loop_end_page is None:
        end = int(doc.pages)
    else:
        end = max(0, min(int(loop_end_page), int(doc.pages)))
    if end < start:
        end = int(doc.pages)

    if doc.page < end:
        doc.next_page(1)
        return True, None
    if loop_enabled:
        doc.goto_page(start)
        return True, None
    return False, "autoplay stopped (end p{})".format(end + 1)


def _strip_ansi(text: str | None) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text or "")


def search_mode(doc: Document, bar: status_bar) -> None:
    screen = _screen()
    if screen is None:
        bar.message = "screen unavailable"
        return

    rg_bin = shutil.which("rg")
    fzf_bin = shutil.which("fzf")
    if rg_bin is None:
        bar.message = "rg not found in PATH"
        return
    if fzf_bin is None:
        bar.message = "fzf not found in PATH"
        return

    stream_path = None
    selection = ""
    try:
        stream_path = doc.start_live_text_stream()
        if not stream_path:
            bar.message = "Failed to initialize live search stream"
            return

        try:
            screen.kb_input.deactivate()
        except Exception:
            pass

        stream_q = shlex.quote(stream_path)
        rg_reload = (
            f"{shlex.quote(rg_bin)} --column --line-number --no-heading "
            "--color=always --smart-case "
            f"-- {{q}} {stream_q} | cut -d: -f3-"
        )
        cat_reload = f"cat {stream_q}"
        bind_ctrl_f = (
            "ctrl-f:unbind(change,ctrl-f)+change-prompt(2. fzf> )+enable-search+"
            f"reload({cat_reload})+clear-query+rebind(ctrl-r)"
        )
        bind_ctrl_r = (
            "ctrl-r:unbind(ctrl-r)+change-prompt(1. ripgrep> )+disable-search+"
            f"reload({rg_reload} || true)+rebind(change,ctrl-f)"
        )

        proc = subprocess.run(
            [
                fzf_bin,
                "--ansi",
                "--height=100%",
                "--disabled",
                "--prompt",
                "1. ripgrep> ",
                "--header",
                "╱ CTRL-R (ripgrep) ╱ CTRL-F (fzf) ╱ ENTER jump ╱",
                "--delimiter",
                "\t",
                "--with-nth",
                "2..",
                "--bind",
                f"start:reload:{rg_reload} || true",
                "--bind",
                f"change:reload:sleep 0.08; {rg_reload} || true",
                "--bind",
                bind_ctrl_f,
                "--bind",
                bind_ctrl_r,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            selection = (proc.stdout or "").strip()
    finally:
        if hasattr(doc, "stop_live_text_stream"):
            doc.stop_live_text_stream()
        try:
            screen.get_size()
            screen.init_terminal()
        except Exception:
            pass
        doc.mark_all_pages_stale(reset_cache=False)

    if selection == "":
        return

    chosen = _strip_ansi(selection).splitlines()[0]
    fields = chosen.split("\t", 2)
    if len(fields) < 3:
        bar.message = "Invalid search selection"
        return

    try:
        physical_page = int(fields[0])
    except Exception:
        bar.message = "Invalid page number in selection"
        return

    page_idx = min(max(0, physical_page - 1), doc.pages)
    doc.goto_page(page_idx)
    snippet = fields[2].strip()
    if len(snippet) > 80:
        snippet = snippet[:77] + "..."
    bar.message = f"match p.{fields[1]}: {snippet}"


def show_keybinds_modal(doc: Document, bar: status_bar) -> None:
    screen = _screen()
    config = _config()
    if screen is None:
        bar.message = "screen unavailable"
        return

    lines = [line.rstrip() for line in VIEWER_SHORTCUTS.strip("\n").splitlines()]
    keys = shortcuts()
    scroll = 0

    while True:
        screen.get_size()
        screen.clear()

        width = max(1, screen.cols)
        status_rows = 1 if bool(getattr(config, "SHOW_STATUS_BAR", True)) else 0
        max_rows = max(1, screen.rows - status_rows)

        header = " Keybinds - j/k scroll, h/l page, ?/Esc close "
        if len(header) > width:
            header = header[: max(1, width - 1)]
        screen.set_cursor(1, 1)
        sys.stdout.write("\033[1;37;44m" + header.ljust(width) + "\033[0m")

        content_top = 2
        visible_rows = max(1, max_rows - content_top + 1)
        max_scroll = max(0, len(lines) - visible_rows)
        scroll = min(max(0, scroll), max_scroll)

        for i in range(visible_rows):
            idx = scroll + i
            if idx >= len(lines):
                break
            row = content_top + i
            line = lines[idx]
            if len(line) > width:
                line = line[: max(1, width - 1)]
            screen.set_cursor(1, row)
            sys.stdout.write(line.ljust(width))

        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        key = screen.kb_input.getch()

        if key in keys.QUIT:
            clean_exit()
        elif key == 27 or key in keys.SHOW_HELP:
            screen.clear()
            doc.mark_all_pages_stale(reset_cache=False)
            return
        elif key in keys.NEXT_PAGE:
            scroll = min(max_scroll, scroll + 1)
        elif key in keys.PREV_PAGE:
            scroll = max(0, scroll - 1)
        elif key in keys.NEXT_CHAP:
            scroll = min(max_scroll, scroll + max(1, visible_rows // 2))
        elif key in keys.PREV_CHAP:
            scroll = max(0, scroll - max(1, visible_rows // 2))


def prerender_adjacent_pages(doc: Document, current_page: int) -> None:
    """Pre-render adjacent pages in background for instant navigation"""
    screen = _screen()
    config = _config()
    shutdown_event = _shutdown_event()
    if screen is None:
        return
    if shutdown_event is not None and shutdown_event.is_set():
        return

    # Pre-render neighboring pages (bias toward forward navigation)
    pages_to_prerender = []
    if current_page < doc.pages:
        pages_to_prerender.append(current_page + 1)
    if current_page + 1 < doc.pages:
        pages_to_prerender.append(current_page + 2)
    if current_page > 0:
        pages_to_prerender.append(current_page - 1)

    for page_num in pages_to_prerender:
        if shutdown_event is not None and shutdown_event.is_set():
            break

        page_state = doc.page_states[page_num]

        if not page_state.begin_prerender():
            continue

        try:
            # Load the page
            page = doc.load_page(page_num)

            # Apply cropping (same logic as display_page)
            if doc.manualcrop and doc.manualcroprect != [None, None] and doc.is_pdf:
                page.set_cropbox(fitz.Rect(doc.manualcroprect[0], doc.manualcroprect[1]))
            elif doc.autocrop and doc.is_pdf:
                page.set_cropbox(page.mediabox)
                crop = doc.auto_crop(page)
                page.set_cropbox(crop)
            elif doc.is_pdf:
                page.set_cropbox(page.mediabox)

            # Calculate factor (same as display_page)
            dw = screen.width
            status_rows = 1 if bool(getattr(config, "SHOW_STATUS_BAR", True)) else 0
            dh = screen.height - (screen.cell_height * status_rows)

            if doc.rotation in [0, 180]:
                pw = page.bound().width
                ph = page.bound().height
            else:
                pw = page.bound().height
                ph = page.bound().width

            fx = dw / pw
            fy = dh / ph
            factor = min(fx, fy)

            # Generate pixmap
            mat = fitz.Matrix(factor, factor)
            mat = mat.prerotate(doc.rotation)

            render_cache = getattr(doc, "_render_cache", None)
            if render_cache is None:
                continue

            entry = render_cache.get(page_num)
            if entry and entry.matrix == mat:
                page_state.set_cached_render(entry.pixmap, entry.matrix)
                page_state.set_cached_ppm(entry.ppm)
                continue

            pix = page.get_pixmap(matrix=mat, alpha=doc.alpha)
            ppm = pix.tobytes("png")
            render_cache.put(page_num, pix, mat, ppm)
            if callable(getattr(doc, "_prune_page_state_caches", None)):
                doc._prune_page_state_caches()
            page_state.set_cached_render(pix, mat)
            page_state.set_cached_ppm(ppm)
            page_state.set_cached_visual_key(None)
            logging.debug(f"Pre-rendered page {page_num}")

        except Exception as e:
            logging.debug(f"Pre-render failed for page {page_num}: {e}")
        finally:
            page_state.end_prerender()


def soft_reload_document(doc: Document) -> Document:
    """Reload PDF content without terminal reinitialization to minimize blink."""
    try:
        new_doc = Document(doc.filename, ctx=_get_ctx())
    except Exception as e:
        logging.warning(f"soft reload failed: {e}")
        return doc

    preserve_attrs = (
        "citekey",
        "papersize",
        "logicalpage",
        "first_page_offset",
        "chapter",
        "rotation",
        "autocrop",
        "manualcrop",
        "manualcroprect",
        "alpha",
        "invert",
        "tint",
        "tint_color",
        "force_tinted",
        "force_original",
        "nvim",
        "nvim_listen_address",
    )
    for attr in preserve_attrs:
        if hasattr(doc, attr):
            setattr(new_doc, attr, getattr(doc, attr))
    apply_forced_visual_mode(new_doc)

    new_doc.build_logical_pages()
    new_doc.goto_logical_page(new_doc.logicalpage)
    new_doc.set_layout(new_doc.papersize, adjustpage=False)
    new_doc.mark_all_pages_stale()

    try:
        doc.close()
    except Exception:
        pass

    buffers = _buffers()
    if buffers is not None:
        buffers.docs[buffers.current] = new_doc
    return new_doc


def refresh_current_document(current_doc: Document) -> Document:
    """Re-open the active document while preserving user-visible settings."""
    screen = _screen()
    buffers = _buffers()
    if screen is not None:
        screen.clear()
        screen.get_size()
        screen.init_terminal()

    current_doc.write_state()
    doc = Document(current_doc.filename, ctx=_get_ctx())
    cachefile = get_cachefile(doc.filename)
    if os.path.exists(cachefile):
        with open(cachefile, "r") as f:
            cached_state = json.load(f)
        apply_cached_state(
            doc,
            cached_state,
            ignore_visual_state=bool(
                getattr(current_doc, "force_tinted", False)
                or getattr(current_doc, "force_original", False)
            ),
        )
    doc.force_tinted = getattr(current_doc, "force_tinted", False)
    doc.force_original = getattr(current_doc, "force_original", False)
    apply_forced_visual_mode(doc)
    if buffers is not None:
        buffers.docs[buffers.current] = doc
    if not doc.citekey:
        inferred_citekey = citekey_from_path(doc.filename)
        if inferred_citekey:
            doc.citekey = inferred_citekey
    doc.build_logical_pages()
    doc.goto_logical_page(doc.logicalpage)
    doc.set_layout(doc.papersize, adjustpage=False)
    return doc


def view(file_change: threading.Event, doc: Document) -> None:
    screen = _screen()
    config = _config()
    buffers = _buffers()
    if screen is None or config is None or buffers is None:
        clean_exit("viewer context not initialized")

    screen.get_size()
    screen.init_terminal()

    # Initialize renderer (will exit if none available)
    try:
        renderer = create_renderer()
        ctx = _get_ctx()
        if ctx is not None:
            ctx.renderer = renderer
            set_context(ctx)
    except SystemExit as e:
        clean_exit(str(e))

    screen.drain_input()

    bar = status_bar()
    if doc.citekey:
        bar.message = doc.citekey

    input_handler = InputHandler()
    keys = input_handler.keys
    executor = ActionExecutor(
        clean_exit_fn=lambda: clean_exit(),
        refresh_doc_fn=refresh_current_document,
        reverse_synctex_fn=run_reverse_synctex_to_neovim,
        toggle_presenter_fn=toggle_presenter_mode,
        show_help_fn=show_keybinds_modal,
        open_external_viewer_fn=open_external_pdf_viewer,
        search_mode_fn=search_mode,
        run_visual_mode_fn=run_visual_mode,
        buffers=buffers,
    )

    autoplay_on = False
    autoplay_fps = _coerce_autoplay_fps(getattr(config, "AUTOPLAY_FPS", 8), 8.0)
    autoplay_loop_enabled = bool(getattr(config, "AUTOPLAY_LOOP", True))
    autoplay_interval = 1.0 / autoplay_fps
    autoplay_next_tick = time.monotonic() + autoplay_interval
    autoplay_loop_start_page = doc.page
    autoplay_end_page = doc.pages
    configured_end = getattr(config, "AUTOPLAY_END_PAGE", None)
    if configured_end is not None:
        try:
            conf = int(configured_end)
            if conf > 0:
                autoplay_end_page = max(0, min(doc.pages, conf - 1))
        except Exception:
            pass

    while True:
        bar.cmd = input_handler.get_command_string()
        # Status bar updated inside display_page, no need to update here
        doc.display_page(bar, doc.page, display=False)

        _poll_external_page_command(doc)

        presenter_msg = sync_presenter_mode(doc)
        if presenter_msg:
            bar.message = presenter_msg

        key = screen.kb_input.getch(timeout=0.01)
        while key == -1 and not file_change.is_set():
            # Keep processing external page commands while idle (presenter/control-file sync).
            prev_page = int(doc.page)
            _poll_external_page_command(doc)
            if int(doc.page) != prev_page:
                break
            if autoplay_on and time.monotonic() >= autoplay_next_tick:
                break
            key = screen.kb_input.getch(timeout=0.01)

        if file_change.is_set():
            logging.debug("view thread sees that file has changed")
            file_change.clear()
            doc = soft_reload_document(doc)
            continue

        if key != -1 and autoplay_on and key not in keys.TOGGLE_AUTOPLAY:
            autoplay_on = False

        if key == -1:
            if autoplay_on and time.monotonic() >= autoplay_next_tick:
                advanced, message = advance_autoplay(
                    doc,
                    autoplay_loop_enabled,
                    loop_start_page=autoplay_loop_start_page,
                    loop_end_page=autoplay_end_page,
                )
                autoplay_next_tick = time.monotonic() + autoplay_interval
                if not advanced:
                    autoplay_on = False
                    if message:
                        bar.message = message
            continue

        action = input_handler.handle_key(key, doc)

        if isinstance(action, ToggleAutoplayAction):
            if action.count_string != "":
                autoplay_fps = _coerce_autoplay_fps(action.count, autoplay_fps)
                autoplay_loop_enabled = bool(getattr(config, "AUTOPLAY_LOOP", True))

            autoplay_interval = 1.0 / autoplay_fps
            if autoplay_on:
                autoplay_on = False
                bar.message = "autoplay paused"
                continue

            segments = parse_pdfcat_anim_segments(doc)
            seg = find_anim_segment_for_page(segments, doc.page)
            autoplay_on = True
            if seg is not None:
                autoplay_loop_start_page = max(0, min(doc.pages, int(seg["start"])))
                autoplay_end_page = max(0, min(doc.pages, int(seg["end"])))
                autoplay_fps = _coerce_autoplay_fps(seg.get("fps"), autoplay_fps)
                autoplay_loop_enabled = bool(seg.get("loop", autoplay_loop_enabled))
                autoplay_interval = 1.0 / autoplay_fps
                seg_name = str(seg.get("name") or "anim")
                mode = "loop" if autoplay_loop_enabled else "once"
                bar.message = "autoplay {} {:.2f} fps (p{}->p{}, {})".format(
                    seg_name,
                    autoplay_fps,
                    autoplay_loop_start_page + 1,
                    autoplay_end_page + 1,
                    mode,
                )
                doc.goto_page(autoplay_loop_start_page)
            else:
                autoplay_loop_start_page = doc.page
                if autoplay_end_page < autoplay_loop_start_page:
                    autoplay_end_page = doc.pages
                mode = "loop" if autoplay_loop_enabled else "once"
                bar.message = "autoplay {:.2f} fps (p{}->p{}, {})".format(
                    autoplay_fps,
                    autoplay_loop_start_page + 1,
                    autoplay_end_page + 1,
                    mode,
                )
            autoplay_next_tick = time.monotonic() + autoplay_interval
            continue

        if isinstance(action, SetAutoplayEndAction):
            if action.count_string == "":
                autoplay_end_page = doc.page
            elif action.count == 0:
                autoplay_end_page = doc.pages
            else:
                if str(action.count) in [str(lp) for lp in doc.logical_pages]:
                    page_from_count = doc.logical_to_physical_page(action.count)
                else:
                    page_from_count = action.count - 1
                autoplay_end_page = max(0, min(doc.pages, int(page_from_count)))

            if autoplay_end_page == doc.pages:
                bar.message = "autoplay end: document end"
            else:
                bar.message = "autoplay end: p{}".format(autoplay_end_page + 1)
            continue

        doc = executor.execute(action, doc, bar)


# runtime singletons
_ctx = ViewerContext(
    config=Config(),
    buffers=Buffers(),
    screen=Screen(),
)
_ctx.config.load_user_config()
if not _ctx.config.URL_BROWSER:
    _ctx.config.detect_browser_command()
_ctx.worker_pool = WorkerPool(max_workers=4)
_ctx.clean_exit = clean_exit
_ctx.prerender_adjacent_pages = prerender_adjacent_pages
set_context(_ctx)


def main(args: Sequence[str] | None = None) -> None:
    config = _config()
    buffers = _buffers()
    screen = _screen()
    shutdown_event = _shutdown_event()
    ctx = _get_ctx()
    if config is None or buffers is None or screen is None:
        raise SystemExit("viewer context not initialized")

    if args is None:
        args = sys.argv

    paths, opts = parse_cli_args(args)
    if opts.get("hide_status_bar"):
        config.SHOW_STATUS_BAR = False

    if not sys.stdin.isatty():
        raise SystemExit("Not an interactive tty")

    screen.get_size()

    if screen.width == 0:
        raise SystemExit(
            "Terminal does not support reporting screen sizes via the TIOCGWINSZ ioctl"
        )

    if screen.width == 65535:
        raise SystemExit(
            "Screen size is not being reported properly.\n"
            "This problem might be caused by the fish shell."
        )

    for path in paths:
        try:
            doc = Document(path, ctx=ctx)
        except Exception:
            raise SystemExit("Unable to open " + path)

        # load saved file state
        cachefile = get_cachefile(doc.filename)
        if os.path.exists(cachefile) and not opts["ignore_cache"]:
            with open(cachefile, "r") as f:
                cached_state = json.load(f)
            apply_cached_state(
                doc,
                cached_state,
                ignore_visual_state=bool(opts.get("force_tinted") or opts.get("force_original")),
            )
        buffers.docs += [doc]

    for doc in buffers.docs:
        if not doc.citekey:
            doc.citekey = citekey_from_path(doc.filename)
        doc.force_tinted = bool(opts.get("force_tinted"))
        doc.force_original = bool(opts.get("force_original"))
        apply_forced_visual_mode(doc)

    doc = buffers.docs[buffers.current]

    # load cli settings
    for key in opts:
        if key == "cli_page_number":
            continue
        setattr(doc, key, opts[key])
    apply_forced_visual_mode(doc)

    # generate logical pages
    doc.build_logical_pages()

    # normalize page number
    if "cli_page_number" in opts:
        doc.goto_page(opts["cli_page_number"] - 1)
    else:
        doc.goto_logical_page(doc.logicalpage)

    # apply layout settings
    doc.set_layout(doc.papersize, adjustpage=False)

    # Set up signal handlers for clean shutdown
    def signal_handler(signum: int, frame: Any) -> None:
        logging.debug(f"Received signal {signum}, shutting down...")
        if shutdown_event is not None:
            shutdown_event.set()
        clean_exit("Interrupted by user")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # set up thread to watch for file changes
    file_change = threading.Event()
    file_watch = threading.Thread(
        target=watch_file_changes,
        args=(file_change, doc.filename),
        name="FileWatcher",
    )
    file_watch.daemon = True  # Daemon is OK for file watcher - it doesn't touch stdin
    file_watch.start()
    if ctx is not None:
        ctx.active_threads.append(file_watch)

    # Run view in the MAIN thread (not a separate thread)
    # This avoids all the stdin threading issues
    try:
        view(file_change, doc)
    except KeyboardInterrupt:
        logging.debug("KeyboardInterrupt in main, cleaning up...")
        if shutdown_event is not None:
            shutdown_event.set()
        clean_exit("Interrupted by user")
    except SystemExit:
        # Normal exit from view
        raise
    except Exception as e:
        logging.exception("Error in view")
        clean_exit(f"Error: {e}")


def run() -> None:
    log_file = os.path.join(os.path.expanduser("~"), ".pdfcat.log")
    try:
        logging.basicConfig(filename=log_file, level=logging.WARNING)
    except OSError:
        logging.basicConfig(level=logging.WARNING)
    try:
        main()
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        try:
            clean_exit("Interrupted by user")
        except Exception:
            sys.exit(0)
    except SystemExit:
        # Allow SystemExit to propagate
        raise
    except Exception as e:
        # Log any other exceptions
        logging.exception("Unexpected error")
        try:
            clean_exit(f"Error: {e}")
        except Exception:
            sys.exit(1)
