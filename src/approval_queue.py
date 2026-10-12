"""Thread-safe, expiring approval requests for the local Nexus web interface."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any


class ApprovalQueue:
    """Hold one-time approval decisions without exposing executable callbacks."""

    def __init__(self, timeout_seconds: float = 120.0) -> None:
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _safe_args(args: object) -> dict[str, str]:
        if not isinstance(args, dict):
            return {}
        safe: dict[str, str] = {}
        for key, value in list(args.items())[:20]:
            name = str(key)[:80]
            if name.lower() == "python_code":
                limit = 3000
            elif name.lower() in {"body", "content"}:
                limit = 600
            else:
                limit = 240
            safe[name] = str(value)[:limit]
        return safe

    def request_approval(self, tool_name: str, args: dict) -> bool:
        """Publish a request and wait for a decision; timeouts fail closed."""
        request_id = uuid.uuid4().hex
        decision_event = threading.Event()
        item: dict[str, Any] = {
            "id": request_id,
            "tool": str(tool_name)[:80],
            "args": self._safe_args(args),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approved": None,
            "_event": decision_event,
        }
        with self._lock:
            self._pending[request_id] = item

        completed = decision_event.wait(self.timeout_seconds)
        with self._lock:
            current = self._pending.pop(request_id, None)
        return bool(completed and current is not None and current.get("approved") is True)

    def list_pending(self) -> list[dict[str, Any]]:
        """Return safe UI payloads without exposing synchronization objects."""
        with self._lock:
            items = list(self._pending.values())
            return [
                {
                    "id": item["id"],
                    "tool": item["tool"],
                    "args": dict(item["args"]),
                    "created_at": item["created_at"],
                }
                for item in items
                if item.get("approved") is None
            ]

    def decide(self, request_id: object, approved: object) -> bool:
        """Resolve one currently pending request; reject malformed decisions."""
        if not isinstance(request_id, str) or not request_id or len(request_id) > 64:
            return False
        if type(approved) is not bool:
            return False
        with self._lock:
            item = self._pending.get(request_id)
            if item is None or item.get("approved") is not None:
                return False
            item["approved"] = approved
            event = item["_event"]
            event.set()
            return True
