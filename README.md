# pdfcat

`pdfcat` is a keyboard-first PDF reader for terminal workflows.

It is built for people who already live in `kitty` + `tmux` + `nvim` and want a fast reader without context switching to a GUI.
![](assets/screenshot.png)

## What pdfcat is good at

- Fast navigation with logical and physical page jumps.
- Search that feels like terminal tooling, not a modal dialog.
- Link following from the keyboard (`f` hints, `F` full list via `fzf`).
- Notes workflow tied to each PDF (`n` and `a`).
- Reverse SyncTeX (`Ctrl-S`) from PDF page to source.
- Multi-document sessions with quick switching (`b` / `B`).
- Presenter mode (`P`) with a synced second window.
- Visual controls for late-night reading (`d`, `i`, `A`, crop, rotate).

## Installation

### Homebrew

Install via tap:

```bash
brew tap marromlam/pdfcat
brew install marromlam/pdfcat/pdfcat
```

Optional tools (recommended):

```bash
brew install timg
brew install fzf ripgrep neovim tmux
```

### pip

```bash
git clone https://github.com/marromlam/pdfcat
cd pdfcat
pip install .
```

## Quick start

```bash
pdfcat paper.pdf
pdfcat -p 10 paper.pdf
pdfcat --force-tinted paper.pdf
pdfcat --force-original --hide-status-bar paper.pdf
```

If your `BIBTEX` config is set:

```bash
pdfcat --open knuth1984
```

## Core keybindings

### Movement

- `j`, `k`, `space`, arrows`: move pages/sections
- `gg`, `G`: start/end
- `[count]G`: go to logical page
- `[count]J`: go to physical page
- `b`, `B`: cycle open documents
- `p`: jump to previous page

### Search and links

- `/`: live search UI
- `Ctrl-R` in search: ripgrep mode
- `Ctrl-F` in search: fzf mode
- `f`: link hint mode (Vimium-style)
- `F`: full link list through `fzf`

### Notes and source sync

- `s`: open current page text in minimal Neovim
- `S`: visual selection mode
- `n`: open the note file for this PDF
- `a`: copy page reference and open note
- `Ctrl-S`: reverse SyncTeX (PDF -> source in Neovim)

### View and utility

- `d`: tint toggle
- `i`: invert toggle
- `A`: alpha toggle
- `c`: crop mode cycle
- `r`, `R`: rotate
- `P`: presenter mode
- `O`: open in system PDF viewer
- `?`: show keybind help
- `q`: quit

## CLI options

- `-p n`, `--page-number n`: open on physical page `n` (1-based)
- `-f n`, `--first-page n`: set logical numbering offset
- `--citekey key`: associate current file with citekey
- `-o`, `--open key`: open by citekey from bibtex
- `--nvim-listen-address path`: Neovim RPC socket path
- `--ignore-cache`: ignore saved per-document state
- `--force-tinted`: force `tint + invert + alpha`, ignore saved visual state
- `--force-original`: force no tint/invert/alpha, ignore saved visual state
- `--hide-status-bar`: hide status bar
- `-v`, `--version`
- `-h`, `--help`

## Config file

`pdfcat` reads JSON config from:

```text
~/.config/pdfcat/config
```

Example:

```json
{
  "TINT_COLOR": "antiquewhite",
  "SHOW_STATUS_BAR": true,
  "AUTOPLAY_FPS": 8,
  "AUTOPLAY_LOOP": true,
  "AUTOPLAY_END_PAGE": null,
  "BIBTEX": "/Users/me/references/library.bib",
  "NOTES_DIR": "/Users/me/notes",
  "KITTYCMD": "kitty --single-instance --instance-group=1",
  "GUI_VIEWER": "system"
}
```

Per-document state is cached under `~/.cache/pdfcat` by default.
