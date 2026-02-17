"""Document rendering and geometry helpers."""

from __future__ import annotations

import re
from itertools import groupby
from operator import itemgetter
from typing import Any

import fitz

from .tinting import terminal_theme_rgb, tint_pixmap_duotone


def resolve_tint_colors(doc: Any):
    """Return (fg_rgb, bg_rgb) for current tint mode."""
    tint_name = str(doc.tint_color).lower()
    if tint_name == "terminal":
        return terminal_theme_rgb()

    if tint_name in doc._named_tint_rgb_cache:
        return doc._named_tint_rgb_cache[tint_name]

    tint = fitz.utils.getColor(doc.tint_color)
    bg_rgb = (
        int(tint[0] * 255),
        int(tint[1] * 255),
        int(tint[2] * 255),
    )
    fg_rgb = (0, 0, 0)
    pair = (fg_rgb, bg_rgb)
    doc._named_tint_rgb_cache[tint_name] = pair
    return pair


def clear_page(doc: Any, p) -> None:
    renderer = doc._renderer()
    if renderer is not None:
        renderer.clear_image(p)


def cell_coords_to_pixels(doc: Any, *coords):
    screen = doc._screen()
    if screen is None:
        return []
    factor = doc.page_states[doc.page].factor
    left, top, _, _ = doc.page_states[doc.page].place
    pix_coords = []
    for coord in coords:
        col = coord[0]
        row = coord[1]
        x = (col - left) * screen.cell_width / factor
        y = (row - top) * screen.cell_height / factor
        pix_coords.append((x, y))
    return pix_coords


def pixel_coords_to_cells(doc: Any, *coords):
    screen = doc._screen()
    if screen is None:
        return []
    factor = doc.page_states[doc.page].factor
    left, top, _, _ = doc.page_states[doc.page].place
    cell_coords = []
    for coord in coords:
        x = coord[0]
        y = coord[1]
        col = (x * factor + left * screen.cell_width) / screen.cell_width
        row = (y * factor + top * screen.cell_height) / screen.cell_height
        col = int(col)
        row = int(row)
        cell_coords.append((col, row))
    return cell_coords


def get_text_in_rect(doc: Any, rect):
    """Get text that is inside a Rect."""
    page = doc.load_page(doc.page)
    words = page.get_text_words()
    mywords = [w for w in words if fitz.Rect(w[:4]) in rect]
    mywords.sort(key=itemgetter(3, 0))  # sort by y1, x0 of the word rect
    grouped_words = groupby(mywords, key=itemgetter(3))
    text = []
    for _y1, gwords in grouped_words:
        text = text + [" ".join(w[4] for w in gwords)]
    return text


def get_text_intersecting_rect(doc: Any, rect):
    """Get text that intersects a Rect."""
    page = doc.load_page(doc.page)
    words = page.get_text_words()
    mywords = [w for w in words if fitz.Rect(w[:4]).intersects(rect)]
    mywords.sort(key=itemgetter(3, 0))  # sort by y1, x0 of the word rect
    grouped_words = groupby(mywords, key=itemgetter(3))
    text = []
    for _y1, gwords in grouped_words:
        text = text + [" ".join(w[4] for w in gwords)]
    return text


def search_text(doc: Any, string) -> str:
    for p in range(doc.page, doc.pages):
        page_text = doc.get_page_text(p, "text")
        if re.search(string, page_text):
            doc.goto_page(p)
            return "match on page"
    return "no matches"


def auto_crop(doc: Any, page):
    blocks = page.get_text_blocks()

    if len(blocks) > 0:
        crop = fitz.Rect(blocks[0][:4])
    else:
        # don't try to crop empty pages
        crop = fitz.Rect(0, 0, 0, 0)
    for block in blocks:
        b = fitz.Rect(block[:4])
        crop = crop | b

    return crop


def display_page(doc: Any, bar, p, display: bool = True) -> None:
    screen = doc._screen()
    config = doc._config()
    renderer = doc._renderer()
    if screen is None or renderer is None:
        bar.message = "renderer unavailable"
        return

    page = doc.load_page(p)
    page_state = doc.page_states[p]

    if doc.manualcrop and doc.manualcroprect != [None, None] and doc.is_pdf:
        page.set_cropbox(fitz.Rect(doc.manualcroprect[0], doc.manualcroprect[1]))

    elif doc.autocrop and doc.is_pdf:
        page.set_cropbox(page.mediabox)
        crop = auto_crop(doc, page)
        page.set_cropbox(crop)

    elif doc.is_pdf:
        page.set_cropbox(page.mediabox)

    dw = screen.width
    status_rows = 1 if bool(getattr(config, "SHOW_STATUS_BAR", True)) else 0
    # Available height = total height - status bar height (if shown)
    dh = screen.height - (screen.cell_height * status_rows)

    if doc.rotation in [0, 180]:
        pw = page.bound().width
        ph = page.bound().height
    else:
        pw = page.bound().height
        ph = page.bound().width

    # calculate zoom factor
    fx = dw / pw
    fy = dh / ph
    factor = min(fx, fy)
    page_state.factor = factor

    # calculate zoomed dimensions
    zw = factor * pw
    zh = factor * ph

    # Center in terminal cells (pane space), not raw pixels.
    # This avoids mis-centering in environments where pixel metrics are unreliable.
    max_cols = max(1, screen.cols)
    max_rows = max(1, screen.rows - status_rows)

    page_cols = max(1, int(round(zw / screen.cell_width)))
    page_rows = max(1, int(round(zh / screen.cell_height)))

    page_cols = min(max_cols, page_cols)
    page_rows = min(max_rows, page_rows)

    l_col = ((max_cols - page_cols) // 2) + 1
    t_row = (max_rows - page_rows) // 2
    r_col = l_col + page_cols
    b_row = t_row + page_rows
    place = (l_col, t_row, r_col, b_row)
    page_state.place = place

    # move cursor to place
    screen.set_cursor(l_col, t_row)

    # Render page if stale or if we need to display
    if page_state.stale or display:
        # get zoomed and rotated pixmap
        mat = fitz.Matrix(factor, factor)
        mat = mat.prerotate(doc.rotation)

        entry = doc._render_cache.get(p)
        cache_hit = bool(entry and entry.matrix == mat)
        if cache_hit and entry is not None:
            pix = entry.pixmap
            page_state.set_cached_render(entry.pixmap, entry.matrix)
            page_state.set_cached_ppm(entry.ppm)
        else:
            pix = page.get_pixmap(matrix=mat, alpha=doc.alpha)
            doc._render_cache.put(p, pix, mat)
            doc._prune_page_state_caches()
            page_state.set_cached_render(pix, mat)
            page_state.set_cached_ppm(None)
            page_state.set_cached_visual_key(None)

        tint_fg_bg = None
        if doc.tint:
            tint_fg_bg = resolve_tint_colors(doc)
        visual_key = (
            bool(doc.invert),
            bool(doc.tint),
            str(doc.tint_color).lower() if doc.tint else "",
            tint_fg_bg[0] if tint_fg_bg else None,
            tint_fg_bg[1] if tint_fg_bg else None,
        )
        cached_ppm = page_state.get_cached_ppm()
        cached_visual_key = page_state.get_cached_visual_key()
        visual_cache_hit = cache_hit and cached_ppm is not None and cached_visual_key == visual_key

        if not visual_cache_hit:
            # Copy before transformations: keep base cached_pixmap immutable.
            if doc.invert or doc.tint:
                pix = fitz.Pixmap(pix)

            if doc.invert:
                pix.invert_irect()

            if doc.tint and tint_fg_bg:
                fg_rgb, bg_rgb = tint_fg_bg
                pix = tint_pixmap_duotone(pix, fg_rgb, bg_rgb)

            page_state.set_cached_ppm(None)  # Regenerate encoded payload for this visual mode.

        # Only clear first for renderers that require destructive redraws.
        if getattr(renderer, "requires_clear_before_render", False):
            renderer.clear_image(p)

        # Render the pixmap to screen (renderer will use cached PPM if available)
        success = renderer.render_pixmap(pix, p, place, screen, page_state)
        if not success:
            page_state.stale = True
            bar.message = "failed to load page " + str(p + 1)
        else:
            page_state.stale = False
            page_state.set_cached_visual_key(visual_key)

    # Always update status bar at end (only once per call)
    bar.update(doc)
    screen.drain_input()

    # Trigger background pre-rendering of adjacent pages for faster navigation
    shutdown_event = doc._shutdown_event()
    if shutdown_event is None or not shutdown_event.is_set():
        worker_pool = doc._worker_pool()
        prerender_callback = doc._prerender_callback()
        if worker_pool is not None and callable(prerender_callback):
            worker_pool.submit(prerender_callback, doc, p)
