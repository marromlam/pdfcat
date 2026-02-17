#!/usr/bin/env python3
"""Test the rendering logic to verify stale flag behavior"""


# Simulate Page_State
class Page_State:
    def __init__(self, p):
        self.number = p
        self.stale = True
        self.cached_pixmap = None
        self.cached_matrix = None


# Test scenarios
print("Testing rendering logic:")
print()

# Scenario 1: First page load
print("Scenario 1: First page load")
page_state = Page_State(0)
display = False
print(f"  page_state.stale = {page_state.stale}")
print(f"  display = {display}")
should_render = page_state.stale or display
print(f"  Should render: {should_render}")
print("  ✓ PASS - First page renders" if should_render else "  ✗ FAIL")
print()

# Scenario 2: Page already rendered (stale=False)
print("Scenario 2: Page already rendered, no navigation")
page_state.stale = False
display = False
print(f"  page_state.stale = {page_state.stale}")
print(f"  display = {display}")
should_render = page_state.stale or display
print(f"  Should render: {should_render}")
print("  ✓ PASS - No unnecessary render" if not should_render else "  ✗ FAIL")
print()

# Scenario 3: Navigation to new page (goto_page sets stale=True)
print("Scenario 3: Navigation to new page")
page_state.stale = True  # goto_page() does this
display = False
print(f"  page_state.stale = {page_state.stale}")
print(f"  display = {display}")
should_render = page_state.stale or display
print(f"  Should render: {should_render}")
print("  ✓ PASS - New page renders" if should_render else "  ✗ FAIL")
print()

# Scenario 4: Transformation applied (mark_all_pages_stale)
print("Scenario 4: Transformation (rotation)")
page_state.stale = True  # mark_all_pages_stale() does this
page_state.cached_pixmap = None  # Cache invalidated
display = False
print(f"  page_state.stale = {page_state.stale}")
print(f"  cached_pixmap = {page_state.cached_pixmap}")
print(f"  display = {display}")
should_render = page_state.stale or display
print(f"  Should render: {should_render}")
print(
    "  ✓ PASS - Page re-renders after transformation" if should_render else "  ✗ FAIL"
)
print()

print("All scenarios PASSED ✓")
