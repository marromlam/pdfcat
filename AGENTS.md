# Repository Guidelines

## Project Structure & Module Organization
Runtime code lives in `src/pdfcat/`:
- `app.py`: CLI entry, event loop, lifecycle/shutdown.
- `document.py`: `Document` model and page state behavior.
- `renderers.py`: Kitty/native/tmux rendering engines.
- `ui.py`: status bar, key bindings, visual mode helpers.
- `core.py`, `bib.py`, `state.py`, `constants.py`: shared support modules.

Compatibility shim remains at repo root (`keyboard_input.py`). Tests are in `tests/`.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate`: create local environment.
- `pip install -r requirements.txt`: install runtime dependencies.
- `pip install -e .`: editable install with `pdfcat` console entrypoint.
- `pdfcat <file.pdf>`: run the viewer.
- `python3 tests/test_renderer.py`: check renderer availability.
- `python3 tests/test_timg_compatibility.py`: verify native renderer behavior against timg source.
- `python3 tests/test_timg_binary_contract.py`: protocol-level native vs. external timg check.
- `python3 -m py_compile src/pdfcat/*.py tests/*.py`: fast syntax validation.

## Coding Style & Naming Conventions
- Use Python 3 with 4-space indentation.
- Naming: `snake_case` functions/variables, `CamelCase` classes, `UPPER_CASE` constants.
- Keep module boundaries clean: rendering logic stays in `renderers.py`, UI state in `ui.py`, orchestration in `app.py`.
- Prefer explicit state access through `pdfcat.state` over new module-level globals.
- Use `logging` for runtime diagnostics; avoid noisy prints in core modules.

## Testing Guidelines
- Tests are script-based (not a full `pytest` suite yet).
- Add test scripts under `tests/` using `test_<feature>.py` naming.
- For renderer changes, validate both non-tmux and tmux paths.
- When changing rendering output, include exact commands used and terminal context (`TERM`, `TMUX`).

## Commit & Pull Request Guidelines
- Use concise imperative commit subjects (prefixes like `feat:` / `fix:` are encouraged).
- Keep each commit scoped to one logical change.
- PRs should include: problem, approach, verification commands, and terminal environment details.

## Security & Configuration Tips
- User config is read from `~/.config/pdfcat/config`.
- Treat external tool availability (`timg`, Kitty protocol support) as optional and fail gracefully.
