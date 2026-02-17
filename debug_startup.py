#!/usr/bin/env python3
"""Debug startup to see what values we have"""

import sys

sys.path.insert(0, "/Users/marcos/Projects/personal/pdfcat")


# Mock the minimal classes needed
class Page_State:
    def __init__(self, p):
        self.number = p
        self.stale = True
        self.factor = (1, 1)
        self.place = (0, 0, 40, 40)
        self.crop = None
        self.cached_pixmap = None
        self.cached_matrix = None
        print(f"  Created Page_State({p}) with stale={self.stale}")


print("Simulating document creation:")
page_states = [Page_State(i) for i in range(0, 5)]

print("\nSimulating goto_page(0):")
page = 0
print(f"  Setting page_states[{page}].stale = True")
page_states[page].stale = True

print("\nSimulating display_page check:")
display = False
page_state = page_states[page]
print(f"  page_state.stale = {page_state.stale}")
print(f"  display = {display}")
should_render = page_state.stale or display
print(f"  Condition (page_state.stale or display) = {should_render}")

if should_render:
    print("  ✓ Would render page")
else:
    print("  ✗ Would NOT render page - THIS IS THE BUG!")
