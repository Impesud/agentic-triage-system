import json
import re
from datetime import UTC, datetime
from typing import Any

from paths import LOG_FILE_PATH

_API_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")


def _ensure_log_dir() -> None:
    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _redact_sensitive_data(text: str) -> str:
    """Oscura solo pattern sensibili (es. API key), non il testo dei ticket."""
    return _API_KEY_PATTERN.sub("sk-***", text)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_sensitive_data(value)
    if isinstance(value, dict):
        return {key: _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def log_event(event_type: str, payload: dict[str, Any]) -> None:
    """Scrive un evento strutturato in logs/activity.jsonl."""
    _ensure_log_dir()

    log_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "payload": _sanitize_value(payload),
    }

    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
