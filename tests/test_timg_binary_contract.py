#!/usr/bin/env python3
"""Best-effort binary contract test against installed timg.

This test captures stdout from both:
1) external `timg -pk` in a pseudo-terminal
2) native NativeRenderer (Python) in a pseudo-terminal

and compares protocol-level invariants.
"""

import os
import pty
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def read_pty_output(master_fd: int) -> bytes:
    chunks = []
    while True:
        try:
            data = os.read(master_fd, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks)


def run_in_pty(argv: list[str], env: dict[str, str]) -> tuple[int, bytes, bytes]:
    master_fd, slave_fd = pty.openpty()
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=slave_fd,
            stderr=subprocess.PIPE,
            env=env,
        )
        os.close(slave_fd)
        out = read_pty_output(master_fd)
        _, err = proc.communicate(timeout=20)
        return proc.returncode, out, err or b""
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass


def create_sample_png(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=220, height=120)
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(10, 10, 210, 110))
    shape.finish(color=(0, 0, 0), fill=(1, 1, 1), width=2)
    shape.commit()
    page.insert_text((70, 65), "KITTY TEST", fontsize=18)
    pix = page.get_pixmap(alpha=False)
    path.write_bytes(pix.tobytes("png"))
    doc.close()


def build_native_helper(image_path: Path) -> str:
    return f"""
import fitz, sys
sys.path.insert(0, r"{SRC}")
from pdfcat.renderers import NativeRenderer
class Screen:
    rows = 40
    cols = 140
    cell_width = 8
    cell_height = 16
    def set_cursor(self, c, r):
        sys.stdout.buffer.write(f"\\033[{{r}};{{c}}f".encode("ascii"))
        sys.stdout.flush()

pix = fitz.Pixmap(r"{image_path}")
renderer = NativeRenderer()
renderer.render_pixmap(pix, 0, (1, 1, 18, 10), Screen(), None)
"""


def contains(pattern: bytes, data: bytes) -> bool:
    return data.find(pattern) >= 0


def main() -> int:
    print("=" * 60)
    print("timg Binary Contract Test")
    print("=" * 60)

    if shutil_which("timg") is None:
        print("SKIP: timg not found in PATH")
        return 0

    env = os.environ.copy()
    env["TERM"] = "xterm-kitty"
    env.pop("TMUX", None)  # non-tmux contract only

    with tempfile.TemporaryDirectory(prefix="pdfcat-timg-test-") as tmp:
        img_path = Path(tmp) / "sample.png"
        create_sample_png(img_path)

        rc_timg, out_timg, err_timg = run_in_pty(
            ["timg", "-pk", "-g", "18x9", str(img_path)],
            env,
        )
        if rc_timg != 0:
            print(f"FAIL: timg exited with {rc_timg}")
            if err_timg:
                print(err_timg.decode("utf-8", errors="replace"))
            return 1

        helper = build_native_helper(img_path)
        rc_native, out_native, err_native = run_in_pty(
            [sys.executable, "-c", helper],
            env,
        )
        if rc_native != 0:
            print(f"FAIL: native helper exited with {rc_native}")
            if err_native:
                print(err_native.decode("utf-8", errors="replace"))
            return 1

        failures = []
        checks = [
            ("timg emits kitty escape introducer", contains(b"\x1b_G", out_timg)),
            ("native emits kitty escape introducer", contains(b"\x1b_G", out_native)),
            ("timg emits kitty upload command", contains(b"a=T", out_timg)),
            ("native emits kitty upload command", contains(b"a=T", out_native)),
            (
                "native uses direct transmit (no separate place) in non-tmux mode",
                not contains(b"a=p", out_native),
            ),
            (
                "native does not emit tmux placeholders in non-tmux mode",
                not contains(b"\xf4\x8e\xbb\xae", out_native),
            ),
            (
                "timg does not emit tmux placeholders in non-tmux mode",
                not contains(b"\xf4\x8e\xbb\xae", out_timg),
            ),
            (
                "native contains base64 PNG payload",
                bool(re.search(rb"iVBORw0KGgo", out_native)),
            ),
        ]

        for label, ok in checks:
            print(f"  {'PASS' if ok else 'FAIL'}: {label}")
            if not ok:
                failures.append(label)

        print("-" * 60)
        print(f"Captured timg bytes:   {len(out_timg)}")
        print(f"Captured native bytes: {len(out_native)}")
        print("-" * 60)

        if failures:
            print(f"FAILED: {len(failures)} contract checks failed")
            return 1

    print("SUCCESS: binary contract checks passed")
    return 0


def shutil_which(name: str):
    # local helper to avoid importing shutil for one call in tiny script context
    return (
        subprocess.run(
            ["which", name],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
        or None
    )


if __name__ == "__main__":
    sys.exit(main())
