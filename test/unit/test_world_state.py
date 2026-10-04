from src.world_state import WorldStateStore
from src.roles import NexusRole, RoleRouter


def test_world_state_persists_and_updates(tmp_path):
    store = WorldStateStore(str(tmp_path / "world.json"))
    business = store.upsert("business", {"name": "ABC Renovations", "status": "interested"})
    assert store.get("business", business["id"])["data"]["name"] == "ABC Renovations"
    store.update_status("business", business["id"], "sold")
    assert store.get("business", business["id"])["data"]["status"] == "sold"


def test_world_state_filters_entities(tmp_path):
    store = WorldStateStore(str(tmp_path / "world.json"))
    store.upsert("lead", {"business_id": "a", "status": "interested"})
    store.upsert("lead", {"business_id": "b", "status": "new"})
    assert len(store.list("lead", "interested")) == 1


def test_roles_route_without_separate_brains():
    assert RoleRouter.for_event("call.outcome.changed") is NexusRole.BUSINESS
    assert RoleRouter.for_event("research.completed") is NexusRole.RESEARCHER
    assert RoleRouter.for_event("project.approval.requested") is NexusRole.BUILDER
