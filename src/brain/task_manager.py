"""SQLite-backed, transactional task queue with crash-safe checkpoints.

Legacy nexus_tasks.json files are imported once on first startup and preserved as
a migration backup. SQLite WAL transactions are used for subsequent task writes.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from src.registry import WORKSPACE_DIR


class TaskManager:
    """Persistent task queue; full task history is stored independently of chat."""

    MAX_TASKS = 50
    MAX_STORE_BYTES = 1_000_000
    MAX_METADATA_FIELDS = 16
    MAX_METADATA_VALUE_CHARS = 2_000
    MAX_METADATA_KEY_CHARS = 64
    STATUSES = frozenset({
        "queued", "running", "waiting", "waiting_for_approval",
        "completed", "failed", "cancelled",
    })
    PRIORITIES = frozenset({"low", "normal", "high"})
    RESERVED_FIELDS = frozenset({
        "id", "goal", "priority", "status", "created_at", "updated_at",
    })

    def __init__(self, path: str | None = None, legacy_path: str | None = None):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self._lock = threading.RLock()
        self.legacy_path = os.path.abspath(
            legacy_path or os.path.join(WORKSPACE_DIR, "nexus_tasks.json")
        ) if path is None else legacy_path
        self.path = os.path.abspath(path or os.path.join(WORKSPACE_DIR, "nexus_state.db"))
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._initialize_database()

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        self._path = os.path.abspath(value)
        # Preserve the historical test/integration seam that redirects the
        # manager to a temporary path after construction.
        if hasattr(self, "_lock"):
            self.legacy_path = None
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            self._initialize_database()

    def _assert_database_file(self):
        if os.path.lexists(self.path) and os.path.islink(self.path):
            raise ValueError("Task store must be a regular, non-symlink file.")
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            return
        with open(self.path, "rb") as handle:
            header = handle.read(16)
        if header == b"SQLite format 3\x00":
            return
        if os.path.getsize(self.path) > self.MAX_STORE_BYTES:
            raise ValueError("Task store exceeds the configured size limit.")
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Task store is unreadable or contains invalid JSON.") from exc
        if not isinstance(data, list) or len(data) > self.MAX_TASKS:
            raise ValueError("Task store has an invalid collection shape.")
        required = {"id", "goal", "priority", "status", "created_at", "updated_at"}
        for record in data:
            if not isinstance(record, dict) or not required.issubset(record):
                raise ValueError("Task store contains a malformed task record.")
            self._validate_record(record)
        raise ValueError("Task store is a legacy JSON file; reopen Nexus to migrate it to SQLite.")

    @contextmanager
    def _connect(self):
        self._assert_database_file()
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        finally:
            connection.close()

    def _initialize_database(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status_sequence
                ON tasks(status, sequence)
            """)
        self._migrate_legacy_json_once()

    def _validate_record(self, task):
        required = {"id", "goal", "priority", "status", "created_at", "updated_at"}
        if not isinstance(task, dict) or not required.issubset(task):
            raise ValueError("Task store contains a malformed task record.")
        if not all(isinstance(task.get(key), str) for key in required):
            raise ValueError("Task store contains invalid task fields.")
        if task["status"] not in self.STATUSES or task["priority"] not in self.PRIORITIES:
            raise ValueError("Task store contains invalid status or priority.")
        extra = set(task) - required
        if (
            len(extra) > self.MAX_METADATA_FIELDS
            or any(not isinstance(key, str) or not key.isidentifier()
                   or len(key) > self.MAX_METADATA_KEY_CHARS
                   or key in self.RESERVED_FIELDS for key in extra)
            or any(not isinstance(task[key], str)
                   or len(task[key]) > self.MAX_METADATA_VALUE_CHARS for key in extra)
        ):
            raise ValueError("Task store contains invalid or excessive metadata.")
        return task

    def _migrate_legacy_json_once(self):
        if not self.legacy_path or not os.path.isfile(self.legacy_path):
            return
        with self._lock, self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            if count:
                return
            if os.path.islink(self.legacy_path):
                raise ValueError("Legacy task store must not be a symlink.")
            try:
                if os.path.getsize(self.legacy_path) > 1_000_000:
                    raise ValueError("Legacy task store exceeds the migration size limit.")
                with open(self.legacy_path, "r", encoding="utf-8") as handle:
                    records = json.load(handle)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("Legacy task store is unreadable; original data was preserved.") from exc
            if not isinstance(records, list) or len(records) > self.MAX_TASKS:
                raise ValueError("Legacy task store has an invalid collection shape.")
            seen = set()
            for record in records:
                self._validate_record(record)
                if record["id"] in seen:
                    raise ValueError("Legacy task store contains duplicate task IDs.")
                seen.add(record["id"])
            conn.execute("BEGIN IMMEDIATE")
            try:
                for record in records:
                    self._insert_record(conn, record)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _insert_record(self, conn, task):
        conn.execute(
            """INSERT INTO tasks(task_id, status, created_at, updated_at, record_json)
               VALUES (?, ?, ?, ?, ?)""",
            (
                task["id"], task["status"], task["created_at"], task["updated_at"],
                json.dumps(task, ensure_ascii=False, separators=(",", ":")),
            ),
        )

    def _load(self, conn):
        rows = conn.execute("SELECT record_json FROM tasks ORDER BY sequence").fetchall()
        records = []
        for row in rows:
            try:
                record = json.loads(row["record_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError("SQLite task record is corrupt; refusing to overwrite state.") from exc
            records.append(self._validate_record(record))
        return records

    def _save(self, conn, tasks):
        # Caller holds a write transaction. Atomic replacement avoids partial task lists.
        conn.execute("DELETE FROM tasks")
        for task in tasks[-self.MAX_TASKS:]:
            self._insert_record(conn, task)

    def create(self, goal, priority="normal", created_by=None, requires_approval=False):
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("Task goal must be non-empty text.")
        if not isinstance(priority, str) or priority not in self.PRIORITIES:
            priority = "normal"
        now = datetime.now(timezone.utc).isoformat()
        task = {
            "id": uuid4().hex, "goal": goal.strip()[:800], "priority": priority,
            "status": "queued", "created_at": now, "updated_at": now,
            "created_by": str(created_by or "")[:100],
            "progress": "0", "checkpoint": "", "result": "", "error": "", "attempts": "0",
            "requires_approval": "true" if requires_approval else "false",
            "approval_status": "pending" if requires_approval else "not_required",
        }
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                tasks = self._load(conn)
                tasks.append(task)
                self._save(conn, tasks)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return task

    def get(self, task_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT record_json FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        if row is None:
            return None
        try:
            return self._validate_record(json.loads(row["record_json"]))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("SQLite task record is corrupt.") from exc

    def update(self, task_id, status, **fields):
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("Task id must be non-empty text.")
        if not isinstance(status, str) or status not in self.STATUSES:
            raise ValueError("Unknown task status.")
        if len(fields) > self.MAX_METADATA_FIELDS:
            raise ValueError("Too many task metadata fields.")
        if any(key in self.RESERVED_FIELDS for key in fields):
            raise ValueError("Task identity and lifecycle fields cannot be overridden.")
        if any(not isinstance(key, str) or not key.isidentifier()
               or len(key) > self.MAX_METADATA_KEY_CHARS for key in fields):
            raise ValueError("Task metadata keys must be short identifiers.")
        if any(not isinstance(value, str) for value in fields.values()):
            raise ValueError("Task metadata values must be text.")
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                tasks = self._load(conn)
                for task in tasks:
                    if task["id"] == task_id:
                        if len((set(task) - self.RESERVED_FIELDS) | set(fields)) > self.MAX_METADATA_FIELDS:
                            raise ValueError("Too many task metadata fields.")
                        task["status"] = status
                        task["updated_at"] = datetime.now(timezone.utc).isoformat()
                        task.update({
                            key: value[:self.MAX_METADATA_VALUE_CHARS]
                            for key, value in fields.items()
                        })
                        self._validate_record(task)
                        self._save(conn, tasks)
                        conn.commit()
                        return task
                conn.commit()
                return None
            except Exception:
                conn.rollback()
                raise

    def checkpoint(self, task_id, progress, checkpoint, status="running"):
        return self.update(
            task_id, status,
            progress=str(progress)[:20],
            checkpoint=str(checkpoint)[:self.MAX_METADATA_VALUE_CHARS],
        )

    def active(self):
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT record_json FROM tasks
                   WHERE status IN ('queued', 'running', 'waiting', 'waiting_for_approval')
                   ORDER BY sequence"""
            ).fetchall()
        active = []
        for row in rows:
            try:
                active.append(self._validate_record(json.loads(row["record_json"])))
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError("SQLite task record is corrupt.") from exc
        return active

    def list_active(self):
        return self.active()
