"""Project metadata and CLI help text."""

__version__ = "0.0.1"
__license__ = "MIT"
__copyright__ = "Copyright (c) 2026"
__author__ = "Marcos Romero Lamas"
__url__ = "https://github.com/marromlam/pdfcat"

USAGE = """\
Usage:
    pdfcat [options] example.pdf

Options:
    -p n, --page-number n : open to physical page n (1-based)
    -f n, --first-page n : set logical page number for page 1 to n
    --citekey key : associate file with bibtex citekey
    -o, --open citekey : open file associated with bibtex entry with citekey
    --nvim-listen-address path : path to nvim msgpack server
    --ignore-cache : ignore saved settings for files
    --force-tinted : force tinted mode (tint+invert+alpha), ignoring saved visual settings
    --force-original : force original mode (no tint/invert/alpha), ignoring saved visual settings
    --hide-status-bar : hide pdfcat status bar
    -v, --version
    -h, --help
"""

VIEWER_SHORTCUTS = """\
Keys:
    j, down, space: forward [count] pages
    k, up:          back [count] pages
    l, right:       forward [count] sections
    h, left:        back [count] sections
    gg:             go to beginning of document
    G:              go to end of document
    [count]G:       go to logical page [count]
    [count]J:       go to physical page [count]
    b:              next open document
    [count]b:       next [count] open documents
    B:              previous open document
    [count]B:       previous [count] open documents
    /:              live search (ripgrep/fzf)
    s:              open current page as text in minimal Neovim
    S:              visual mode
    t:              table of contents
    M:              show metadata
    f:              follow link hint (Vimium-style)
    F:              open full link list in fzf (fallback to in-terminal list)
    r:              rotate [count] quarter turns clockwise
    R:              rotate [count] quarter turns counterclockwise
    c:              toggle autocropping of margins
    n:              open document note in Neovim
    a:              copy page link and open document note in Neovim
    A:              toggle alpha transparency
    i:              invert colors
    d:              darken using TINT_COLOR
    z:              toggle autoplay ([count]z sets fps)
    E:              set autoplay end page ([count]E, 0E clears to doc end)
    P:              toggle presenter mode
    O:              open in external system PDF viewer
    [count]P:       Set logical page number of current page to count
    -:              zoom out (reflowable only)
    +:              zoom in (reflowable only)
    ctrl-r:         refresh
    (in / search) ctrl-r: ripgrep mode, ctrl-f: fzf mode
    ctrl-s:         reverse SyncTeX (PDF -> source in Neovim)
    ?:              show keybinds
    q:              quit
"""
