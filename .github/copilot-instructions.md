# Copilot Instructions for pdfcat

This repository contains a terminal-first PDF viewer written in Python. Use these instructions to build, test, and navigate the codebase efficiently in Copilot sessions.

## Build, Test, and Lint Commands

- Environment setup (local venv):
  - python3 -m venv .venv && source .venv/bin/activate
  - pip install -e .[dev]
  - If extras expansion fails: pip install -e . && pip install -r requirements-dev.txt
- Runtime install only:
  - pip install -r requirements.txt && pip install -e .
- Run the app:
  - pdfcat <file.pdf>
- Script-based tests (Makefile):
  - make test
  - Or individually:
    - python3 -m py_compile src/pdfcat/*.py tests/*.py
    - python3 tests/test_renderer.py
    - python3 tests/test_rendering_logic.py
    - python3 tests/test_no_blink_update.py
    - python3 tests/test_tint_mode.py
    - python3 tests/test_timg_compatibility.py
    - python3 tests/test_timg_binary_contract.py
- Pytest suite:
  - pytest -v --cov=src/pdfcat --cov-report=term-missing
  - Run a single test file: pytest tests/test_renderer.py -v
  - Run a single test by name: pytest -k test_renderer_protocol_detection -v
- Linting and type checks:
  - make lint
  - Auto-format: make fixup
  - Tools configured via pyproject.toml: ruff, black, isort, flake8, mypy

## High-Level Architecture

- Entry points:
  - src/pdfcat/app.py (project script: pdfcat=pdfcat.app:run)
  - src/pdfcat/__main__.py for python -m pdfcat
- Core orchestration and context:
  - runtime_context.py provides ViewerContext; components access context via get_context() or Document._get_context()
  - app.py wires screen, renderer, worker pool, and lifecycle/shutdown
- Document model and rendering pipeline:
  - document.py extends fitz.Document with navigation, cache, notes, presenter, and page state
  - document_rendering.py performs pixmap generation, placement, cropping, and search interactions
  - page_state.py tracks per-page placement, caches, and last image IDs
  - cache.py caches rendered PNG/PPM payloads with size/entry limits
  - navigator.py encapsulates logical/physical navigation and chapters
  - document_labels.py maps physical/logical numbering and label parsing
- Rendering engines:
  - renderers.py exposes KittyRenderer and NativeRenderer; create_renderer() selects based on environment (kitty, tmux+kitty, wezterm)
  - NativeRenderer implements Kitty protocol directly (including tmux passthrough, placeholder tiles, history clear)
  - Renderer selection is a hard requirement; the app exits if none are available
- UI and interaction:
  - ui.py renders the status bar (Rich-based), visual selection mode, and key shortcuts
  - input_handler.py defines keymaps; actions.py + executor.py execute bound operations
  - presenter.py, presenter_views.py, presenter_links.py handle TOC, metadata, link hints/list
- Neovim and notes:
  - neovim_bridge.py integrates with nvim RPC for text view/notes
  - notes.py + note_naming.py manage note paths, copying page link references, and slugification
- Multi-document and streaming:
  - document_stream.py provides live search streaming; workers.py manages background tasks

## Key Conventions Specific to pdfcat

- Module boundaries:
  - Rendering logic stays in renderers.py; do not mix UI or input handling into renderers
  - UI status and visual selection live in ui.py; input binding in input_handler.py; execution in actions.py/executor.py
  - Orchestration/lifecycle lives in app.py; shared helpers in core.py/constants.py
- Context access:
  - Prefer explicit access through runtime_context.get_context() or Document._get_context(); avoid new globals
- Rendering contract:
  - NativeRenderer and KittyRenderer must honor placement and avoid cursor flicker; tests cover no-blink behavior and tmux placeholder cleanup
  - Treat external tools (timg) as optional; fail gracefully and keep protocol compatibility
- Configuration and state:
  - User JSON config: ~/.config/pdfcat/config (e.g., TINT_COLOR, SHOW_STATUS_BAR, KITTYCMD)
  - Per-document state cache under ~/.cache/pdfcat; forced visual modes keep toggles ephemeral
- Testing discipline:
  - Validate both direct kitty and tmux+kitty paths; use test_timg_compatibility.py and test_timg_binary_contract.py for protocol-level checks
  - When rendering changes affect output, include terminal context (TERM, TMUX) in PRs
- Keyboard shim:
  - keyboard_input.py at repo root keeps src/ on sys.path for compatibility with older import paths

## References

- README.md: installation, keybindings, quick start
- CONTRIBUTING.md: setup, commands, guidelines, renderer-change validation
- Makefile: lint, fixup, test, release version bump/tag flow
- pyproject.toml: scripts, pytest/coverage, ruff config, dynamic version from pdfcat.constants

## AI Assistant Configs

- AGENTS.md exists; align with its project structure and commands. No other assistant rule files detected.

---

Would you like me to configure any MCP servers relevant to this project (e.g., a terminal graphics or testing helper)?

Summary: Added a focused Copilot instructions file with build/test/lint commands, architecture, and codebase conventions. Want to adjust anything or add coverage for areas I may have missed?