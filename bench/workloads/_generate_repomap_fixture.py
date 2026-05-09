"""Generate a representative Python codebase fixture for the aider-repomap sandbox.

Creates bench/workloads/codebase-fixture-python/ with ~10 modules totaling
~1500 LOC — a realistic-sized small library. Each module has a mix of:
  - public functions (with body + docstring)
  - private helpers (underscore-prefix)
  - classes with several methods
  - constants / type aliases
  - imports (some used, some shadowed for realism)

The repomap test compares:
  (a) full file contents — what the agent would see if context-stuffed
  (b) repomap-compressed view (signatures + docstrings only)

Run from repo root:
  python bench/workloads/_generate_repomap_fixture.py
"""

from __future__ import annotations

from pathlib import Path
import textwrap


FIXTURE_ROOT = Path(__file__).resolve().parent / "codebase-fixture-python"


# Each entry: (relative_path, content)
MODULES: list[tuple[str, str]] = [
    (
        "mylib/__init__.py",
        textwrap.dedent('''\
            """A small example library exposing a tiny CRUD service."""
            from .config import load_config, Config
            from .store import MemoryStore, KeyError as StoreKeyError
            from .api import create_app, Handler

            __all__ = ["load_config", "Config", "MemoryStore", "StoreKeyError", "create_app", "Handler"]
            __version__ = "0.1.0"
        '''),
    ),
    (
        "mylib/config.py",
        textwrap.dedent('''\
            """Configuration loader. Reads TOML from disk with env override."""
            from __future__ import annotations
            import os
            from dataclasses import dataclass, field
            from pathlib import Path

            try:
                import tomllib
            except ImportError:  # pragma: no cover
                import tomli as tomllib  # type: ignore


            @dataclass
            class Config:
                """Top-level config record."""
                host: str = "127.0.0.1"
                port: int = 8080
                debug: bool = False
                allowed_origins: list[str] = field(default_factory=list)


            def load_config(path: str | Path = "config.toml") -> Config:
                """Load config from TOML, applying MYLIB_* env overrides."""
                p = Path(path)
                data: dict = {}
                if p.exists():
                    with p.open("rb") as f:
                        data = tomllib.load(f)
                _apply_env_overrides(data)
                return Config(**data)


            def _apply_env_overrides(data: dict) -> None:
                """Mutate data dict to honor MYLIB_HOST, MYLIB_PORT, MYLIB_DEBUG."""
                if (h := os.environ.get("MYLIB_HOST")):
                    data["host"] = h
                if (p := os.environ.get("MYLIB_PORT")):
                    data["port"] = int(p)
                if (d := os.environ.get("MYLIB_DEBUG")):
                    data["debug"] = d.lower() in ("1", "true", "yes")
        '''),
    ),
    (
        "mylib/store.py",
        textwrap.dedent('''\
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
        '''),
    ),
    (
        "mylib/api.py",
        textwrap.dedent('''\
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
        '''),
    ),
    (
        "mylib/auth.py",
        textwrap.dedent('''\
            """Token-based auth middleware."""
            from __future__ import annotations
            import hmac
            import hashlib
            import secrets
            import time


            def generate_token(secret: bytes, subject: str, ttl_seconds: int = 3600) -> str:
                """Generate a signed token of form 'subject.expiry.signature'."""
                expiry = int(time.time()) + ttl_seconds
                payload = f"{subject}.{expiry}".encode()
                sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:32]
                return f"{subject}.{expiry}.{sig}"


            def verify_token(secret: bytes, token: str) -> str | None:
                """Verify a token and return its subject, or None if invalid/expired."""
                parts = token.split(".")
                if len(parts) != 3:
                    return None
                subject, expiry_str, sig = parts
                try:
                    expiry = int(expiry_str)
                except ValueError:
                    return None
                if time.time() > expiry:
                    return None
                payload = f"{subject}.{expiry}".encode()
                expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()[:32]
                if not hmac.compare_digest(sig, expected):
                    return None
                return subject


            def random_secret(n_bytes: int = 32) -> bytes:
                """Generate a cryptographically-strong random secret."""
                return secrets.token_bytes(n_bytes)
        '''),
    ),
    (
        "mylib/log.py",
        textwrap.dedent('''\
            """Structured logging shim. Wraps stdlib `logging` with JSON output."""
            from __future__ import annotations
            import json
            import logging
            import sys
            from typing import Any


            class JSONFormatter(logging.Formatter):
                """Format log records as single-line JSON."""

                def format(self, record: logging.LogRecord) -> str:
                    payload: dict[str, Any] = {
                        "ts": self.formatTime(record),
                        "level": record.levelname,
                        "logger": record.name,
                        "msg": record.getMessage(),
                    }
                    if record.exc_info:
                        payload["exc"] = self.formatException(record.exc_info)
                    return json.dumps(payload)


            def configure(level: str = "INFO") -> logging.Logger:
                """Configure root logger with JSON output to stderr."""
                root = logging.getLogger()
                root.setLevel(level)
                handler = logging.StreamHandler(sys.stderr)
                handler.setFormatter(JSONFormatter())
                root.handlers.clear()
                root.addHandler(handler)
                return root


            def get_logger(name: str) -> logging.Logger:
                """Return a child logger inheriting the JSON formatter."""
                return logging.getLogger(name)
        '''),
    ),
    (
        "mylib/util.py",
        textwrap.dedent('''\
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
        '''),
    ),
    (
        "tests/__init__.py",
        textwrap.dedent('''\
            """Test package marker."""
        '''),
    ),
    (
        "tests/test_store.py",
        textwrap.dedent('''\
            """Tests for MemoryStore."""
            from __future__ import annotations
            import time
            import pytest
            from mylib.store import MemoryStore, KeyError as StoreKeyError


            def test_set_get_basic():
                s = MemoryStore()
                s.set("foo", "bar")
                assert s.get("foo") == "bar"


            def test_get_missing_raises():
                s = MemoryStore()
                with pytest.raises(StoreKeyError):
                    s.get("nope")


            def test_ttl_expires():
                s = MemoryStore()
                s.set("k", "v", ttl_seconds=0.01)
                time.sleep(0.05)
                with pytest.raises(StoreKeyError):
                    s.get("k")


            def test_delete_returns_true_when_existed():
                s = MemoryStore()
                s.set("a", 1)
                assert s.delete("a") is True
                assert s.delete("a") is False


            def test_keys_excludes_expired():
                s = MemoryStore()
                s.set("alive", 1)
                s.set("dead", 2, ttl_seconds=0.01)
                time.sleep(0.05)
                assert "alive" in list(s.keys())
                assert "dead" not in list(s.keys())
        '''),
    ),
    (
        "tests/test_auth.py",
        textwrap.dedent('''\
            """Tests for auth tokens."""
            from __future__ import annotations
            import time
            import pytest
            from mylib.auth import generate_token, verify_token, random_secret


            def test_round_trip():
                secret = random_secret()
                token = generate_token(secret, "alice", ttl_seconds=60)
                assert verify_token(secret, token) == "alice"


            def test_wrong_secret_returns_none():
                a = random_secret()
                b = random_secret()
                token = generate_token(a, "alice")
                assert verify_token(b, token) is None


            def test_expired_returns_none():
                secret = random_secret()
                token = generate_token(secret, "alice", ttl_seconds=0)
                time.sleep(0.05)
                assert verify_token(secret, token) is None


            def test_malformed_returns_none():
                secret = random_secret()
                assert verify_token(secret, "garbage") is None
                assert verify_token(secret, "x.y.z") is None
        '''),
    ),
]


def main() -> int:
    if FIXTURE_ROOT.exists():
        # Wipe so we're idempotent
        import shutil

        shutil.rmtree(FIXTURE_ROOT)

    for relpath, content in MODULES:
        out = FIXTURE_ROOT / relpath
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
    print(f"Wrote {len(MODULES)} files to {FIXTURE_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
