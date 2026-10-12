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


def test_authenticated_owner_gets_approval_required_for_elevated_actions():
    permissions = PermissionSystem(Authorization(), actor_id="hilal")
    cases = [
        ("file_system", {"action": "write", "path": "notes.txt", "content": "hello"}),
        ("email", {"action": "send", "to": "client@example.com", "subject": "Update", "body": "Hello"}),
        ("code_tester", {"python_code": "print('test')"}),
    ]

    for tool_name, args in cases:
        result = permissions.evaluate_clearance(tool_name, args)
        assert result["status"] == "approval_required", (tool_name, result)
        assert result["authenticated"] is True


def test_non_destructive_reads_remain_allowed_for_authenticated_owner():
    permissions = PermissionSystem(Authorization(), actor_id="hilal")

    assert permissions.evaluate_clearance("email", {"action": "read"})["status"] == "allowed"
    assert permissions.evaluate_clearance(
        "file_system", {"action": "read", "path": "notes.txt"}
    )["status"] == "allowed"


def test_invalid_elevated_action_is_blocked_before_approval():
    permissions = PermissionSystem(Authorization(), actor_id="hilal")
    result = permissions.evaluate_clearance(
        "file_system", {"action": "delete", "path": "notes.txt"}
    )
    assert result["status"] == "blocked"
