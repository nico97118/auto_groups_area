"""Logging helpers for the Auto Groups by Area integration."""

from __future__ import annotations

from collections.abc import Iterable


def format_list(items: Iterable[str], *, limit: int = 20) -> str:
    """Format a list for logs with truncation."""
    items_list = list(items)
    if len(items_list) <= limit:
        return str(items_list)
    return f"{items_list[:limit]} (+{len(items_list) - limit} more)"


def diff_lists(old: Iterable[str], new: Iterable[str]) -> tuple[list[str], list[str]]:
    """Return (added, removed) between two iterables."""
    old_set = set(old)
    new_set = set(new)
    added = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)
    return added, removed
