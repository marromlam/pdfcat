PYTHON ?= python3
ISORT ?= isort
BLACK ?= black
FLAKE8 ?= flake8
MYPY ?= mypy
PUSH ?= 0

FORMAT_FILES = keyboard_input.py setup.py src/pdfcat/*.py tests/*.py debug_startup.py verify_implementation.py
FLAKE8_FILES = src tests keyboard_input.py setup.py
MYPY_FILES = src tests keyboard_input.py

CURRENT_VERSION := $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' src/pdfcat/constants.py)
NEXT_VERSION := $(shell CURRENT_VERSION="$(CURRENT_VERSION)" $(PYTHON) -c 'import os, sys; p = os.environ["CURRENT_VERSION"].split("."); (len(p) == 3 and all(x.isdigit() for x in p)) or sys.exit("CURRENT_VERSION must be semantic version x.y.z"); a, b, c = map(int, p); print(f"{a}.{b}.{c+1}")')
RELEASE_VERSION ?= $(NEXT_VERSION)

.PHONY: lint fixup test commit release

lint:
	$(ISORT) --check-only --diff $(FORMAT_FILES)
	$(BLACK) --check $(FORMAT_FILES)
	$(FLAKE8) $(FLAKE8_FILES)
	PYTHONPATH=src $(MYPY) $(MYPY_FILES)

fixup:
	$(ISORT) $(FORMAT_FILES)
	$(BLACK) $(FORMAT_FILES)

test:
	$(PYTHON) -m py_compile keyboard_input.py src/pdfcat/*.py tests/*.py
	$(PYTHON) tests/test_rendering_logic.py
	$(PYTHON) tests/test_renderer.py
	$(PYTHON) tests/test_no_blink_update.py
	$(PYTHON) tests/test_tint_mode.py
	$(PYTHON) tests/test_timg_compatibility.py
	$(PYTHON) tests/test_timg_binary_contract.py

commit: lint test
	@if [ -z "$(MSG)" ]; then \
		echo 'Usage: make commit MSG="<commit message>"'; \
		exit 1; \
	fi
	@if [ "$(ADD_NEW)" = "1" ]; then \
		git add -A; \
	else \
		git add -u; \
	fi
	git commit -m "$(MSG)"

release: lint test
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Working tree is dirty. Commit or stash changes before releasing."; \
		exit 1; \
	fi
	@echo "Releasing v$(RELEASE_VERSION) (current: v$(CURRENT_VERSION))"
	@RELEASE_VERSION="$(RELEASE_VERSION)" $(PYTHON) - <<'PY'\nfrom pathlib import Path\nimport os\nimport re\nnew_version = os.environ["RELEASE_VERSION"]\nupdates = [\n    (Path("src/pdfcat/constants.py"), r'(__version__\\s*=\\s*")([^"]+)(")'),\n    (Path("setup.py"), r'(version\\s*=\\s*")([^"]+)(")'),\n]\nfor path, pattern in updates:\n    text = path.read_text(encoding="utf-8")\n    updated, count = re.subn(pattern, rf'\\1{new_version}\\3', text, count=1)\n    if count != 1:\n        raise SystemExit(f"Failed to update version in {path}")\n    path.write_text(updated, encoding="utf-8")\nprint(f"Updated version to {new_version}")\nPY
	git add src/pdfcat/constants.py setup.py
	git commit -m "release: v$(RELEASE_VERSION)"
	git tag -a "v$(RELEASE_VERSION)" -m "v$(RELEASE_VERSION)"
	@if [ "$(PUSH)" = "1" ]; then \
		git push origin HEAD && git push origin "v$(RELEASE_VERSION)"; \
		echo "Release pushed to origin."; \
	else \
		echo "Release commit/tag created locally."; \
		echo "To push: git push origin HEAD && git push origin v$(RELEASE_VERSION)"; \
	fi
