# Top 10 Improvements for pdfcat

**Ranked by Impact vs Effort**
**Created**: 2026-02-15

This document lists the top 10 improvements you can make to pdfcat, ranked by their impact-to-effort ratio. Each improvement includes estimated time, impact level, and implementation complexity.

---

## Scoring System

- **Impact**: Low (1) → High (5)
- **Effort**: Low (1) → High (5)
- **Score**: Impact / Effort (higher is better)

---

## 1. Vim-like Buffer Switching ⭐️ Score: 5.0

**Current**: `bb` to switch PDFs (confusing, requires two keypresses)
**Proposed**: `b` for next, `B` for previous, `3b` for jump forward 3

**Impact**: 5/5 - Used constantly when working with multiple PDFs
**Effort**: 1/5 - Simple keybinding change (~2-3 hours)
**Files**: `app.py`, `ui.py`, `constants.py`

### Why This Matters
Every time you work with multiple papers/documents, you'll feel this improvement. Current system is frustrating and non-intuitive.

### Implementation Complexity
- ✅ Simple: Just change keybinding logic
- ✅ Low risk: No core functionality changes
- ✅ Easy to test

---

## 2. Remove `_write_gr_cmd_with_response()` ⭐️ Score: 4.0

**Current**: Blocking stdin reads, potential threading issues
**Proposed**: Environment-based detection (like NativeRenderer)

**Impact**: 4/5 - Fixes potential hangs and threading bugs
**Effort**: 1/5 - Delete method, use env vars (~1-2 hours)
**Files**: `renderers.py`

### Why This Matters
Eliminates a source of bugs and simplifies the codebase. Makes rendering faster and more reliable.

### Implementation Complexity
- ✅ Very simple: Remove code + use env vars
- ✅ Zero risk: NativeRenderer already does this
- ✅ Immediate performance gain

---

## 3. Add Page Number in Status Bar ⭐️ Score: 4.0

**Current**: Status bar shows `[logical/total]` but not physical page
**Proposed**: Show both logical and physical page numbers

**Impact**: 4/5 - Constantly referenced when navigating
**Effort**: 1/5 - Small status bar change (~30 minutes)
**Files**: `ui.py`

### Example
```
Before: [v/42]
After:  [v/42] (p.15)
```

### Why This Matters
When working with PDFs that have roman numerals for front matter, you often need to know both the logical page (for citations) and physical page (for navigation).

### Implementation
```python
# In ui.py status_bar.update():
p_logical = doc.physical_to_logical_page()
p_physical = doc.page + 1
self.counter = f"[{p_logical}/{pc}] (p.{p_physical})"
```

---

## 4. Fix Command Injection Vulnerabilities 🔒 Score: 3.75

**Current**: `GUI_VIEWER` and file paths not sanitized
**Proposed**: Validate all external commands and paths

**Impact**: 5/5 - **CRITICAL SECURITY ISSUE**
**Effort**: 1.33/5 - ~4 hours to fix all instances
**Files**: `app.py`, new `security.py`

### Why This Matters
**Security vulnerability** - malicious PDFs or configs could execute arbitrary commands.

### What to Fix
1. `open_external_pdf_viewer()` - sanitize viewer command
2. `os.system()` calls - replace with `subprocess.run(shell=False)`
3. Note paths - validate against directory traversal

See PLAN.md Phase 0 for complete implementation.

---

## 5. Memory-Bounded Cache with LRU ⭐️ Score: 3.33

**Current**: Unlimited pixmap caching (can use 4.5GB for 200-page PDF!)
**Proposed**: LRU cache with 500MB limit

**Impact**: 5/5 - Prevents memory exhaustion
**Effort**: 1.5/5 - ~6 hours to implement properly
**Files**: New `cache.py`, `document.py`

### Why This Matters
Currently, opening large PDFs can consume all available RAM and crash the system. This makes pdfcat unusable for large documents.

### Implementation
- Create `PageRenderCache` class
- LRU eviction when memory limit reached
- Keep 10 most recent pages cached
- See PLAN.md Task 1.2 for full implementation

---

## 6. Search History with Arrow Keys ⭐️ Score: 3.0

**Current**: Search mode (`/`) doesn't remember previous searches
**Proposed**: Arrow up/down to cycle through search history

**Impact**: 3/5 - Quality of life for repeated searches
**Effort**: 1/5 - ~2-3 hours
**Files**: `app.py` (search_mode function)

### Why This Matters
When researching, you often search for the same terms multiple times across different papers.

### Implementation
```python
# Global search history
_search_history = []
_search_history_index = -1

def search_mode(doc, bar):
    # ... existing fzf setup ...

    # Add --history flag
    history_file = os.path.expanduser("~/.cache/pdfcat/search_history")
    os.makedirs(os.path.dirname(history_file), exist_ok=True)

    proc = subprocess.run([
        fzf_bin,
        "--history", history_file,  # ← Add this
        # ... rest of flags ...
    ])
```

Actually, `fzf` already supports this with the `--history` flag! Super easy.

---

## 7. Persistent Window Size/Position per PDF ⭐️ Score: 2.5

**Current**: Rotation, crop, tint saved; but not zoom level or layout
**Proposed**: Save and restore zoom/layout preferences per PDF

**Impact**: 5/5 - Different PDFs need different layouts
**Effort**: 2/5 - ~8 hours (state management changes)
**Files**: `document.py`, `core.py`

### Why This Matters
Academic papers need different zoom than textbooks. Comics need different layout than technical docs. Currently you have to reconfigure every time.

### What to Save
- Zoom level (papersize)
- Crop settings
- Rotation
- Tint/invert/alpha (already saved)
- **NEW**: Window size preference
- **NEW**: Fit-to-width vs fit-to-height preference

---

## 8. Bookmark System ⭐️ Score: 2.5

**Current**: Can only remember last page via cache
**Proposed**: Named bookmarks within document (`m` to mark, `'` to jump)

**Impact**: 5/5 - Super useful for research workflows
**Effort**: 2/5 - ~8 hours
**Files**: `document.py`, new storage in cache

### Why This Matters
When reading a 500-page textbook, you want to mark important pages and jump back to them quickly.

### Proposed Keybindings (Vim-style)
- `ma` - Mark current page as bookmark 'a'
- `'a` - Jump to bookmark 'a'
- `'` - List all bookmarks (fzf interface)
- `:marks` - Show bookmark list

### Storage
```python
# In cached state file:
{
    "bookmarks": {
        "a": 42,  # page number
        "b": 103,
        "t": 5,   # commonly used for table of contents
    }
}
```

---

## 9. Two-Page Spread Mode ⭐️ Score: 2.0

**Current**: Single page view only
**Proposed**: Side-by-side pages for books/comics

**Impact**: 4/5 - Essential for reading books naturally
**Effort**: 2/5 - ~10 hours (rendering complexity)
**Files**: `document.py`, `renderers.py`

### Why This Matters
Books are meant to be read as spreads. Comics especially need this. Currently you have to mentally stitch pages together.

### Implementation Considerations
- Toggle with `2` key (like Zathura)
- Odd pages on right, even on left
- Handle single-page mode and spread mode
- Crop both pages to same height
- Center spread on screen

### Challenges
- Rendering two pages efficiently
- Cache invalidation for both pages
- Navigation (next spread vs next page)

---

## 10. Copy Selected Text to Clipboard ⭐️ Score: 2.0

**Current**: Visual mode `S` highlights text but you can't copy easily
**Proposed**: `y` in visual mode copies selected text

**Impact**: 4/5 - Constantly need to quote PDFs
**Effort**: 2/5 - ~10 hours (text extraction complexity)
**Files**: `ui.py`, `document.py`

### Why This Matters
When writing papers, you need to copy quotes, definitions, equations. Current workflow requires opening PDF in another app.

### Current Workaround
1. Enter visual mode with `S`
2. Select region
3. Press `y` → copies to clipboard
4. Paste into notes

### Implementation
Already partially implemented in `get_selected_text_rows()`, just need to:
- Make `y` key work more reliably
- Add visual feedback (flash selection?)
- Copy to system clipboard (already uses `pyperclip`)
- Show confirmation in status bar

Actually, looking at the code (`ui.py:287-296`), this already works! Just needs better documentation and maybe a visual confirmation.

---

## Honorable Mentions

These didn't make top 10 but are worth considering:

### 11. Fuzzy File Opener (Score: 1.67)
**Impact**: 5/5 | **Effort**: 3/5
Open PDFs from command palette with fuzzy search through recent files

### 12. PDF Annotations Support (Score: 1.25)
**Impact**: 5/5 | **Effort**: 4/5
Highlight, underline, add notes directly in PDF (saves to file)

### 13. Table of Contents Auto-Generation (Score: 1.67)
**Impact**: 5/5 | **Effort**: 3/5
Generate TOC from headings if PDF lacks one

### 14. Split View (Horizontal/Vertical) (Score: 1.0)
**Impact**: 4/5 | **Effort**: 4/5
View two parts of same PDF simultaneously

### 15. OCR for Scanned PDFs (Score: 0.8)
**Impact**: 4/5 | **Effort**: 5/5
Extract text from image-based PDFs using tesseract

---

## Implementation Priority

Based on score and dependencies, here's the recommended order:

### Week 1: Quick Wins (Days 1-2)
1. ✅ **Vim-like buffer switching** (3 hours)
2. ✅ **Remove `_write_gr_cmd_with_response()`** (2 hours)
3. ✅ **Page number in status bar** (30 minutes)
4. ✅ **Search history** (1 hour)

**Total**: ~1.5 days, massive UX improvement

### Week 2: Security & Stability (Days 3-5)
5. ✅ **Command injection fixes** (1 day)
6. ✅ **Memory-bounded cache** (1.5 days)

**Total**: 2.5 days, production-ready security

### Week 3: Features (Days 6-10)
7. ✅ **Persistent layout per PDF** (1 day)
8. ✅ **Bookmark system** (1 day)
9. ✅ **Two-page spread mode** (1.5 days)
10. ✅ **Text copying improvements** (0.5 days)

**Total**: 4 days, major feature additions

---

## Detailed Breakdown by Category

### 🚀 **Quick Wins** (< 4 hours each)
1. Vim-like buffer switching
2. Remove `_write_gr_cmd_with_response()`
3. Page number in status bar
6. Search history with arrow keys

### 🔒 **Security** (Critical but moderate effort)
4. Command injection fixes

### 💾 **Stability** (Prevents crashes)
5. Memory-bounded cache

### ✨ **Features** (High value, higher effort)
7. Persistent window size/position
8. Bookmark system
9. Two-page spread mode
10. Copy selected text

---

## Quick Reference Table

| # | Improvement | Impact | Effort | Score | Time |
|---|------------|--------|--------|-------|------|
| 1 | Vim buffer switching | 5 | 1 | 5.0 | 3h |
| 2 | Remove blocking reads | 4 | 1 | 4.0 | 2h |
| 3 | Page # in status bar | 4 | 1 | 4.0 | 30m |
| 4 | Security fixes | 5 | 1.33 | 3.75 | 4h |
| 5 | Memory-bounded cache | 5 | 1.5 | 3.33 | 6h |
| 6 | Search history | 3 | 1 | 3.0 | 2h |
| 7 | Persistent layout | 5 | 2 | 2.5 | 8h |
| 8 | Bookmarks | 5 | 2 | 2.5 | 8h |
| 9 | Two-page spread | 4 | 2 | 2.0 | 10h |
| 10 | Copy text polish | 4 | 2 | 2.0 | 10h |

---

## My Recommendation

Start with the **Week 1 Quick Wins** (items 1-3, 6):

1. **Vim buffer switching** - You'll use this every day
2. **Remove blocking reads** - Eliminates potential bugs
3. **Page number in status bar** - Constant quality of life
4. **Search history** - Makes research workflows better

**Total time**: ~6.5 hours
**Impact**: Immediately noticeable, pdfcat feels much more polished

Then move to **Week 2 Security** (items 4-5):
- These are critical for production use
- Prevents crashes and security issues
- Makes pdfcat safe to recommend to others

**Which would you like to tackle first?** I'd recommend starting with #1 (Vim buffer switching) since it's high-impact and you already expressed interest in it!
