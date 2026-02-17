"""Document page-label and logical-page helpers."""

from __future__ import annotations

import logging
import string
from operator import attrgetter
from typing import Any, NoReturn

import roman


def parse_page_labels(doc: Any):
    if doc.is_pdf:
        from pagelabels import PageLabels
        from pdfrw import PdfReader

        try:
            reader = PdfReader(doc.filename)
            labels = PageLabels.from_pdf(reader)
            labels = sorted(labels, key=attrgetter("startpage"))
        except Exception:
            labels = []
    else:
        labels = []
    return labels


def set_page_label(doc: Any, count, style: str = "arabic") -> None:
    if doc.is_pdf:
        from pagelabels import PageLabels, PageLabelScheme
        from pdfrw import PdfReader, PdfWriter

        reader = PdfReader(doc.filename)
        labels = PageLabels.from_pdf(reader)
        newlabels = PageLabels()
        for label in labels:
            if label.startpage != doc.page:
                newlabels.append(label)

        newlabel = PageLabelScheme(startpage=doc.page, style=style, prefix="", firstpagenum=count)
        newlabels.append(newlabel)
        newlabels.write(reader)

        writer = PdfWriter()
        writer.trailer = reader
        logging.debug("writing new pagelabels...")
        writer.write(doc.filename)


def parse_page_labels_pure(doc: Any) -> NoReturn:
    # unused; using pdfrw instead
    cat = doc._getPDFroot()

    cat_str = doc._getXrefString(cat)
    lines = cat_str.split("\n")
    labels = []
    for line in lines:
        if line.startswith("/PageLabels"):
            labels += [line]
    logging.debug(labels)
    raise SystemExit


def build_logical_pages(doc: Any) -> None:
    labels = parse_page_labels(doc)
    doc.logical_pages = [str(p) for p in range(0, doc.pages + 1)]

    def divmod_alphabetic(n):
        a, b = divmod(n, 26)
        if b == 0:
            return a - 1, b + 26
        return a, b

    def to_alphabetic(n):
        chars = []
        while n > 0:
            n, d = divmod_alphabetic(n)
            chars.append(string.ascii_uppercase[d - 1])
        return "".join(reversed(chars))

    if labels == []:
        for p in range(0, doc.pages + 1):
            doc.logical_pages[p] = str(p + doc.first_page_offset)
    else:
        for p in range(0, doc.pages + 1):
            for label in labels:
                if p >= label.startpage:
                    lp = (p - label.startpage) + label.firstpagenum
                    style = label.style
                    prefix = label.prefix
            if style == "roman uppercase":
                lp = prefix + roman.toRoman(lp)
                lp = lp.upper()
            elif style == "roman lowercase":
                lp = prefix + roman.toRoman(lp)
                lp = lp.lower()
            elif style == "alphabetic uppercase":
                lp = prefix + to_alphabetic(lp)
            elif style == "alphabetic lowercase":
                lp = prefix + to_alphabetic(lp)
                lp = lp.lower()
            else:
                lp = prefix + str(lp)
            doc.logical_pages[p] = lp


def physical_to_logical_page(doc: Any, p=None):
    if not p:
        p = doc.page
    return doc.logical_pages[p]


def logical_to_physical_page(doc: Any, lp=None):
    if not lp:
        lp = doc.logicalpage
    try:
        p = doc.logical_pages.index(str(lp))
    except ValueError:
        p = 0
    return p
