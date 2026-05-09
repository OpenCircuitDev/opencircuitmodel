"""Misc utilities — string manipulation, time helpers."""
from __future__ import annotations
import time
from collections.abc import Iterable


def chunked(items: Iterable, size: int) -> Iterable[list]:
    """Yield successive size-N chunks from items."""
    buf: list = []
    for item in items:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def truncate_middle(s: str, max_len: int, marker: str = "…") -> str:
    """Truncate the middle of s to fit max_len, preserving start + end."""
    if len(s) <= max_len:
        return s
    each = (max_len - len(marker)) // 2
    return s[:each] + marker + s[-each:]


def humanize_duration(seconds: float) -> str:
    """Convert seconds to a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
