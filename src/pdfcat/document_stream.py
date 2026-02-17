"""Document live-text streaming helpers."""

from __future__ import annotations

import logging
import threading
from typing import Any

import fitz

from .tempfiles import get_temp_file_manager


def stop_live_text_stream(doc: Any) -> None:
    """Stop and cleanup active live text stream resources for a document."""
    if doc._search_stream_stop_event is not None:
        doc._search_stream_stop_event.set()

    if doc._search_stream_thread is not None and doc._search_stream_thread.is_alive():
        try:
            doc._search_stream_thread.join(timeout=0.3)
        except Exception as exc:
            logging.warning("Failed to join search stream thread: %s", exc)

    doc._search_stream_thread = None
    doc._search_stream_stop_event = None
    doc._search_stream_done = False

    if doc._search_stream_path is not None:
        manager = get_temp_file_manager(doc._get_context())
        manager.cleanup_path(doc._search_stream_path)
    doc._search_stream_path = None


def start_live_text_stream(doc: Any) -> str | None:
    """Start asynchronous page-text streaming to a temporary TSV file."""
    stop_live_text_stream(doc)

    stop_event = threading.Event()
    doc._search_stream_stop_event = stop_event
    doc._search_stream_done = False

    logical_pages = [str(lp) for lp in doc.logical_pages]
    start_page = int(doc.page or 0)
    page_order = list(range(start_page, doc.pages + 1)) + list(range(0, start_page))
    manager = get_temp_file_manager(doc._get_context())
    with manager.temp_file(suffix=".tsv", prefix="pdfcat-search-") as (tmp_path, _tmp):
        doc._search_stream_path = tmp_path

    stream_path = doc._search_stream_path
    if stream_path is None:
        return None
    filename = doc.filename

    def worker() -> None:
        try:
            with (
                fitz.open(filename) as search_doc,
                open(stream_path, "a", encoding="utf-8", buffering=1) as out,
            ):
                for p in page_order:
                    if stop_event.is_set():
                        break

                    try:
                        page = search_doc.load_page(p)
                        try:
                            text = page.get_text("text", sort=True)
                        except TypeError:
                            text = page.get_text("text")
                    except Exception:
                        continue

                    if not text:
                        continue

                    for raw_line in text.splitlines():
                        if stop_event.is_set():
                            break
                        line = " ".join(raw_line.split()).strip()
                        if line == "":
                            continue
                        physical = str(p + 1)
                        logical = (
                            logical_pages[p] if p < len(logical_pages) else physical
                        )
                        out.write(f"{physical}\t{logical}\t{line}\n")

                    try:
                        out.flush()
                    except Exception:
                        pass
        except Exception as exc:
            logging.debug("Search stream worker failed: %s", exc)
        finally:
            doc._search_stream_done = True

    thread = threading.Thread(target=worker, daemon=True, name="SearchTextStream")
    doc._search_stream_thread = thread
    thread.start()
    return doc._search_stream_path
