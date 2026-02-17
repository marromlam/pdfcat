"""Process-wide runtime context accessor."""

from __future__ import annotations

from typing import Any

_viewer_context: Any = None


def set_context(ctx: Any) -> None:
    """Set active runtime context."""
    global _viewer_context
    _viewer_context = ctx


def get_context() -> Any:
    """Get active runtime context."""
    return _viewer_context
