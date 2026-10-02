from src.access import Authorization
from src.permissions import PermissionSystem


def test_permission_system_fails_closed_without_authenticated_owner():
    permissions = PermissionSystem(Authorization())
    result = permissions.evaluate_clearance("calculator", {"expression": "2 + 2"})
    assert result["status"] == "blocked"
    assert "Authenticated owner" in result["reason"]


def test_permission_system_accepts_known_owner():
    permissions = PermissionSystem(Authorization(), actor_id="hilal")
    result = permissions.evaluate_clearance("calculator", {"expression": "2 + 2"})
    assert result["status"] == "allowed"
