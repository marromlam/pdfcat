#!/usr/bin/env python3
"""Test script to verify renderer initialization"""

import logging
import os
import shutil

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# Test renderer availability
def test_timg():
    """Test if timg is available"""
    timg_path = shutil.which("timg")
    if timg_path:
        logging.info(f"✓ timg found at: {timg_path}")
        return True
    else:
        logging.warning("✗ timg not found")
        return False


def test_tmux_detection():
    """Test tmux detection"""
    in_tmux = "TMUX" in os.environ
    term = os.environ.get("TERM", "")

    logging.info(f"TERM: {term}")
    logging.info(f"In tmux: {in_tmux}")

    return in_tmux


def main():
    print("=" * 60)
    print("Renderer Availability Test")
    print("=" * 60)

    timg_available = test_timg()
    in_tmux = test_tmux_detection()

    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)

    if timg_available:
        print("✓ Recommended renderer (timg) is available")
        if in_tmux:
            print("  → Will work in tmux with Kitty graphics protocol")
        else:
            print("  → Will auto-detect best graphics protocol")
    else:
        print("✓ External timg not found")
        print("  → Native renderer will be used")

    print("\nTo install timg:")
    print("  macOS:  brew install timg")
    print("  Ubuntu: sudo apt install timg")
    print("=" * 60)


if __name__ == "__main__":
    main()
