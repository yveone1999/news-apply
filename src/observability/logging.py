"""结构化日志（JSON 行），敏感字段脱敏。"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

_SENSITIVE = re.compile(r"(authorization|api[_-]?key|token|secret|password|bearer\s+)[\"']?\s*[:=]\s*[\"']?[^\s,\"'}]+", re.I)


def scrub(message: str) -> str:
    return _SENSITIVE.sub(lambda m: f"{m.group(1)}=***", message)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": scrub(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.environ.get("LOG_LEVEL", level).upper())
