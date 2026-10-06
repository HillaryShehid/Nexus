from src.autonomy import AutonomyEngine
from src.events import EventStore, NexusEvent
from src.brain.task_manager import TaskManager
from src.roles import NexusRole
from src.world_state import WorldStateStore


def make_engine(tmp_path):
    events = EventStore(str(tmp_path / "events.json"))
    tasks = TaskManager()
    tasks.path = str(tmp_path / "tasks.json")
    world = WorldStateStore(str(tmp_path / "world.json"))
    return events, tasks, world, AutonomyEngine(events, tasks, world)


def test_interested_event_updates_world_and_routes_to_research(tmp_path):
    events, tasks, world, engine = make_engine(tmp_path)
    business_id = "business-abc"
    event = events.append(NexusEvent(
        type="call.outcome.changed",
        source="caller",
        payload={
            "business_id": business_id,
            "company_name": "ABC Renovations",
            "outcome": "interested",
        },
    ))

    result = engine.reconcile(event_id=event["id"])

    assert result["processed"] == 1
    assert result["tasks_created"] == 1
    assert events.pending() == []
    business = world.get("business", business_id)
    assert business["data"]["status"] == "interested"
    task = result["tasks"][0]
    assert task["role"] == NexusRole.RESEARCHER.value
    assert task["business_id"] == business_id
    assert "research" in task["allowed_entities"]


def test_sold_event_routes_to_builder(tmp_path):
    events, tasks, world, engine = make_engine(tmp_path)
    event = events.append(NexusEvent(
        type="call.outcome.changed",
        source="caller",
        payload={"business_id": "b1", "company_name": "ABC", "outcome": "sold"},
    ))

    result = engine.reconcile(event_id=event["id"])

    assert result["tasks_created"] == 1
    assert result["tasks"][0]["role"] == NexusRole.BUILDER.value
    assert result["tasks"][0]["business_id"] == "b1"
    assert world.get("business", "b1")["data"]["status"] == "sold"


def test_approval_event_requires_approval_and_waits(tmp_path):
    events, tasks, world, engine = make_engine(tmp_path)
    event = events.append(NexusEvent(
        type="project.approval.requested",
        source="builder",
        payload={"project_id": "project-1", "project_name": "ABC website"},
    ))

    result = engine.reconcile(event_id=event["id"])

    assert result["tasks_created"] == 1
    task = result["tasks"][0]
    assert task["status"] == "waiting_for_approval"
    assert task["requires_approval"] == "true"
    assert task["approval_status"] == "pending"
