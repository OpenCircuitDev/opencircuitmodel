"""HTTP API surface — minimal sync handler protocol."""
from __future__ import annotations
from typing import Protocol
from .config import Config
from .store import MemoryStore


class Handler(Protocol):
    """Protocol any HTTP handler must satisfy."""

    def handle(self, method: str, path: str, body: bytes) -> tuple[int, bytes]:
        """Return (status_code, response_body)."""


def create_app(config: Config, store: MemoryStore) -> Handler:
    """Wire the config + store into a Handler-conforming app instance."""
    return _AppImpl(config, store)


class _AppImpl:
    """Internal — concrete app. Not exported."""

    def __init__(self, config: Config, store: MemoryStore) -> None:
        self.config = config
        self.store = store

    def handle(self, method: str, path: str, body: bytes) -> tuple[int, bytes]:
        if method == "GET" and path.startswith("/kv/"):
            return self._handle_get(path[4:])
        if method == "PUT" and path.startswith("/kv/"):
            return self._handle_put(path[4:], body)
        return (404, b"not found")

    def _handle_get(self, key: str) -> tuple[int, bytes]:
        try:
            v = self.store.get(key)
        except KeyError:
            return (404, b"missing")
        return (200, str(v).encode())

    def _handle_put(self, key: str, body: bytes) -> tuple[int, bytes]:
        self.store.set(key, body.decode())
        return (204, b"")
