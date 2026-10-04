from src.autonomy import AutonomyEngine
from src.events import EventStore, NexusEvent
from src.brain.task_manager import TaskManager
from src.roles import NexusRole
from src.world_state import WorldStateStore


def test_interested_event_updates_world_and_routes_to_research(tmp_path):
    events = EventStore(str(tmp_path / "events.json"))
    tasks = TaskManager()
    tasks.path = str(tmp_path / "tasks.json")
    world = WorldStateStore(str(tmp_path / "world.json"))
    engine = AutonomyEngine(events, tasks, world)

    business_id = "business-abc"
    events.append(NexusEvent(
        type="call.outcome.changed",
        source="caller",
        payload={
            "business_id": business_id,
            "company_name": "ABC Renovations",
            "outcome": "interested",
        },
    ))

    result = engine.reconcile()
    assert result["tasks_created"] == 1
    business = world.get("business", business_id)
    assert business["data"]["status"] == "interested"
    task = result["tasks"][0]
    assert task["role"] == NexusRole.RESEARCHER.value


def test_sold_event_routes_to_builder(tmp_path):
    events = EventStore(str(tmp_path / "events.json"))
    tasks = TaskManager()
    tasks.path = str(tmp_path / "tasks.json")
    world = WorldStateStore(str(tmp_path / "world.json"))
    engine = AutonomyEngine(events, tasks, world)

    events.append(NexusEvent(
        type="call.outcome.changed",
        source="caller",
        payload={"business_id": "b1", "company_name": "ABC", "outcome": "sold"},
    ))

    result = engine.reconcile()
    assert result["tasks"][0]["role"] == NexusRole.BUILDER.value
