from src.access import Authorization, DEFAULT_USERS, Role
from src.storage import MemoryStore, TaskStore


def test_personal_owner_identity_is_centralized():
    assert set(DEFAULT_USERS) == {"hilal"}
    assert DEFAULT_USERS["hilal"].role is Role.OWNER
    assert Authorization().can("hilal", "read_memory")


def test_unknown_users_cannot_act():
    auth = Authorization()
    assert not auth.can("someone_else", "read_memory")
    assert auth.describe("someone_else")["authenticated"] is False


def test_owner_controls_high_impact_actions():
    auth = Authorization()
    assert auth.can("hilal", "spend_money")
    assert auth.can("hilal", "self_modify_foundation")


def test_storage_interfaces_are_explicit():
    assert MemoryStore.__abstractmethods__ == {"get", "save", "search", "delete"}
    assert TaskStore.__abstractmethods__ == {"create", "get", "update", "list_active"}
