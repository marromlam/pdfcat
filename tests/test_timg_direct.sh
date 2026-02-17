#!/bin/bash
# Test timg directly to ensure it works in tmux

echo "Testing timg in current environment..."
echo ""
echo "Environment:"
echo "  TERM: $TERM"
echo "  TMUX: ${TMUX:-not set}"
echo ""

# Create a simple test image
python3 <<'PYEOF'
from PIL import Image, ImageDraw, ImageFont

# Create a test image
img = Image.new('RGB', (400, 200), color='blue')
draw = ImageDraw.Draw(img)
draw.rectangle([50, 50, 350, 150], fill='white', outline='black', width=3)
draw.text((100, 85), "Test Image", fill='black')
img.save('/tmp/test_timg.png')
print("Created /tmp/test_timg.png")
PYEOF

echo ""
echo "Testing timg with -pk flag (Kitty protocol in tmux)..."
timg -g 40x10 -pk /tmp/test_timg.png

echo ""
echo "If you see a blue rectangle with 'Test Image' above, timg is working!"
echo ""
echo "If blank, try:"
echo "  1. timg -g 40x10 /tmp/test_timg.png  (without -pk)"
echo "  2. Check timg version: timg --version"
echo "  3. Check tmux version: tmux -V (needs >= 3.3)"
echo "  4. Check kitty version: kitty --version (needs >= 0.28)"

rm /tmp/test_timg.png
