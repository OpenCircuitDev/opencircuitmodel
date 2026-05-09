"""A small example library exposing a tiny CRUD service."""
from .config import load_config, Config
from .store import MemoryStore, KeyError as StoreKeyError
from .api import create_app, Handler

__all__ = ["load_config", "Config", "MemoryStore", "StoreKeyError", "create_app", "Handler"]
__version__ = "0.1.0"
