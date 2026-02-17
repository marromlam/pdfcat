# Contributing to pdfcat

Thanks for contributing. This project is a terminal-first PDF viewer with a Python codebase under `src/pdfcat/`.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

If your shell does not support extras expansion, use:

```bash
pip install -e .
pip install -r requirements-dev.txt
```

## Development Commands

- Lint + typing:
  - `make lint`
- Auto-format:
  - `make fixup`
- Script-based tests:
  - `make test`
- Pytest suite:
  - `pytest -v --cov=src/pdfcat --cov-report=term-missing`

## Code Guidelines

- Python 3.11+ and 4-space indentation.
- Keep responsibilities separated:
  - rendering logic in `renderers.py`
  - UI behavior in `ui.py`
  - orchestration in `app.py`
- Prefer explicit context access through `ViewerContext` / `runtime_context`.
- Use `logging` instead of ad-hoc `print()` in runtime paths.

## Typical Contribution Flows

### Add a New Keybinding

1. Add key mapping in `src/pdfcat/input_handler.py`.
2. Add/extend action in `src/pdfcat/actions.py`.
3. Implement execution in `src/pdfcat/executor.py`.
4. Update shortcut text in `src/pdfcat/constants.py`.
5. Add unit test(s) in `tests/`.

### Add Document Behavior

1. Implement focused helper function/module in `src/pdfcat/`.
2. Keep `Document` as integration/orchestration layer.
3. Add tests for both core function and user-visible behavior.

### Add/Change Renderer Behavior

1. Update `src/pdfcat/renderers.py`.
2. Validate both direct kitty and tmux+kitty paths.
3. Run compatibility checks:
   - `python3 tests/test_timg_compatibility.py`
   - `python3 tests/test_timg_binary_contract.py`

## Pull Request Checklist

- Code formatted and linted.
- Relevant tests added/updated.
- `make test` and `pytest` pass locally.
- PR description includes:
  - problem statement
  - approach
  - verification commands
  - terminal context (`TERM`, `TMUX`) for renderer changes.
