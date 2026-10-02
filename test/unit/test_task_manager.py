import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.brain.task_manager import TaskManager


def test_task_lifecycle_is_bounded_and_metadata_cannot_replace_identity():
    manager = TaskManager()
    task = manager.create("  finish the audit  ", priority="high")

    assert task["goal"] == "finish the audit"
    assert task["priority"] == "high"
    assert manager.active() == [task]

    updated = manager.update(task["id"], "completed", summary="verified")
    assert updated["status"] == "completed"
    assert updated["summary"] == "verified"
    assert manager.active() == []

    with pytest.raises(ValueError):
        manager.update(task["id"], "queued", id="replacement")


def test_task_checkpoints_are_resumable():
    manager = TaskManager()
    task = manager.create("prepare a study plan", created_by="hilal")
    checkpointed = manager.checkpoint(task["id"], 42, "completed research; waiting for build")

    assert checkpointed["status"] == "running"
    assert checkpointed["progress"] == "42"
    assert checkpointed["checkpoint"] == "completed research; waiting for build"
    assert manager.get(task["id"])["checkpoint"] == "completed research; waiting for build"


def test_approval_tasks_have_explicit_approval_state():
    manager = TaskManager()
    task = manager.create("change an important setting", created_by="hilal", requires_approval=True)
    assert task["requires_approval"] == "true"
    assert task["approval_status"] == "pending"
    waiting = manager.update(task["id"], "waiting_for_approval")
    assert waiting["status"] == "waiting_for_approval"
    assert manager.active() == [waiting]

def test_create_rejects_empty_or_non_text_goals():
    manager = TaskManager()
    for goal in ("", "  ", None, 42):
        with pytest.raises(ValueError):
            manager.create(goal)
    assert manager.active() == []


def test_unknown_status_is_rejected():
    manager = TaskManager()
    task = manager.create("persist state")
    with pytest.raises(ValueError):
        manager.update(task["id"], "permitted")
    assert manager.active()[0]["status"] == "queued"


def test_corrupt_store_is_preserved_instead_of_overwritten():
    manager = TaskManager()
    original = "{not valid json"
    with open(manager.path, "w", encoding="utf-8") as handle:
        handle.write(original)

    with pytest.raises(ValueError, match="invalid JSON"):
        manager.create("must not erase the broken store")

    with open(manager.path, "r", encoding="utf-8") as handle:
        assert handle.read() == original


def test_malformed_and_oversized_store_fail_closed():
    manager = TaskManager()
    with open(manager.path, "w", encoding="utf-8") as handle:
        json.dump([{"id": "partial"}], handle)
    with pytest.raises(ValueError, match="malformed"):
        manager.active()

    with open(manager.path, "w", encoding="utf-8") as handle:
        handle.write(" " * (manager.MAX_STORE_BYTES + 1))
    with pytest.raises(ValueError, match="size limit"):
        manager.active()


def test_concurrent_task_creates_do_not_lose_updates():
    managers = [TaskManager() for _ in range(20)]
    with ThreadPoolExecutor(max_workers=10) as pool:
        tasks = list(pool.map(lambda pair: pair[0].create(pair[1]), zip(managers, map(str, range(20)))))

    saved = TaskManager().active()
    assert len(saved) == 20
    assert len({task["id"] for task in tasks}) == 20
    assert {task["id"] for task in saved} == {task["id"] for task in tasks}


def test_task_store_symlink_is_rejected(tmp_path):
    manager = TaskManager()
    target = os.path.join(os.path.dirname(manager.path), "outside-task-store.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump([], handle)
    try:
        os.symlink(target, manager.path)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this platform.")

    with pytest.raises(ValueError, match="symlink"):
        manager.active()
