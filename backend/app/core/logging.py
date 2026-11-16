"""Application logging utilities.

- Uses the standard ``logging`` library configured via ``LOG_LEVEL``.
- Emits JSON‑formatted logs (timestamp, level, name, message, optional extra).
- Never logs any of the secrets from ``app.core.config.Settings``.
"""

import json
import logging
import sys
from typing import Any, Mapping

from app.core.config import settings

# ---------------------------------------------------------------------------
# JSON formatter – a lightweight implementation that avoids external deps.
# ---------------------------------------------------------------------------

class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        """Return a JSON string for *record*.

        The default ``LogRecord`` attributes are kept, plus any mapping passed
        via ``extra`` when logging (e.g. ``logger.info(msg, extra={"user_id": …})``).
        """
        log_obj: Mapping[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        # ``record.__dict__`` may contain ``extra`` items – filter out the built‑ins.
        extra_keys = set(record.__dict__) - set(logging.LogRecord.__dict__)
        for key in extra_keys:
            value = getattr(record, key, None)
            # Prevent accidental logging of secret settings.
            if key.upper().endswith("_SECRET") or key.upper().endswith("_KEY"):
                continue
            log_obj[key] = value
        return json.dumps(log_obj, ensure_ascii=False, default=str)

# ---------------------------------------------------------------------------
# Logger configuration – called once at import time.
# ---------------------------------------------------------------------------

def _configure_root_logger() -> None:
    root = logging.getLogger()
    if root.handlers:
        # Assume already configured (e.g., by Uvicorn). Keep existing handlers.
        return
    root.setLevel(settings.LOG_LEVEL.upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)

_configure_root_logger()

# Export a module‑level logger for convenience.
logger = logging.getLogger("ctrx")
