"""In-memory key-value store with TTL support."""
from __future__ import annotations
import time
from collections.abc import Iterator


class KeyError(Exception):
    """Raised when a key is missing from the store."""


class MemoryStore:
    """Tiny in-memory KV store with optional per-key TTL."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[object, float | None]] = {}

    def set(self, key: str, value: object, ttl_seconds: float | None = None) -> None:
        """Set a key. Optionally expire after ttl_seconds."""
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        self._data[key] = (value, expires_at)

    def get(self, key: str) -> object:
        """Fetch a key. Raises KeyError if missing or expired."""
        if key not in self._data:
            raise KeyError(key)
        value, expires_at = self._data[key]
        if expires_at is not None and time.time() > expires_at:
            del self._data[key]
            raise KeyError(key)
        return value

    def delete(self, key: str) -> bool:
        """Remove a key. Returns True if it existed."""
        return self._data.pop(key, None) is not None

    def keys(self) -> Iterator[str]:
        """Iterate non-expired keys."""
        now = time.time()
        for k, (_, exp) in list(self._data.items()):
            if exp is None or now <= exp:
                yield k

    def _gc(self) -> int:
        """Garbage-collect expired entries. Returns count removed."""
        now = time.time()
        expired = [k for k, (_, exp) in self._data.items() if exp and now > exp]
        for k in expired:
            del self._data[k]
        return len(expired)
