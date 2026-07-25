"""Structured JSON logging with secret redaction.

The redaction filter is a safety net, not permission to log secrets. Do not pass a
key, token, or password to a log call and rely on this to catch it.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"(?i)(x-(?:mcp|api)-key\s*[:=]\s*)([\w\-.]+)"),
    re.compile(r"(?i)(bearer\s+)([\w\-._~+/]+=*)"),
    re.compile(r"(?i)((?:api|secret|access|private)[_-]?(?:key|token)\W{1,4})([\w\-._~+/]{8,})"),
    re.compile(r"(?i)(password\W{1,4})(\S+)"),
    re.compile(r"\bsk-[A-Za-z0-9\-_]{16,}\b"),
]

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


def redact(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(r"\1***REDACTED***", text)
        else:
            text = pattern.sub("***REDACTED***", text)
    return text


class RedactingJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        # Anything passed via extra= becomes a top-level field: project_id, task_id, agent.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return redact(json.dumps(payload, default=str))


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RedactingJSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Uvicorn's own handlers would otherwise double-log in plain text.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
