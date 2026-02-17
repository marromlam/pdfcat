# 10 New Features for pdfcat (Not in Current Plans)

**Beyond Refactoring - Feature Enhancements**
**Created**: 2026-02-15

This document lists 10 new features and improvements that are NOT covered in PLAN.md, PLAN2.md, or the refactoring work. These are net-new capabilities that would enhance pdfcat's functionality.

---

## Scoring System

- **Impact**: Low (1) → High (5) - How much does this improve the user experience?
- **Effort**: Low (1) → High (5) - How hard is it to implement?
- **Score**: Impact / Effort (higher is better)
- **Category**: UX | Integration | Performance | Feature

---

## 1. PDF Annotations & Highlighting ⭐️ Score: 4.0

**Category**: Feature
**Impact**: 5/5 | **Effort**: 1.25/5 | **Time**: ~6 hours

### What It Does
Add, edit, and save highlights, underlines, and text annotations directly in PDFs.

### Current Gap
You can VIEW PDFs but can't mark them up. Need to switch to external tools for annotations.

### Proposed Workflow
```
In pdfcat:
- `S` - Enter visual selection mode (already exists)
- Select text with j/k
- `h` - Highlight selection (yellow)
- `u` - Underline selection
- `n` - Add text note at cursor
- `da` - Delete annotation under cursor
```

### Implementation
```python
# Use PyMuPDF's annotation API
import fitz

def add_highlight(doc, page_num, rect, color="yellow"):
    """Add highlight annotation to PDF."""
    page = doc.load_page(page_num)

    # Create highlight annotation
    highlight = page.add_highlight_annot(rect)

    # Set color
    if color == "yellow":
        highlight.set_colors({"stroke": (1, 1, 0)})
    elif color == "green":
        highlight.set_colors({"stroke": (0, 1, 0)})

    highlight.update()

    # Save changes
    doc.saveIncr()  # Incremental save preserves original
```

### Storage
Annotations are saved **in the PDF file itself** (standard PDF annotations), so they're visible in any PDF reader.

### Why This Matters
- ✅ No need to switch to external apps for markup
- ✅ Annotations sync with the PDF (not separate files)
- ✅ Works with existing PDF annotation standards
- ✅ Essential for research/study workflows

---

## 2. Table of Contents Auto-Generation ⭐️ Score: 3.33

**Category**: Feature
**Impact**: 5/5 | **Effort**: 1.5/5 | **Time**: ~8 hours

### What It Does
Automatically generate a table of contents for PDFs that don't have one, using font size/style heuristics.

### Current Gap
Many PDFs (especially scanned books, papers) lack proper TOC metadata. Press `t` and get "No ToC available".

### Proposed Workflow
```
Press `T` (shift-t) to auto-generate TOC:
1. Analyze document for heading patterns
2. Detect chapters/sections by font size
3. Build clickable TOC
4. Optionally save to PDF metadata
```

### Implementation
```python
def auto_generate_toc(doc):
    """Generate TOC from document structure."""
    toc_entries = []

    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                for span in line["spans"]:
                    # Detect headings by font size
                    font_size = span["size"]
                    text = span["text"].strip()

                    # Chapter heading (large font)
                    if font_size > 18 and len(text) > 3:
                        toc_entries.append([1, text, page_num + 1])

                    # Section heading (medium font)
                    elif font_size > 14 and len(text) > 3:
                        toc_entries.append([2, text, page_num + 1])

    # Remove duplicates, clean up
    return deduplicate_toc(toc_entries)
```

### Advanced: ML-Based Detection
Use patterns to detect:
- Numbered sections (1.1, 1.2, etc.)
- All-caps headings
- Bold text at start of page
- Consistent spacing patterns

### Why This Matters
- ✅ Makes poorly-formatted PDFs navigable
- ✅ Essential for scanned books/papers
- ✅ Can export TOC to share with others

---

## 3. Fuzzy File Opener (Recent Files + Full Library) ⭐️ Score: 2.5

**Category**: UX
**Impact**: 5/5 | **Effort**: 2/5 | **Time**: ~10 hours

### What It Does
Press `O` (shift-o) to open fuzzy finder for:
- Recent PDFs
- PDFs in configured directories
- PDFs from BibTeX library

### Current Gap
Can only open PDFs via command line. No way to quickly switch to a different document while in pdfcat.

### Proposed Workflow
```
Press `O`:
┌─────────────────────────────────────────────────────┐
│ Open PDF (fuzzy search)                             │
├─────────────────────────────────────────────────────┤
│ > paper.pdf (recently viewed)                       │
│   thesis-chapter-3.pdf (recently viewed)            │
│   knuth1984 - The TeXbook (from bibtex)            │
│   ~/Documents/textbook.pdf                          │
│   ~/Papers/quantum-computing.pdf                    │
└─────────────────────────────────────────────────────┘
```

### Implementation
```python
def fuzzy_open_file(ctx):
    """Open file with fuzzy finder."""

    # Build file list
    files = []

    # 1. Recent files (from cache)
    recent = get_recent_files(limit=20)
    for path in recent:
        files.append(("recent", os.path.basename(path), path))

    # 2. BibTeX library
    if ctx.config.BIBTEX:
        bib_entries = load_bibtex_entries(ctx.config.BIBTEX)
        for key, entry in bib_entries.items():
            if "File" in entry.fields:
                files.append(("bibtex", f"{key} - {entry.fields['title']}",
                            entry.fields["File"]))

    # 3. Configured directories
    if hasattr(ctx.config, "PDF_DIRS"):
        for pdf_dir in ctx.config.PDF_DIRS:
            for pdf_path in glob.glob(f"{pdf_dir}/**/*.pdf", recursive=True):
                files.append(("dir", os.path.basename(pdf_path), pdf_path))

    # Format for fzf
    fzf_input = "\n".join([f"{source}\t{name}\t{path}"
                          for source, name, path in files])

    # Run fzf
    proc = subprocess.run(
        ["fzf", "--prompt", "Open PDF> ", "--delimiter", "\t", "--with-nth", "2"],
        input=fzf_input,
        capture_output=True,
        text=True,
    )

    if proc.returncode == 0:
        # Extract path from selection
        selected = proc.stdout.strip()
        path = selected.split("\t")[2]

        # Open in new buffer
        return open_pdf_in_buffer(ctx, path)
```

### Configuration
```json
{
  "PDF_DIRS": [
    "~/Documents/Papers",
    "~/Dropbox/Reading",
    "~/Library/Books"
  ],
  "RECENT_FILES_LIMIT": 50
}
```

### Why This Matters
- ✅ Never leave pdfcat to open another PDF
- ✅ Quick access to your entire library
- ✅ Recent files at your fingertips
- ✅ BibTeX integration for research

---

## 4. Two-Page Spread Mode (Book Layout) ⭐️ Score: 2.0

**Category**: Feature
**Impact**: 5/5 | **Effort**: 2.5/5 | **Time**: ~12 hours

### What It Does
View two pages side-by-side, like a physical book spread.

### Current Gap
Single-page view only. Books and comics are meant to be read as spreads.

### Proposed Workflow
```
Press `2` to toggle spread mode:

Single page:          Two-page spread:
┌──────────┐         ┌──────────┬──────────┐
│          │         │          │          │
│  Page 5  │   →     │  Page 4  │  Page 5  │
│          │         │  (even)  │  (odd)   │
└──────────┘         └──────────┴──────────┘
```

### Implementation Challenges
```python
class SpreadRenderer:
    """Render two pages side-by-side."""

    def render_spread(self, doc, left_page_num, right_page_num):
        """Render two pages as a spread."""

        # Load both pages
        left_page = doc.load_page(left_page_num)
        right_page = doc.load_page(right_page_num)

        # Calculate combined dimensions
        left_rect = left_page.rect
        right_rect = right_page.rect

        # Make heights equal (scale to match)
        target_height = max(left_rect.height, right_rect.height)

        # Render both pages
        left_pix = left_page.get_pixmap(...)
        right_pix = right_page.get_pixmap(...)

        # Combine into single image
        combined_width = left_pix.width + right_pix.width
        combined_pix = stitch_horizontal(left_pix, right_pix)

        # Render to screen
        return combined_pix
```

### Keybindings
- `2` - Toggle two-page mode
- `j` in spread mode - Next spread (advance 2 pages)
- `k` in spread mode - Previous spread (back 2 pages)
- `l` - Single page forward (for asymmetric navigation)

### Advanced Features
- First page alone (cover page)
- Reverse mode for manga (right-to-left)
- Crop both pages to same aspect ratio

### Why This Matters
- ✅ Natural reading experience for books
- ✅ Essential for comics/manga
- ✅ See chapter context (heading on left, content on right)

---

## 5. Presentation Mode (Full Screen + Pointer) ⭐️ Score: 2.0

**Category**: Feature
**Impact**: 4/5 | **Effort**: 2/5 | **Time**: ~10 hours

### What It Does
Full-screen presentation mode with on-screen pointer/spotlight for teaching/presenting.

### Current Gap
Presenter mode (`P`) creates second window, but no drawing tools or spotlight.

### Proposed Workflow
```
Press `p` (lowercase) to enter presentation mode:
- Full screen (hide status bar)
- Laser pointer (mouse cursor becomes red dot)
- Drawing mode (annotate on-screen, don't save to PDF)
- Timer (show elapsed time)
```

### Keybindings in Presentation Mode
- `p` - Toggle presentation mode
- `d` - Toggle drawing mode (draw with mouse/trackpad)
- `c` - Clear drawings
- `l` - Toggle laser pointer
- `t` - Toggle timer
- `b` - Black screen (pause)
- `w` - White screen (pause)

### Implementation
```python
class PresentationMode:
    """Full-screen presentation mode with annotations."""

    def __init__(self, doc) -> None:
        self.doc = doc
        self.drawings = []  # Temporary annotations
        self.laser_enabled = False
        self.timer_start = None
        self.blacked_out = False

    def draw_laser_pointer(self, x, y):
        """Draw red dot at cursor position."""
        # Overlay red circle at mouse position
        sys.stdout.write(f"\033[{y};{x}H\033[41m  \033[0m")

    def add_drawing(self, points, color="red"):
        """Add temporary drawing annotation."""
        self.drawings.append({
            "points": points,
            "color": color,
            "page": self.doc.page,
        })

    def render_with_overlays(self):
        """Render page with presentation overlays."""
        # Render base page
        self.doc.display_page(...)

        # Draw annotations
        for drawing in self.drawings:
            if drawing["page"] == self.doc.page:
                self.render_drawing(drawing)

        # Draw laser pointer
        if self.laser_enabled:
            mouse_pos = get_mouse_position()
            self.draw_laser_pointer(*mouse_pos)

        # Draw timer
        if self.timer_start:
            elapsed = time.time() - self.timer_start
            self.draw_timer(elapsed)
```

### Advanced Features
- Export drawings as overlay PDF
- Screen recording integration
- Zoom to region (like macOS zoom)

### Why This Matters
- ✅ Teach from terminal without external tools
- ✅ Present papers at conferences
- ✅ No need for PowerPoint export

---

## 6. Incremental Search (Live Search as You Type) ⭐️ Score: 2.5

**Category**: UX
**Impact**: 5/5 | **Effort**: 2/5 | **Time**: ~10 hours

### What It Does
Search jumps to matches as you type (like Vim's `incsearch`), instead of waiting for full query.

### Current Gap
Press `/` → opens fzf → type full query → see results. No live feedback.

### Proposed Workflow
```
Press `/`:
Type: "quan"
  → Immediately jumps to first match on current page
Type: "t" (now "quant")
  → Updates to first "quant" match
Press `n` → next match
Press `N` → previous match
Press ESC → cancel, return to original page
Press Enter → accept, stay at current match
```

### Implementation
```python
def incremental_search(doc, bar):
    """Live search as you type."""
    original_page = doc.page
    query = ""
    current_match_idx = 0
    all_matches = []

    state.scr.kb_input.activate()

    while True:
        # Show search prompt
        bar.message = f"Search: {query}_"
        bar.update(doc)

        key = state.scr.kb_input.getch(timeout=None)

        if key == 27:  # ESC - cancel
            doc.goto_page(original_page)
            return

        elif key == 10:  # Enter - accept
            bar.message = f"Found: {query}"
            return

        elif key in (127, 8):  # Backspace
            query = query[:-1]

        elif key == ord('n'):  # Next match
            current_match_idx = (current_match_idx + 1) % len(all_matches)
            if all_matches:
                doc.goto_page(all_matches[current_match_idx]["page"])
            continue

        elif key == ord('N'):  # Previous match
            current_match_idx = (current_match_idx - 1) % len(all_matches)
            if all_matches:
                doc.goto_page(all_matches[current_match_idx]["page"])
            continue

        elif 32 <= key <= 126:  # Printable char
            query += chr(key)

        # Update search results
        all_matches = search_document(doc, query)

        # Jump to first match
        if all_matches:
            current_match_idx = 0
            doc.goto_page(all_matches[0]["page"])
            # TODO: Highlight match on page
```

### Visual Feedback
Highlight matching text on current page (like less/vim):
```python
def highlight_matches(doc, query):
    """Highlight search matches on current page."""
    page = doc.load_page(doc.page)

    # Find all instances
    instances = page.search_for(query)

    # Draw yellow rectangles around matches
    for inst in instances:
        # Convert to screen coordinates
        # Draw highlight overlay
        pass
```

### Why This Matters
- ✅ Much faster than fzf for quick searches
- ✅ Immediate visual feedback
- ✅ Familiar Vim-style workflow
- ✅ No context switching to external tool

---

## 7. Session Management (Save/Restore Workspace) ⭐️ Score: 2.0

**Category**: Feature
**Impact**: 4/5 | **Effort**: 2/5 | **Time**: ~10 hours

### What It Does
Save and restore entire workspace: all open PDFs, pages, layouts, notes.

### Current Gap
Quit pdfcat → lose all open documents and positions. Have to manually reopen everything.

### Proposed Workflow
```
Working on thesis with 5 papers open:
- paper1.pdf at page 42
- paper2.pdf at page 15
- thesis-draft.pdf at page 3
- reference.pdf at page 100
- notes.pdf at page 1

Press `:w thesis-session` → saves workspace

Tomorrow:
pdfcat --session thesis-session
  → Restores all 5 PDFs at exact pages
```

### Implementation
```python
class SessionManager:
    """Save and restore pdfcat sessions."""

    def save_session(self, name, ctx):
        """Save current workspace to session file."""
        session = {
            "version": 1,
            "created": datetime.now().isoformat(),
            "documents": [],
            "current_buffer": ctx.buffers.current,
        }

        # Save state of each open document
        for doc in ctx.buffers.docs:
            session["documents"].append({
                "path": doc.filename,
                "page": doc.page,
                "logical_page": doc.logicalpage,
                "rotation": doc.rotation,
                "zoom": doc.papersize,
                "tint": doc.tint,
                "invert": doc.invert,
                "alpha": doc.alpha,
                "citekey": doc.citekey,
            })

        # Save to file
        session_file = os.path.expanduser(f"~/.config/pdfcat/sessions/{name}.json")
        os.makedirs(os.path.dirname(session_file), exist_ok=True)

        with open(session_file, "w") as f:
            json.dump(session, f, indent=2)

    def load_session(self, name, ctx):
        """Restore workspace from session file."""
        session_file = os.path.expanduser(f"~/.config/pdfcat/sessions/{name}.json")

        with open(session_file) as f:
            session = json.load(f)

        # Restore all documents
        for doc_state in session["documents"]:
            doc = Document(doc_state["path"], ctx=ctx)
            doc.goto_page(doc_state["page"])
            doc.rotation = doc_state["rotation"]
            doc.papersize = doc_state["zoom"]
            # ... restore other settings ...

            ctx.buffers.docs.append(doc)

        # Restore current buffer
        ctx.buffers.current = session["current_buffer"]

        return ctx.buffers.docs[ctx.buffers.current]
```

### CLI Integration
```bash
# Save current session
pdfcat --save-session mysession

# Restore session
pdfcat --session mysession

# List sessions
pdfcat --list-sessions

# Delete session
pdfcat --delete-session mysession
```

### Auto-save Feature
```json
{
  "AUTO_SAVE_SESSION": true,
  "AUTO_SAVE_INTERVAL": 60  // seconds
}
```

### Why This Matters
- ✅ Research workflows often span days/weeks
- ✅ Switch between projects easily
- ✅ Never lose your place
- ✅ Share workspace with collaborators

---

## 8. Smart Zoom (Fit Width / Fit Height / Fit Content) ⭐️ Score: 2.5

**Category**: UX
**Impact**: 5/5 | **Effort**: 2/5 | **Time**: ~10 hours

### What It Does
Intelligent zoom modes beyond the current fixed paper sizes.

### Current Gap
Zoom is tied to paper sizes (A7, A6, A5, etc.). No "fit width" or "fit to content" modes.

### Proposed Zoom Modes
```
Press `z` to cycle through zoom modes:
1. Fit Width  - maximize horizontal space
2. Fit Height - maximize vertical space
3. Fit Page   - show entire page (current default)
4. Fit Content - zoom to text area (ignore margins)
5. Custom %   - [count]z sets zoom to count% (e.g., 150z = 150%)
```

### Implementation
```python
class ZoomMode:
    """Smart zoom calculations."""

    @staticmethod
    def fit_width(page, screen):
        """Calculate zoom to fit page width to screen width."""
        page_width = page.rect.width
        screen_width = screen.width

        return screen_width / page_width

    @staticmethod
    def fit_height(page, screen):
        """Calculate zoom to fit page height to screen height."""
        page_height = page.rect.height
        screen_height = screen.height - screen.cell_height  # Status bar

        return screen_height / page_height

    @staticmethod
    def fit_content(page, screen):
        """Calculate zoom to fit text content (ignore margins)."""
        # Get text bounding box
        text_blocks = page.get_text("blocks")
        if not text_blocks:
            return ZoomMode.fit_page(page, screen)

        # Find content bounds
        min_x = min(block[0] for block in text_blocks)
        min_y = min(block[1] for block in text_blocks)
        max_x = max(block[2] for block in text_blocks)
        max_y = max(block[3] for block in text_blocks)

        content_width = max_x - min_x
        content_height = max_y - min_y

        # Calculate zoom to fit content
        zoom_x = screen.width / content_width
        zoom_y = (screen.height - screen.cell_height) / content_height

        return min(zoom_x, zoom_y)

    @staticmethod
    def custom_percent(percent, page):
        """Calculate zoom for custom percentage."""
        # 100% = actual page size
        # 150% = 1.5x larger
        return (percent / 100.0)
```

### Keybindings
- `z` - Cycle zoom modes
- `zw` - Fit width
- `zh` - Fit height
- `zc` - Fit content
- `150z` - 150% zoom
- `+` / `-` - Fine-tune zoom ±10%

### Why This Matters
- ✅ Two-column papers need fit-width
- ✅ Scanned books need fit-content
- ✅ Presentations need fit-height
- ✅ Much more intuitive than paper sizes

---

## 9. PDF Merge/Split from Within pdfcat ⭐️ Score: 1.67

**Category**: Feature
**Impact**: 5/5 | **Effort**: 3/5 | **Time**: ~15 hours

### What It Does
Merge multiple PDFs or extract page ranges without leaving pdfcat.

### Current Gap
Need external tools (pdftk, PyPDF2 CLI) to manipulate PDFs.

### Proposed Workflow
```
Merge PDFs:
1. Open multiple PDFs in buffers
2. Press `:merge output.pdf`
3. Merges all open PDFs into output.pdf

Extract pages:
1. Open PDF
2. Visual select pages: `vip` (visual select pages)
3. Mark start: ma, navigate, mark end: mb
4. Extract: `:extract 'a,'b output.pdf`
   → Extracts pages between marks a and b
```

### Implementation
```python
class PDFManipulator:
    """PDF merge and split operations."""

    @staticmethod
    def merge_pdfs(input_paths, output_path):
        """Merge multiple PDFs into one."""
        import fitz

        result = fitz.open()

        for path in input_paths:
            with fitz.open(path) as pdf:
                result.insert_pdf(pdf)

        result.save(output_path)
        result.close()

    @staticmethod
    def extract_pages(input_path, page_range, output_path):
        """Extract page range to new PDF."""
        import fitz

        doc = fitz.open(input_path)
        result = fitz.open()

        start, end = page_range
        result.insert_pdf(doc, from_page=start, to_page=end)

        result.save(output_path)
        result.close()
        doc.close()

    @staticmethod
    def split_pdf(input_path, output_dir, pages_per_file=10):
        """Split PDF into multiple files."""
        import fitz

        doc = fitz.open(input_path)
        total_pages = doc.page_count

        for i in range(0, total_pages, pages_per_file):
            result = fitz.open()
            end = min(i + pages_per_file, total_pages)
            result.insert_pdf(doc, from_page=i, to_page=end - 1)

            output_path = os.path.join(output_dir, f"part_{i//pages_per_file + 1}.pdf")
            result.save(output_path)
            result.close()

        doc.close()
```

### Command Mode
```vim
:merge output.pdf           " Merge all open PDFs
:extract 10-20 output.pdf   " Extract pages 10-20
:split 50                   " Split into 50-page chunks
:rotate 90                  " Rotate current PDF 90°
:crop                       " Permanently crop PDF to current crop
```

### Why This Matters
- ✅ Common PDF workflow operations
- ✅ No context switching to external tools
- ✅ Preview before saving
- ✅ Undo support

---

## 10. OCR for Scanned PDFs (Text Layer Generation) ⭐️ Score: 1.33

**Category**: Feature
**Impact**: 4/5 | **Effort**: 3/5 | **Time**: ~15 hours

### What It Does
Run OCR on image-based PDFs to make them searchable and copy-able.

### Current Gap
Scanned PDFs (images only) can't be searched or text-copied.

### Proposed Workflow
```
Open scanned PDF:
- Try to search → "No text found"
- Press `:ocr` → runs OCR on entire document
- Progress bar shows OCR progress
- Text layer added to PDF (saved to new file)
- Now searchable and copy-able
```

### Implementation
```python
class OCREngine:
    """OCR integration for scanned PDFs."""

    def __init__(self) -> None:
        self.tesseract_available = shutil.which("tesseract") is not None

    def ocr_page(self, doc, page_num, language="eng"):
        """Run OCR on a single page."""
        if not self.tesseract_available:
            raise Exception("tesseract not installed")

        # Get page as image
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=300)  # High DPI for OCR

        # Save to temp file
        temp_image = tempfile.mktemp(suffix=".png")
        pix.save(temp_image)

        # Run tesseract
        result = subprocess.run(
            ["tesseract", temp_image, "stdout", "-l", language],
            capture_output=True,
            text=True,
        )

        os.unlink(temp_image)

        return result.stdout

    def add_text_layer(self, doc, page_num, text):
        """Add invisible text layer to page."""
        page = doc.load_page(page_num)

        # Parse OCR output (includes coordinates)
        # tesseract -c tessedit_create_hocr=1 for coordinates

        # Add invisible text annotations at correct positions
        # This makes PDF searchable while keeping original image

        page.insert_text(
            point=(0, 0),
            text=text,
            color=(1, 1, 1),  # White (invisible)
            opacity=0,
        )

    def ocr_document(self, input_path, output_path, language="eng",
                     progress_callback=None):
        """OCR entire document and save with text layer."""
        doc = fitz.open(input_path)

        for page_num in range(doc.page_count):
            # Run OCR
            text = self.ocr_page(doc, page_num, language)

            # Add text layer
            self.add_text_layer(doc, page_num, text)

            # Progress callback
            if progress_callback:
                progress_callback(page_num + 1, doc.page_count)

        # Save to new file
        doc.save(output_path)
        doc.close()
```

### Integration
```python
# In pdfcat viewer:
elif key == ord(':'):
    command = read_command()  # Read from status bar

    if command.startswith("ocr"):
        parts = command.split()
        output_path = parts[1] if len(parts) > 1 else doc.filename.replace(".pdf", "_ocr.pdf")

        bar.message = "Running OCR (this may take a while)..."
        bar.update(doc)

        ocr = OCREngine()
        ocr.ocr_document(
            doc.filename,
            output_path,
            progress_callback=lambda curr, total:
                bar.message = f"OCR: {curr}/{total} pages"
        )

        bar.message = f"OCR complete: {output_path}"
```

### Requirements
```bash
# Install tesseract
brew install tesseract       # macOS
sudo apt install tesseract   # Ubuntu

# Language packs
brew install tesseract-lang  # All languages
```

### Why This Matters
- ✅ Essential for old scanned books/papers
- ✅ Makes PDFs searchable
- ✅ Enable copy/paste from scans
- ✅ Research workflow improvement

---

## Summary Table

| # | Feature | Impact | Effort | Score | Time | Category |
|---|---------|--------|--------|-------|------|----------|
| 1 | PDF Annotations | 5 | 1.25 | 4.0 | 6h | Feature |
| 2 | Auto-generate TOC | 5 | 1.5 | 3.33 | 8h | Feature |
| 3 | Fuzzy file opener | 5 | 2 | 2.5 | 10h | UX |
| 4 | Two-page spread | 5 | 2.5 | 2.0 | 12h | Feature |
| 5 | Presentation mode | 4 | 2 | 2.0 | 10h | Feature |
| 6 | Incremental search | 5 | 2 | 2.5 | 10h | UX |
| 7 | Session management | 4 | 2 | 2.0 | 10h | Feature |
| 8 | Smart zoom | 5 | 2 | 2.5 | 10h | UX |
| 9 | PDF merge/split | 5 | 3 | 1.67 | 15h | Feature |
| 10 | OCR integration | 4 | 3 | 1.33 | 15h | Feature |

---

## Recommended Implementation Order

### Phase 1: Quick UX Wins (2-3 days)
1. **Incremental search** (10h) - Immediate workflow improvement
2. **Smart zoom** (10h) - Much better than paper sizes
3. **Fuzzy file opener** (10h) - Never leave pdfcat

### Phase 2: Core Features (1 week)
4. **PDF Annotations** (6h) - Essential for research
5. **Auto-generate TOC** (8h) - Makes bad PDFs usable
6. **Session management** (10h) - Long-term workflow support

### Phase 3: Advanced Features (1 week)
7. **Two-page spread** (12h) - Book reading experience
8. **Presentation mode** (10h) - Teaching/presenting capability

### Phase 4: Power User Features (1 week)
9. **PDF merge/split** (15h) - Advanced manipulation
10. **OCR integration** (15h) - Scanned PDF support

---

## Configuration Examples

Add to `~/.config/pdfcat/config`:

```json
{
  "PDF_DIRS": [
    "~/Documents/Papers",
    "~/Dropbox/Research",
    "~/Books"
  ],
  "RECENT_FILES_LIMIT": 50,
  "AUTO_SAVE_SESSION": true,
  "AUTO_SAVE_INTERVAL": 60,
  "DEFAULT_ZOOM_MODE": "fit-width",
  "OCR_LANGUAGE": "eng",
  "ANNOTATION_DEFAULT_COLOR": "yellow",
  "PRESENTATION_TIMER": true,
  "TWO_PAGE_MODE_DEFAULT": false
}
```

---

## My Recommendation

Start with **Phase 1 (Quick UX Wins)**:

1. **Incremental search** - You'll use this every day
2. **Smart zoom** - Much more intuitive than current system
3. **Fuzzy file opener** - Game-changer for productivity

These three features take ~30 hours total and dramatically improve the daily pdfcat experience.

Then move to **Phase 2** for research workflow essentials (annotations, TOC, sessions).

**Which one interests you most?**
