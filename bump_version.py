#!/usr/bin/env python3
"""Bump version in constants.py"""

import os
import re
from pathlib import Path

new_version = os.environ["RELEASE_VERSION"]
constants_path = Path("src/pdfcat/constants.py")
text = constants_path.read_text(encoding="utf-8")
updated, count = re.subn(
    r'__version__\s*=\s*"[^"]+"',
    f'__version__ = "{new_version}"',
    text,
    count=1
)
if count != 1:
    raise SystemExit(f"Failed to update version in {constants_path}")
constants_path.write_text(updated, encoding="utf-8")
print(f"Updated version to {new_version}")

