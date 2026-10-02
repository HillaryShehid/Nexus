import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from uuid import uuid4

from src.registry import WORKSPACE_DIR


class TaskManager:
    """Bounded, atomic persistent task queue with resumable checkpoints."""

    MAX_TASKS = 50
    MAX_STORE_BYTES = 1_000_000
    MAX_METADATA_FIELDS = 16
    MAX_METADATA_VALUE_CHARS = 2_000
    MAX_METADATA_KEY_CHARS = 64
    STATUSES = frozenset({"queued", "running", "waiting", "waiting_for_approval", "completed", "failed", "cancelled"})
    PRIORITIES = frozenset({"low", "normal", "high"})
    RESERVED_FIELDS = frozenset({"id", "goal", "priority", "status", "created_at", "updated_at"})
    _lock = threading.RLock()

    def __init__(self):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self.path = os.path.abspath(os.path.join(WORKSPACE_DIR, "nexus_tasks.json"))

    def _load(self):
        if not os.path.exists(self.path):
            return []
        if os.path.islink(self.path) or not os.path.isfile(self.path):
            raise ValueError("Task store must be a regular, non-symlink file.")
        if os.path.getsize(self.path) > self.MAX_STORE_BYTES:
            raise ValueError("Task store exceeds the configured size limit.")
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Task store is unreadable or contains invalid JSON.") from exc
        if not isinstance(data, list) or len(data) > self.MAX_TASKS:
            raise ValueError("Task store has an invalid collection shape.")
        required = {"id", "goal", "priority", "status", "created_at", "updated_at"}
        seen_ids = set()
        for task in data:
            if not isinstance(task, dict) or not required.issubset(task):
                raise ValueError("Task store contains a malformed task record.")
            if (not all(isinstance(task.get(key), str) for key in required)
                    or task["status"] not in self.STATUSES
                    or task["priority"] not in self.PRIORITIES):
                raise ValueError("Task store contains invalid task fields.")
            extra = set(task) - required
            if (task["id"] in seen_ids or len(extra) > self.MAX_METADATA_FIELDS
                    or any(not isinstance(key, str) or not key.isidentifier()
                           or len(key) > self.MAX_METADATA_KEY_CHARS
                           or key in self.RESERVED_FIELDS for key in extra)
                    or any(not isinstance(task[key], str)
                           or len(task[key]) > self.MAX_METADATA_VALUE_CHARS for key in extra)):
                raise ValueError("Task store contains invalid or excessive metadata.")
            seen_ids.add(task["id"])
        return data

    def _save(self, tasks):
        fd, temp = tempfile.mkstemp(dir=os.path.dirname(self.path), prefix=".nexus_tasks_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(tasks[-self.MAX_TASKS:], f, indent=2, ensure_ascii=False)
                f.flush(); os.fsync(f.fileno())
            if os.path.getsize(temp) > self.MAX_STORE_BYTES:
                raise ValueError("Task store exceeds the configured size limit.")
            os.replace(temp, self.path)
        except Exception:
            try: os.unlink(temp)
            except OSError: pass
            raise

    def create(self, goal, priority="normal", created_by=None, assigned_to=None, requires_approval=False):
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("Task goal must be non-empty text.")
        if not isinstance(priority, str) or priority not in self.PRIORITIES:
            priority = "normal"
        now = datetime.now(timezone.utc).isoformat()
        task = {
            "id": uuid4().hex, "goal": goal.strip()[:800], "priority": priority,
            "status": "queued", "created_at": now, "updated_at": now,
            "created_by": str(created_by or "")[:100], "assigned_to": str(assigned_to or "")[:100],
            "progress": "0", "checkpoint": "", "result": "", "error": "", "attempts": "0",
            "requires_approval": "true" if requires_approval else "false",
            "approval_status": "pending" if requires_approval else "not_required",
        }
        with self._lock:
            tasks = self._load(); tasks.append(task); self._save(tasks)
        return task

    def get(self, task_id):
        with self._lock:
            return next((task for task in self._load() if task["id"] == task_id), None)

    def update(self, task_id, status, **fields):
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("Task id must be non-empty text.")
        if not isinstance(status, str) or status not in self.STATUSES:
            raise ValueError("Unknown task status.")
        if len(fields) > self.MAX_METADATA_FIELDS:
            raise ValueError("Too many task metadata fields.")
        if any(key in self.RESERVED_FIELDS for key in fields):
            raise ValueError("Task identity and lifecycle fields cannot be overridden.")
        if any(not isinstance(key, str) or not key.isidentifier() or len(key) > self.MAX_METADATA_KEY_CHARS for key in fields):
            raise ValueError("Task metadata keys must be short identifiers.")
        if any(not isinstance(value, str) for value in fields.values()):
            raise ValueError("Task metadata values must be text.")
        with self._lock:
            tasks = self._load()
            for task in tasks:
                if task["id"] == task_id:
                    if len((set(task) - self.RESERVED_FIELDS) | set(fields)) > self.MAX_METADATA_FIELDS:
                        raise ValueError("Too many task metadata fields.")
                    task["status"] = status; task["updated_at"] = datetime.now(timezone.utc).isoformat()
                    task.update({key: value[:self.MAX_METADATA_VALUE_CHARS] for key, value in fields.items()})
                    self._save(tasks); return task
        return None

    def checkpoint(self, task_id, progress, checkpoint, status="running"):
        return self.update(task_id, status, progress=str(progress)[:20], checkpoint=str(checkpoint)[:2000])

    def active(self):
        with self._lock:
            return [task for task in self._load() if task["status"] in {"queued", "running", "waiting", "waiting_for_approval"}]

    def list_active(self):
        return self.active()
