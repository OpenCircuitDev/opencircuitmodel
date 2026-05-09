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
