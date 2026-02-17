"""BibTeX lookup helpers."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any

from .runtime_context import get_context


def _bibtex_path() -> str:
    ctx = get_context()
    if ctx is not None:
        config = getattr(ctx, "config", None)
        return str(getattr(config, "BIBTEX", ""))
    return ""


def bib_from_field(field: str, regex: str) -> Any | None:
    bibtex_path = _bibtex_path()
    if shutil.which("bibtool") is not None:
        from pybtex.database import parse_string

        select = "select {" + field + " "
        select = select + '"{}"'.format(regex)
        select = select + "}"
        text = subprocess.run(
            ["bibtool", "-r", "biblatex", "--", select, bibtex_path],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        if text.returncode != 0:
            return None
        bib = parse_string(text.stdout, "bibtex")
        if len(bib.entries) == 0:
            return None
    else:
        from pybtex.database import parse_file

        bib = parse_file(bibtex_path, "bibtex")

    return bib


def bib_from_key(citekeys: list[str]) -> Any | None:
    field = "$key"
    regex = r"\|".join(citekeys)
    regex = "^" + regex + "$"
    return bib_from_field(field, regex)


def citekey_from_path(path: str) -> str | None:
    path = os.path.basename(path)
    bib = bib_from_field("File", path)

    if bib and len(bib.entries) == 1:
        citekey = list(bib.entries)[0]
        return str(citekey)
    return None


def path_from_citekey(citekey: str) -> str | None:
    bib = bib_from_key([citekey])
    if bib is None:
        raise SystemExit("Cannot find file associated with " + citekey)
    if len(bib.entries) == 1:
        try:
            paths = bib.entries[citekey].fields["File"]
        except (KeyError, AttributeError) as e:
            logging.error("BibTeX entry missing 'File' field for %s: %s", citekey, e)
            raise SystemExit(f"No file for {citekey}") from e
        paths = paths.split(";")
        exts = [".pdf", ".xps", ".cbz", ".fb2"]
        extsf = [".epub", ".oxps"]
        extsl = [".html"]
        best = [path for path in paths if path[-4:] in exts]
        okay = [path for path in paths if path[-5:] in extsf]
        worst = [path for path in paths if path[-5:] in extsl]
        if len(best) != 0:
            return str(best[0])
        elif len(okay) != 0:
            return str(okay[0])
        elif len(worst) != 0:
            return str(worst[0])
    return None


# Command line helper functions
