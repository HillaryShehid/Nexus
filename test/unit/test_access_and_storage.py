from src.access import Authorization, DEFAULT_USERS, Role
from src.storage import MemoryStore, TaskStore


def test_default_team_roles_are_centralized():
    assert DEFAULT_USERS["hilal"].role is Role.OWNER
    assert DEFAULT_USERS["hamza"].role is Role.WORKER
    assert DEFAULT_USERS["talha"].role is Role.WORKER
    assert DEFAULT_USERS["zachariah"].role is Role.WORKER
    assert DEFAULT_USERS["mustafa"].role is Role.WORKER


def test_authorization_centralizes_high_impact_actions():
    auth = Authorization()
    assert auth.can("hilal", "purchase_domain")
    assert not auth.can("hamza", "purchase_domain")
    assert auth.can("hamza", "research_company")


def test_storage_interfaces_are_explicit():
    assert MemoryStore.__abstractmethods__ == {"get", "save", "search", "delete"}
    assert TaskStore.__abstractmethods__ == {"create", "get", "update", "list_active"}
