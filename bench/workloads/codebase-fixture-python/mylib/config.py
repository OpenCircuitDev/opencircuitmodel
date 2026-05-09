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
