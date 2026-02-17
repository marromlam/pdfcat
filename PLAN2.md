# pdfcat Quick Wins & UX Improvements

**Status**: Draft
**Created**: 2026-02-15
**Target Completion**: 2-3 days
**Owner**: Engineering Team

This document contains high-impact, low-effort improvements that can be done quickly before the major refactoring in PLAN.md.

---

## Table of Contents

1. [Quick Win 1: Remove _write_gr_cmd_with_response()](#quick-win-1-remove-_write_gr_cmd_with_response)
2. [Quick Win 2: Vim-like Buffer Switching](#quick-win-2-vim-like-buffer-switching)

---

## Quick Win 1: Remove _write_gr_cmd_with_response()

**Priority**: P1 (Quick Win)
**Estimated Effort**: 1-2 hours
**File**: `src/pdfcat/renderers.py`

### Problem

The `_write_gr_cmd_with_response()` method in KittyRenderer:
- Blocks on stdin reading (can cause threading issues)
- Adds unnecessary complexity
- Slows down rendering
- Is NOT used by NativeRenderer (the default renderer)

### Solution

Replace terminal protocol detection with environment variable checks, matching what NativeRenderer already does.

### Implementation

**Step 1**: Update `KittyRenderer` class in `src/pdfcat/renderers.py`:

```python
class KittyRenderer(RenderingEngine):
    """Native Kitty protocol renderer (legacy fallback)"""

    def __init__(self) -> None:
        self.name = "kitty"
        self.requires_clear_before_render = False

    def detect_support(self) -> bool:
        """Check if Kitty protocol is supported via environment.

        Returns:
            True if Kitty protocol is available
        """
        term = os.environ.get("TERM", "").lower()
        term_program = os.environ.get("TERM_PROGRAM", "").lower()

        kitty_env = bool(
            os.environ.get("KITTY_WINDOW_ID") or
            os.environ.get("KITTY_PID")
        )

        # Support kitty and wezterm
        if "kitty" in term or kitty_env or term_program == "wezterm":
            logging.info("Kitty protocol detected via environment")
            return True

        logging.debug("Kitty protocol not detected in environment")
        return False

    def _serialize_gr_command(self, cmd, payload=None):
        """Serialize a graphics command.

        Args:
            cmd: Command dictionary
            payload: Optional payload bytes

        Returns:
            Serialized command bytes
        """
        cmd_str = ",".join("{}={}".format(k, v) for k, v in cmd.items())
        ans = []
        w = ans.append
        w(b"\033_G"), w(cmd_str.encode("ascii"))
        if payload:
            w(b";")
            w(payload)
        w(b"\033\\")
        return b"".join(ans)

    def _write_gr_cmd(self, cmd, payload=None) -> None:
        """Write a graphics command to stdout.

        Args:
            cmd: Command dictionary
            payload: Optional payload bytes
        """
        sys.stdout.buffer.write(self._serialize_gr_command(cmd, payload))
        sys.stdout.flush()

    # REMOVED: _write_gr_cmd_with_response() - no longer needed!

    def _write_chunked(self, cmd, data) -> None:
        """Write data in chunks.

        Args:
            cmd: Command dictionary (will be modified)
            data: Data to write
        """
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

    def render_pixmap(self, pixmap, page_num, placement, screen, page_state=None):
        """Render a pixmap using Kitty protocol.

        Args:
            pixmap: Pixmap to render
            page_num: Page number
            placement: Placement tuple (left, top, right, bottom)
            screen: Screen object
            page_state: Optional page state

        Returns:
            True (assumes success)
        """
        # Build command to send to kitty
        cmd = {"i": page_num + 1, "t": "d", "s": pixmap.width, "v": pixmap.height}

        if pixmap.alpha:
            cmd["f"] = 32
        else:
            cmd["f"] = 24

        # Transfer the image
        self._write_chunked(cmd, pixmap.samples)

        # Display the image (fire and forget for performance)
        cmd = {"a": "p", "i": page_num + 1, "z": -1}
        self._write_gr_cmd(cmd)

        # Assume success - if terminal doesn't support it, detection would have failed
        return True

    def clear_image(self, page_num) -> None:
        """Clear a previously rendered image.

        Args:
            page_num: Page number to clear
        """
        cmd = {"a": "d", "d": "a", "i": page_num + 1}
        self._write_gr_cmd(cmd)

    def cleanup(self) -> None:
        """Cleanup resources."""
        pass
```

**Step 2**: Remove the old method entirely:

Search for and delete (lines 78-96 in original):
```python
def _write_gr_cmd_with_response(self, cmd, payload=None) -> bool | None:
    """Write a graphics command and wait for response"""
    # ... DELETE THIS ENTIRE METHOD ...
```

**Step 3**: Test the changes:

```bash
# Test that pdfcat still works
pdfcat sample.pdf

# Should see in logs (if you have logging enabled):
# "Kitty protocol detected via environment"
```

### Benefits

- ✅ **Simpler code**: Removes 18 lines of complex stdin reading
- ✅ **Faster**: No blocking on terminal responses
- ✅ **More reliable**: No threading issues with stdin
- ✅ **Consistent**: Matches NativeRenderer behavior
- ✅ **Safer**: No risk of hanging on response timeout

### Acceptance Criteria

- ✅ `_write_gr_cmd_with_response()` method removed
- ✅ KittyRenderer uses environment detection
- ✅ pdfcat still renders PDFs correctly
- ✅ No regression in kitty/wezterm terminals

### Testing Checklist

```bash
# 1. Test in kitty terminal
export TERM=xterm-kitty
pdfcat test.pdf
# Should work

# 2. Test in tmux + kitty
tmux
pdfcat test.pdf
# Should work

# 3. Test in non-kitty terminal (should gracefully fail)
export TERM=xterm-256color
unset KITTY_WINDOW_ID
pdfcat test.pdf
# Should show error about no renderer available
```

---

## Quick Win 2: Vim-like Buffer Switching

**Priority**: P1 (UX Improvement)
**Estimated Effort**: 2-3 hours
**Files**: `src/pdfcat/app.py`, `src/pdfcat/ui.py`, `src/pdfcat/constants.py`

### Problem

Current buffer switching is not intuitive:
- `bb` to go to next PDF (requires two key presses)
- `b0`, `b1`, `b2` to jump to specific buffer (inconsistent with count prefix)
- Not Vim-like

### Desired Behavior (Vim-style)

- `b` - go to next PDF (one keypress)
- `B` - go to previous PDF
- `3b` - go forward 3 PDFs
- `5B` - go back 5 PDFs
- `:b2` or `2gb` - jump to buffer 2 (future enhancement, not in this quick win)

### Implementation

**Step 1**: Update keybinding definitions in `src/pdfcat/ui.py`:

Find the shortcuts class (around line 328) and update:

```python
class shortcuts:
    def __init__(self) -> None:
        # ... other keybindings ...

        # OLD (two-key buffer switching):
        # self.BUFFER_CYCLE = [ord("b")]
        # self.BUFFER_CYCLE_REV = [ord("B")]

        # NEW (Vim-style single-key buffer switching):
        self.BUFFER_NEXT = [ord("b")]
        self.BUFFER_PREV = [ord("B")]

        # Remove the old multi-key buffer system
        # REMOVED: self.BUFFER_CYCLE
        # REMOVED: self.BUFFER_CYCLE_REV
```

**Step 2**: Update the main event loop in `src/pdfcat/app.py`:

Find the buffer switching logic (around line 1228-1270) and replace with:

```python
# REMOVE OLD BUFFER SWITCHING CODE (lines ~1228-1270):
# elif stack[0] in keys.BUFFER_CYCLE and key in range(48, 58):
#     ...
# elif stack[0] in keys.BUFFER_CYCLE and key == ord("d"):
#     ...
# elif stack[0] in keys.BUFFER_CYCLE and key in keys.BUFFER_CYCLE:
#     ...
# elif key in keys.BUFFER_CYCLE_REV:
#     ...

# ADD NEW VIM-STYLE BUFFER SWITCHING:

        elif key in keys.BUFFER_NEXT:
            # b or [count]b: cycle forward through buffers
            state.bufs.cycle(count)
            doc = state.bufs.docs[state.bufs.current]
            doc.goto_logical_page(doc.logicalpage)
            doc.set_layout(doc.papersize, adjustpage=False)
            doc.mark_all_pages_stale()
            if doc.citekey:
                bar.message = f"Buffer {state.bufs.current + 1}/{len(state.bufs.docs)}: {doc.citekey}"
            else:
                import os
                filename = os.path.basename(doc.filename)
                bar.message = f"Buffer {state.bufs.current + 1}/{len(state.bufs.docs)}: {filename}"
            count_string = ""
            stack = [0]

        elif key in keys.BUFFER_PREV:
            # B or [count]B: cycle backward through buffers
            state.bufs.cycle(-count)
            doc = state.bufs.docs[state.bufs.current]
            doc.goto_logical_page(doc.logicalpage)
            doc.set_layout(doc.papersize, adjustpage=False)
            doc.mark_all_pages_stale()
            if doc.citekey:
                bar.message = f"Buffer {state.bufs.current + 1}/{len(state.bufs.docs)}: {doc.citekey}"
            else:
                import os
                filename = os.path.basename(doc.filename)
                bar.message = f"Buffer {state.bufs.current + 1}/{len(state.bufs.docs)}: {filename}"
            count_string = ""
            stack = [0]
```

**Step 3**: Update documentation in `src/pdfcat/constants.py`:

Update the VIEWER_SHORTCUTS help text (around line 27):

```python
VIEWER_SHORTCUTS = """\
Keys:
    j, down, space: forward [count] pages
    k, up:          back [count] pages
    l, right:       forward [count] sections
    h, left:        back [count] sections
    gg:             go to beginning of document
    G:              go to end of document
    [count]G:       go to logical page [count]
    [count]J:       go to physical page [count]
    b:              next buffer (PDF)
    [count]b:       next [count] buffers
    B:              previous buffer
    [count]B:       previous [count] buffers
    /:              live search (ripgrep/fzf)
    s:              open current page as text in minimal Neovim
    S:              visual mode
    t:              table of contents
    M:              show metadata
    f:              follow link hint (Vimium-style)
    F:              open full link list in fzf (fallback to in-terminal list)
    r:              rotate [count] quarter turns clockwise
    R:              rotate [count] quarter turns counterclockwise
    c:              toggle autocropping of margins
    n:              open document note in Neovim
    a:              copy page link and open document note in Neovim
    A:              toggle alpha transparency
    i:              invert colors
    d:              darken using TINT_COLOR
    z:              toggle autoplay ([count]z sets fps)
    E:              set autoplay end page ([count]E, 0E clears to doc end)
    P:              toggle presenter mode
    O:              open in external system PDF viewer
    [count]P:       Set logical page number of current page to count
    -:              zoom out (reflowable only)
    +:              zoom in (reflowable only)
    ctrl-r:         refresh
    (in / search) ctrl-r: ripgrep mode, ctrl-f: fzf mode
    ctrl-s:         reverse SyncTeX (PDF -> source in Neovim)
    ?:              show keybinds
    q:              quit
"""
```

**Step 4**: Update the README.md:

Find the buffer switching section and update:

```markdown
### Buffer Management

- `b`: next buffer (PDF)
- `3b`: next 3 buffers
- `B`: previous buffer
- `5B`: previous 5 buffers
```

**Step 5** (Optional): Add buffer delete command

If you want to keep the ability to close a buffer, add a new keybinding:

In `src/pdfcat/ui.py`:
```python
self.BUFFER_DELETE = [ord("d")]  # Only when in "close mode", or use :bd
```

For now, we can skip this and just use `q` to quit when on the last buffer.

### Alternative: Keep `bd` for Delete

If you want to keep the `bd` pattern for closing buffers (which is also Vim-like), you can:

```python
# In shortcuts class:
self.BUFFER_NEXT = [ord("b")]
self.BUFFER_PREV = [ord("B")]
self.BUFFER_DELETE_PREFIX = [ord("b")]  # First 'b' for bd command

# In event loop:
elif stack[0] in keys.BUFFER_DELETE_PREFIX and key == ord("d"):
    # bd: close current buffer
    state.bufs.close_buffer(state.bufs.current)
    doc = state.bufs.docs[state.bufs.current]
    doc.goto_logical_page(doc.logicalpage)
    doc.set_layout(doc.papersize, adjustpage=False)
    doc.mark_all_pages_stale()
    bar.message = f"Buffer closed. Now viewing {state.bufs.current + 1}/{len(state.bufs.docs)}"
    count_string = ""
    stack = [0]

elif key in keys.BUFFER_NEXT:
    # Single 'b' press
    if stack[0] == ord("b"):
        # This was 'bb', but we want single 'b' to work
        # Clear the stack first
        stack = [0]
    state.bufs.cycle(count)
    # ... rest of buffer switching ...
```

Actually, this gets complex. Let me provide a cleaner solution:

### Cleaner Solution: Use Timeout for `bd`

```python
# In the event loop, where you handle keys:

elif key == ord("b"):
    # Wait briefly to see if 'd' follows (for 'bd' command)
    next_key = state.scr.kb_input.getch(timeout=0.3)  # 300ms timeout

    if next_key == ord("d"):
        # bd: close current buffer
        state.bufs.close_buffer(state.bufs.current)
        doc = state.bufs.docs[state.bufs.current]
        doc.goto_logical_page(doc.logicalpage)
        doc.set_layout(doc.papersize, adjustpage=False)
        doc.mark_all_pages_stale()
        if doc.citekey:
            bar.message = f"Closed buffer. Now: {doc.citekey}"
        else:
            bar.message = f"Closed buffer. Now viewing {state.bufs.current + 1}/{len(state.bufs.docs)}"
        count_string = ""
        stack = [0]

    elif next_key == -1:
        # Timeout - just 'b' was pressed
        state.bufs.cycle(count)
        doc = state.bufs.docs[state.bufs.current]
        doc.goto_logical_page(doc.logicalpage)
        doc.set_layout(doc.papersize, adjustpage=False)
        doc.mark_all_pages_stale()
        if doc.citekey:
            bar.message = f"Buffer {state.bufs.current + 1}/{len(state.bufs.docs)}: {doc.citekey}"
        else:
            import os
            filename = os.path.basename(doc.filename)
            bar.message = f"Buffer {state.bufs.current + 1}/{len(state.bufs.docs)}: {filename}"
        count_string = ""
        stack = [0]

    else:
        # Some other key was pressed after 'b'
        # Put it back for processing
        # This is tricky - we'd need to buffer it
        # For now, just ignore
        pass
```

**Actually, this timeout approach is janky. Better solution:**

### Best Solution: Single Character Commands Only

Keep it simple and Vim-pure:

- `b` = next buffer (like `:bn` in Vim)
- `B` = previous buffer (like `:bp` in Vim)
- Remove `bd` - users can just use `q` to quit
- If they want to close a specific buffer, they can switch to it and quit

This is the cleanest and most Vim-like. Let's go with this approach.

### Final Implementation

Here's the complete, clean implementation:

**File: `src/pdfcat/ui.py`** (update shortcuts class):

```python
class shortcuts:
    def __init__(self) -> None:
        # Navigation
        self.GOTO_PAGE = [ord("G")]
        self.GOTO_PAGE_PHYSICAL = [ord("J")]
        self.GOTO = [ord("g")]
        self.NEXT_PAGE = [ord("j"), "KEY_DOWN", ord(" ")]
        self.PREV_PAGE = [ord("k"), "KEY_UP"]
        self.GO_BACK = [ord("p")]
        self.NEXT_CHAP = [ord("l"), "KEY_RIGHT"]
        self.PREV_CHAP = [ord("h"), "KEY_LEFT"]

        # Buffer switching (Vim-style)
        self.BUFFER_NEXT = [ord("b")]
        self.BUFFER_PREV = [ord("B")]

        # ... rest of shortcuts ...
```

**File: `src/pdfcat/app.py`** (replace buffer switching logic around line 1228-1270):

```python
        # Remove all the old buffer switching code with stack[0] checks
        # Replace with simple, direct buffer switching:

        elif key in keys.BUFFER_NEXT:
            # b or [count]b: next buffer(s)
            state.bufs.cycle(count)
            doc = state.bufs.docs[state.bufs.current]
            doc.goto_logical_page(doc.logicalpage)
            doc.set_layout(doc.papersize, adjustpage=False)
            doc.mark_all_pages_stale()

            # Show which buffer we're on
            total_buffers = len(state.bufs.docs)
            current_buffer = state.bufs.current + 1

            if doc.citekey:
                bar.message = f"[{current_buffer}/{total_buffers}] {doc.citekey}"
            else:
                import os
                filename = os.path.basename(doc.filename)
                bar.message = f"[{current_buffer}/{total_buffers}] {filename}"

            count_string = ""
            stack = [0]

        elif key in keys.BUFFER_PREV:
            # B or [count]B: previous buffer(s)
            state.bufs.cycle(-count)
            doc = state.bufs.docs[state.bufs.current]
            doc.goto_logical_page(doc.logicalpage)
            doc.set_layout(doc.papersize, adjustpage=False)
            doc.mark_all_pages_stale()

            # Show which buffer we're on
            total_buffers = len(state.bufs.docs)
            current_buffer = state.bufs.current + 1

            if doc.citekey:
                bar.message = f"[{current_buffer}/{total_buffers}] {doc.citekey}"
            else:
                import os
                filename = os.path.basename(doc.filename)
                bar.message = f"[{current_buffer}/{total_buffers}] {filename}"

            count_string = ""
            stack = [0]
```

### Testing

**Test Case 1: Single buffer switching**
```bash
pdfcat file1.pdf file2.pdf file3.pdf

# Press 'b' → switches from file1 to file2
# Press 'b' → switches from file2 to file3
# Press 'b' → wraps to file1
# Press 'B' → switches back to file3
```

**Test Case 2: Count prefix**
```bash
pdfcat file1.pdf file2.pdf file3.pdf file4.pdf file5.pdf

# Currently on file1
# Press '3b' → jumps to file4 (1 + 3)
# Press '2B' → jumps to file2 (4 - 2)
```

**Test Case 3: Buffer wrapping**
```bash
pdfcat file1.pdf file2.pdf file3.pdf

# On file3
# Press 'b' → wraps to file1
# Press 'B' → wraps to file3
```

### Benefits

- ✅ **More intuitive**: Single keypress to switch buffers
- ✅ **Vim-like**: Matches `:bn` and `:bp` behavior
- ✅ **Count support**: `3b` to jump forward 3 buffers
- ✅ **Simpler code**: Removes complex stack-based buffer logic
- ✅ **Better UX**: Clear feedback in status bar

### Acceptance Criteria

- ✅ Single `b` switches to next buffer
- ✅ Single `B` switches to previous buffer
- ✅ `[count]b` advances count buffers
- ✅ `[count]B` goes back count buffers
- ✅ Buffer wraps around (last → first, first → last)
- ✅ Status bar shows `[current/total] filename`
- ✅ All existing functionality preserved

### Documentation Updates

Update README.md:

```markdown
### Multi-document sessions

When opening multiple PDFs:

```bash
pdfcat paper1.pdf paper2.pdf paper3.pdf
```

- `b`: next document
- `3b`: skip forward 3 documents
- `B`: previous document
- `2B`: skip back 2 documents
```

---

## Summary

These two quick wins provide:

1. **Cleaner code**: Remove blocking stdin reads and complex buffer logic
2. **Better UX**: Vim-like buffer switching that feels natural
3. **Low risk**: Small, focused changes
4. **High impact**: Noticeable improvement in daily use

Both can be completed in a few hours and don't require the larger refactoring from PLAN.md.

---

## Next Steps

After completing these quick wins:

1. Test thoroughly with multiple PDFs
2. Update all documentation
3. Create a PR with these changes
4. Then move on to PLAN.md for the larger refactoring

These improvements will make pdfcat more pleasant to use while you work through the bigger architectural changes!
