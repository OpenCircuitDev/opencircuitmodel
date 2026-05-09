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
