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
