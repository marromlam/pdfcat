# tmux and Sixel Support Guide

## Quick Start

### Installing Required Tools

No external image renderer is required for normal usage.
`pdfcat` uses its built-in native renderer.

Optional (for compatibility tests only):
```bash
brew install timg
```

### Using with tmux

Simply run pdfcat inside tmux as you normally would:

```bash
tmux new-session
./pdfcat your-document.pdf
```

`pdfcat` will automatically:
- Detect that you're in tmux
- Use Kitty graphics protocol with tmux passthrough
- Display images correctly inside tmux

### Using with Sixel Terminals

If you're using a Sixel-capable terminal (xterm, mlterm, wezterm, foot, etc.):

```bash
./pdfcat your-document.pdf
```

The application will automatically detect your terminal's capabilities and use the appropriate protocol.

## How It Works

### Renderer Priority

The application tries renderers in this order:

1. **Native renderer** (default)
   - Best tmux + kitty support
   - No external binary required

2. **Legacy Kitty renderer** (fallback)
   - Works in kitty-compatible terminals

### Automatic Protocol Detection

Protocol is detected automatically:

- **Kitty terminal outside tmux**: Uses Kitty graphics protocol
- **Kitty terminal inside tmux**: Uses Kitty protocol with tmux passthrough
- **Sixel-capable terminal**: Uses Sixel protocol
- **Other terminals**: Attempts to auto-detect best available protocol

## Troubleshooting

### "No graphics renderer available" Error

This means your terminal does not provide a kitty-compatible graphics path.
Use kitty, tmux with a kitty client, or wezterm.

### Images Not Displaying in tmux

1. Verify you're in a kitty-compatible terminal:
   ```bash
   echo $TERM
   # Should show: xterm-kitty
   ```

2. Check tmux is running:
   ```bash
   echo $TMUX
   # Should show a path like: /tmp/tmux-...
   ```

3. Try running the test script:
   ```bash
   python3 test_renderer.py
   ```

### Images Not Displaying in Other Terminals

1. Check if your terminal supports Sixel:
   - xterm (with sixel support compiled in)
   - mlterm
   - wezterm
   - foot
   - Some versions of alacritty

2. Verify your terminal supports kitty graphics protocol.

## Testing Your Setup

### Quick Renderer Test

```bash
python3 test_renderer.py
```

This will show:
- Which renderers are available
- Whether you're in tmux
- What terminal type you're using
- Recommended installation steps

### Full Verification

```bash
python3 verify_implementation.py
```

This runs a complete verification of the implementation.

## Terminal Compatibility

### Confirmed Working

| Terminal | Native | In tmux | Protocol |
|----------|--------|---------|----------|
| Kitty | ✓ | ✓ | Kitty |
| wezterm | ✓ | ✓ (kitty client in tmux) | Kitty |

### Not Supported

- Terminals without graphics protocol support
- Plain terminal emulators (unless using ASCII art fallback)

## Advanced Usage

### Forcing a Specific Renderer

Currently, the renderer is auto-selected. Future versions may support:

```bash
# Not yet implemented
./pdfcat --renderer timg document.pdf
./pdfcat --renderer kitty document.pdf
```

### Configuration File

Future enhancement: Add to `~/.config/pdfcat/config`:

```json
{
  "RENDERER": "timg",
  "GRAPHICS_PROTOCOL": "auto"
}
```

## Performance Notes

### Rendering Speed

Native renderer overhead is minimal:
- PNG encoding: ~5-10ms per page
- File I/O: minimal (single temp file reused)
- Protocol transmission: handled by external tool

### Memory Usage

- Single temporary PNG file per session (typically 100-500KB)
- No accumulation of temp files
- Automatic cleanup on exit

## Known Limitations

1. **Window resize**: Some terminals may not handle resizing perfectly with external renderers
2. **Color accuracy**: May vary slightly between protocols
3. **Animation**: Not supported (PDFs are static anyway)

## Reporting Issues

If you encounter issues:

1. Run the diagnostic script:
   ```bash
   python3 test_renderer.py
   ```

2. Include this information in your bug report:
   - Terminal type (`echo $TERM`)
   - Whether in tmux (`echo $TMUX`)
   - Renderer in use (from status bar)
   - Error messages from pdfcat

## Additional Resources

- [Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/)
