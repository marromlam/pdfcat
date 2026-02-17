# pdfcat Consolidated Learnings

This file consolidates the root-level Markdown notes in this repository into one source of truth.

Scope covered:
- `AGENTS.md`
- `BLANK_SCREEN_FIX.md`
- `CENTERING_AND_TOC_FIX.md`
- `CURSES_REPLACEMENT_PLAN.md`
- `CURSOR_HIDING_FIX.md`
- `DEPENDENCIES_STATUS.md`
- `FINAL_STATUS.md`
- `FIXES_APPLIED.md`
- `IMPLEMENTATION_SUMMARY.md`
- `README.md`
- `RENDERING_FIX.md`
- `RICH_MIGRATION_COMPLETE.md`
- `RICH_TEXTUAL_MIGRATION.md`
- `RICH_VS_TEXTUAL.md`
- `SCROLLING_FIX.md`
- `STATUSBAR_FIX.md`
- `STATUSBAR_PERSISTENCE_FIX.md`
- `STATUSBAR_RENDER_FIX.md`
- `STATUSBAR_STYLING_UPDATE.md`
- `THREAD_CLEANUP_FIX.md`
- `THREAD_FIX_V2.md`
- `THREAD_FIX_V3_FINAL.md`
- `TMUX_SIXEL_GUIDE.md`

## 1. High-Level Outcome

`pdfcat` evolved from a curses-based script into a package-based terminal PDF reader with:
- Rich-based status/UI text rendering
- custom raw keyboard input handling
- renderer abstraction with terminal/protocol-aware backends
- tmux + kitty compatibility as a primary target
- cleaner shutdown behavior and fewer stdin/thread issues

## 2. Canonical Technical Decisions

### 2.1 UI and terminal control

- Keep terminal control low-level for critical operations.
- Use ANSI escape sequences for screen/cursor control where graphics reliability matters.
- Do not rely on `console.clear()` in graphics paths.
- Keep status/UI rendering separate from image rendering.

Why:
- Multiple docs (`RENDERING_FIX.md`, `SCROLLING_FIX.md`, `STATUSBAR_PERSISTENCE_FIX.md`) show that high-level clears and unmanaged cursor state caused blank screens, disappearing status bar, or scroll artifacts.

### 2.2 Rendering strategy

- Rendering is backend-driven (native kitty path with kitty fallback).
- Renderer selection is environment-aware (kitty/tmux/sixel capabilities).
- External renderer image output must go directly to terminal stdout.
- Avoid capturing renderer stdout when the renderer emits graphics escape sequences.

Why:
- `BLANK_SCREEN_FIX.md` and `TMUX_SIXEL_GUIDE.md` show this was the key difference between visible images and blank output.

### 2.3 Threading and shutdown

- Final rule: stdin/UI loop runs on the main thread.
- Background threads are allowed only for non-stdin work (for example file-watch checks).
- Shutdown should be signal-aware and deterministic.

Why:
- `THREAD_CLEANUP_FIX.md` -> `THREAD_FIX_V2.md` -> `THREAD_FIX_V3_FINAL.md` documents iterative fixes, with V3 capturing the stable model.

### 2.4 ncurses replacement choice

- Rich + custom input handling was chosen over Textual and over continuing with ncurses.

Why:
- `RICH_TEXTUAL_MIGRATION.md`, `RICH_VS_TEXTUAL.md`, `CURSES_REPLACEMENT_PLAN.md` converge on this:
  - Rich gives formatting without forcing a heavy app framework.
  - custom input avoids ncurses lifecycle/thread conflicts.
  - Textual was judged heavier and potentially conflicting for this graphics-heavy viewer.

## 3. Consolidated Fix Learnings

### 3.1 Rendering correctness

- Do not capture subprocess stdout for graphics renderers.
- Avoid `console.clear()` in render-critical paths.
- Always account for full-screen clearing side effects when redrawing UI.

### 3.2 Status bar reliability

- Protect the status bar row from image placement geometry.
- Re-render the status bar after any operation that clears the full terminal.
- Keep styling logic independent from placement logic.

Related docs:
- `STATUSBAR_RENDER_FIX.md`
- `STATUSBAR_FIX.md`
- `STATUSBAR_PERSISTENCE_FIX.md`
- `STATUSBAR_STYLING_UPDATE.md`

### 3.3 Cursor behavior

- Cursor hiding has to be reapplied after operations that may reset cursor state.
- Restore cursor on exit.

Related doc:
- `CURSOR_HIDING_FIX.md`

### 3.4 TOC/metadata stability during migration

- During ncurses removal, compatibility shims were needed (`SimpleWindow`-style API expectations).
- This fixed crashes but is an interim architecture; a native Rich rendering path for these views is cleaner long-term.

Related doc:
- `CENTERING_AND_TOC_FIX.md`

## 4. Environment and Dependency Learnings

- Python dependencies are straightforward (`PyMuPDF`, `Pillow`, `rich`, etc.).
- Real terminal behavior depends heavily on external tool availability and terminal protocol support.
- `timg` is the most important external renderer for tmux+kitty scenarios.

Related docs:
- `DEPENDENCIES_STATUS.md`
- `TMUX_SIXEL_GUIDE.md`

## 5. Testing and Verification Pattern

The docs consistently recommend validating changes with:
- syntax/import checks
- renderer availability checks
- protocol compatibility checks
- manual navigation/rotation/status bar checks inside target terminal contexts

This is now reflected in repository scripts and testing notes (`AGENTS.md`, `IMPLEMENTATION_SUMMARY.md`, `FINAL_STATUS.md`).

## 6. Document Status Map (Current vs Historical)

### Current reference docs

- `README.md`: user-facing usage and feature overview.
- `AGENTS.md`: contributor rules and project conventions.
- `TMUX_SIXEL_GUIDE.md`: environment and renderer behavior guidance.
- `IMPLEMENTATION_SUMMARY.md`: broad technical context (still useful).

### Historical/iterative fix logs (valuable for root-cause history)

- `THREAD_CLEANUP_FIX.md`, `THREAD_FIX_V2.md`, `THREAD_FIX_V3_FINAL.md`
- `STATUSBAR_RENDER_FIX.md`, `STATUSBAR_FIX.md`, `STATUSBAR_PERSISTENCE_FIX.md`, `STATUSBAR_STYLING_UPDATE.md`
- `RENDERING_FIX.md`, `BLANK_SCREEN_FIX.md`, `SCROLLING_FIX.md`
- `CENTERING_AND_TOC_FIX.md`
- `FINAL_STATUS.md`, `FIXES_APPLIED.md`, `DEPENDENCIES_STATUS.md`
- `RICH_MIGRATION_COMPLETE.md`

### Planning docs (superseded by implementation)

- `CURSES_REPLACEMENT_PLAN.md`
- `RICH_TEXTUAL_MIGRATION.md`
- `RICH_VS_TEXTUAL.md`

## 7. Practical Rules to Keep

1. Treat graphics rendering and terminal control as protocol-sensitive code; avoid high-level abstractions in critical paths.
2. Keep stdin/UI in the main thread.
3. Assume full-screen clears will erase UI overlays; redraw status/UI explicitly.
4. Protect reserved UI rows in geometry calculations.
5. Validate behavior in real terminal contexts (`TERM`, `TMUX`) before declaring a fix complete.
6. Keep renderer fallbacks graceful when tools are missing.

## 8. Open Follow-Ups Highlighted Across Notes

- Replace shimmed text-window compatibility with native Rich-based TOC/metadata/link views.
- Continue reducing duplicated historical docs as behavior stabilizes.
- Keep documentation aligned with package layout (`src/pdfcat`) and current command (`pdfcat`).
