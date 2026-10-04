"""Persistent event backbone for Nexus autonomy.

Events are durable facts about changes in the Nexus world. They are intentionally
separate from model reasoning so important state changes can wake Nexus without
requiring a user command or a fresh model conversation.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from src.registry import WORKSPACE_DIR


@dataclass(frozen=True)
class NexusEvent:
    type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventStore:
    """Small durable event log with bounded storage and atomic writes."""

    MAX_EVENTS = 500
    MAX_STORE_BYTES = 2_000_000
    MAX_PAYLOAD_FIELDS = 32
    MAX_STRING_CHARS = 4_000
    STATUSES = frozenset({"pending", "processed", "failed"})
    _lock = threading.RLock()

    def __init__(self, path: str | None = None):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self.path = os.path.abspath(path or os.path.join(WORKSPACE_DIR, "nexus_events.json"))

    def _load(self) -> list[dict[str, Any]]:
        if os.path.lexists(self.path) and os.path.islink(self.path):
            raise ValueError("Event store must be a regular, non-symlink file.")
        if not os.path.exists(self.path):
            return []
        if not os.path.isfile(self.path) or os.path.getsize(self.path) > self.MAX_STORE_BYTES:
            raise ValueError("Event store is missing, invalid, or exceeds the configured size limit.")
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Event store is unreadable or contains invalid JSON.") from exc
        if not isinstance(data, list) or len(data) > self.MAX_EVENTS:
            raise ValueError("Event store has an invalid collection shape.")
        return data

    def _save(self, events: list[dict[str, Any]]) -> None:
        fd, temp = tempfile.mkstemp(
            dir=os.path.dirname(self.path), prefix=".nexus_events_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(events[-self.MAX_EVENTS:], handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            if os.path.getsize(temp) > self.MAX_STORE_BYTES:
                raise ValueError("Event store exceeds the configured size limit.")
            os.replace(temp, self.path)
        except Exception:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise

    @classmethod
    def _normalize_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Event payload must be an object.")
        if len(payload) > cls.MAX_PAYLOAD_FIELDS:
            raise ValueError("Event payload has too many fields.")
        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or not key or len(key) > 80:
                raise ValueError("Event payload keys must be short text.")
            if isinstance(value, str):
                normalized[key] = value[:cls.MAX_STRING_CHARS]
            elif isinstance(value, (int, float, bool)) or value is None:
                normalized[key] = value
            elif isinstance(value, (list, dict)):
                encoded = json.dumps(value, ensure_ascii=False)
                if len(encoded) > cls.MAX_STRING_CHARS:
                    raise ValueError("Event payload value is too large.")
                normalized[key] = value
            else:
                raise ValueError("Event payload contains an unsupported value.")
        return normalized

    def append(self, event: NexusEvent) -> dict[str, Any]:
        if not isinstance(event, NexusEvent):
            raise ValueError("Event must be a NexusEvent.")
        if not event.type.strip() or len(event.type) > 120:
            raise ValueError("Event type must be short non-empty text.")
        if not event.source.strip() or len(event.source) > 120:
            raise ValueError("Event source must be short non-empty text.")
        record = {
            "id": event.id,
            "type": event.type,
            "source": event.source,
            "created_at": event.created_at,
            "status": "pending",
            "payload": self._normalize_payload(event.payload),
        }
        with self._lock:
            events = self._load()
            events.append(record)
            self._save(events)
        return record

    def pending(self, limit: int = 50) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or limit < 1:
            limit = 1
        with self._lock:
            return [event for event in self._load() if event.get("status") == "pending"][:limit]

    def mark(self, event_id: str, status: str) -> dict[str, Any] | None:
        if status not in self.STATUSES:
            raise ValueError("Unknown event status.")
        with self._lock:
            events = self._load()
            for event in events:
                if event.get("id") == event_id:
                    event["status"] = status
                    self._save(events)
                    return event
        return None
