"""Persistent business world-state for Nexus."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from src.registry import WORKSPACE_DIR


class WorldStateStore:
    """Durable source of truth for business entities and workflow state."""

    MAX_RECORDS = 500
    MAX_STORE_BYTES = 5_000_000
    ENTITY_TYPES = frozenset({
        "business", "contact", "lead", "call", "research",
        "website_project", "payment", "workflow",
    })
    STATUSES = frozenset({
        "new", "contacted", "interested", "follow_up", "sold", "active",
        "pending", "approved", "rejected", "paid", "unpaid", "completed",
        "cancelled",
    })
    _lock = threading.RLock()

    def __init__(self, path: str | None = None):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self.path = os.path.abspath(path or os.path.join(WORKSPACE_DIR, "nexus_world.json"))

    def _load(self) -> list[dict[str, Any]]:
        if os.path.lexists(self.path) and os.path.islink(self.path):
            raise ValueError("World-state store must be a regular, non-symlink file.")
        if not os.path.exists(self.path):
            return []
        if not os.path.isfile(self.path) or os.path.getsize(self.path) > self.MAX_STORE_BYTES:
            raise ValueError("World-state store is missing, invalid, or too large.")
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("World-state store is unreadable or invalid.") from exc
        if not isinstance(data, list) or len(data) > self.MAX_RECORDS:
            raise ValueError("World-state store has an invalid collection shape.")
        return data

    def _save(self, records):
        fd, temp = tempfile.mkstemp(dir=os.path.dirname(self.path), prefix=".nexus_world_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(records[-self.MAX_RECORDS:], handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            if os.path.getsize(temp) > self.MAX_STORE_BYTES:
                raise ValueError("World-state store exceeds the configured size limit.")
            os.replace(temp, self.path)
        except Exception:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise

    @staticmethod
    def _clean(value: Any, limit: int = 12000) -> Any:
        if isinstance(value, str):
            return value[:limit]
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [WorldStateStore._clean(v, limit) for v in value[:100]]
        if isinstance(value, dict):
            return {str(k)[:80]: WorldStateStore._clean(v, limit) for k, v in list(value.items())[:100]}
        raise ValueError("World-state data contains an unsupported value.")

    def upsert(self, entity_type: str, data: dict[str, Any], entity_id: str | None = None):
        if entity_type not in self.ENTITY_TYPES:
            raise ValueError("Unknown world-state entity type.")
        if not isinstance(data, dict) or not data:
            raise ValueError("Entity data must be a non-empty object.")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            records = self._load()
            existing = next(
                (r for r in records if r["entity_type"] == entity_type and entity_id and r["id"] == entity_id),
                None,
            )
            if existing:
                existing["data"].update(self._clean(data))
                existing["updated_at"] = now
                record = existing
            else:
                record = {
                    "id": entity_id or uuid4().hex,
                    "entity_type": entity_type,
                    "created_at": now,
                    "updated_at": now,
                    "data": self._clean(data),
                }
                records.append(record)
            self._save(records)
            return record

    def get(self, entity_type: str, entity_id: str):
        if entity_type not in self.ENTITY_TYPES:
            raise ValueError("Unknown world-state entity type.")
        with self._lock:
            return next(
                (r for r in self._load() if r["entity_type"] == entity_type and r["id"] == entity_id),
                None,
            )

    def list(self, entity_type: str, status: str | None = None):
        if entity_type not in self.ENTITY_TYPES:
            raise ValueError("Unknown world-state entity type.")
        if status is not None and status not in self.STATUSES:
            raise ValueError("Unknown world-state status.")
        with self._lock:
            records = [r for r in self._load() if r["entity_type"] == entity_type]
            if status is not None:
                records = [r for r in records if r.get("data", {}).get("status") == status]
            return records

    def find(self, entity_type: str, **criteria: Any):
        if entity_type not in self.ENTITY_TYPES:
            raise ValueError("Unknown world-state entity type.")
        with self._lock:
            return [
                r for r in self._load()
                if r["entity_type"] == entity_type
                and all(r.get("data", {}).get(key) == value for key, value in criteria.items())
            ]

    def update_status(self, entity_type: str, entity_id: str, status: str):
        if status not in self.STATUSES:
            raise ValueError("Unknown world-state status.")
        if self.get(entity_type, entity_id) is None:
            raise KeyError(f"{entity_type} {entity_id} was not found.")
        return self.upsert(entity_type, {"status": status}, entity_id=entity_id)
