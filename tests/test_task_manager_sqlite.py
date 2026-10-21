import json
import sqlite3

import pytest

from src.brain.task_manager import TaskManager


def test_task_state_persists_across_manager_instances(tmp_path):
    db = tmp_path / "nexus_state.db"
    first = TaskManager(path=str(db))
    task = first.create("research a prospect")
    assert first.checkpoint(task["id"], 50, "sources collected")["status"] == "running"

    second = TaskManager(path=str(db))
    restored = second.get(task["id"])
    assert restored["goal"] == "research a prospect"
    assert restored["progress"] == "50"
    assert restored["checkpoint"] == "sources collected"
    assert restored["id"] in {item["id"] for item in second.active()}


def test_sqlite_uses_wal_mode(tmp_path):
    db = tmp_path / "nexus_state.db"
    TaskManager(path=str(db))
    with sqlite3.connect(db) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_task_updates_reject_reserved_fields(tmp_path):
    manager = TaskManager(path=str(tmp_path / "state.db"))
    task = manager.create("safe task")
    with pytest.raises(ValueError):
        manager.update(task["id"], "running", goal="changed")


def test_legacy_json_is_imported_and_preserved(tmp_path):
    legacy = tmp_path / "nexus_tasks.json"
    record = {
        "id": "legacy-task", "goal": "old task", "priority": "normal",
        "status": "queued", "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00", "checkpoint": "",
        "progress": "0", "result": "", "error": "", "attempts": "0",
        "created_by": "", "requires_approval": "false",
        "approval_status": "not_required",
    }
    legacy.write_text(json.dumps([record]), encoding="utf-8")
    manager = TaskManager(path=str(tmp_path / "state.db"), legacy_path=str(legacy))
    assert manager.get("legacy-task")["goal"] == "old task"
    assert json.loads(legacy.read_text(encoding="utf-8"))[0]["id"] == "legacy-task"


def test_invalid_legacy_json_is_not_silently_discarded(tmp_path):
    legacy = tmp_path / "nexus_tasks.json"
    legacy.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        TaskManager(path=str(tmp_path / "state.db"), legacy_path=str(legacy))
    assert legacy.read_text(encoding="utf-8") == "{broken"
