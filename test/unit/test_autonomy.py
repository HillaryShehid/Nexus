import json

from src.autonomy import AutonomyEngine
from src.brain.task_manager import TaskManager
from src.events import EventStore, NexusEvent


def test_interested_call_event_wakes_nexus_and_creates_research_task(tmp_path):
    events = EventStore(str(tmp_path / "events.json"))
    tasks = TaskManager()
    tasks.path = str(tmp_path / "tasks.json")
    engine = AutonomyEngine(events, tasks)

    event = events.append(NexusEvent(
        type="call.outcome.changed",
        source="nexus_core",
        payload={"company_name": "ABC Renovations", "outcome": "interested"},
    ))

    result = engine.reconcile()

    assert result["processed"] == 1
    assert result["tasks_created"] == 1
    assert events.pending() == []
    task = tasks.active()[0]
    assert "ABC Renovations" in task["goal"]
    assert task["priority"] == "high"


def test_sold_event_queues_builder_preparation(tmp_path):
    events = EventStore(str(tmp_path / "events.json"))
    tasks = TaskManager()
    tasks.path = str(tmp_path / "tasks.json")
    engine = AutonomyEngine(events, tasks)

    events.append(NexusEvent(
        type="call.outcome.changed",
        source="calls",
        payload={"company_name": "North Star Roofing", "outcome": "sold"},
    ))

    result = engine.reconcile()

    assert result["tasks_created"] == 1
    assert "Nexus Builder" in tasks.active()[0]["goal"]


def test_email_event_becomes_actionable_task(tmp_path):
    events = EventStore(str(tmp_path / "events.json"))
    tasks = TaskManager()
    tasks.path = str(tmp_path / "tasks.json")
    engine = AutonomyEngine(events, tasks)

    events.append(NexusEvent(
        type="email.received",
        source="email",
        payload={"sender": "client@example.com", "subject": "We are ready"},
    ))

    engine.reconcile()

    task = tasks.active()[0]
    assert "client@example.com" in task["goal"]
    assert "We are ready" in task["goal"]


def test_event_store_is_durable_and_bounded(tmp_path):
    path = str(tmp_path / "events.json")
    store = EventStore(path)
    store.append(NexusEvent("test.event", "test", {"value": "hello"}))

    reloaded = EventStore(path)
    pending = reloaded.pending()

    assert len(pending) == 1
    assert pending[0]["type"] == "test.event"
    assert pending[0]["payload"]["value"] == "hello"


def test_unknown_events_are_still_visible_to_nexus(tmp_path):
    events = EventStore(str(tmp_path / "events.json"))
    tasks = TaskManager()
    tasks.path = str(tmp_path / "tasks.json")
    engine = AutonomyEngine(events, tasks)

    events.append(NexusEvent("website.changed", "builder", {"project": "ABC"}))
    engine.reconcile()

    assert "website.changed" in tasks.active()[0]["goal"]
