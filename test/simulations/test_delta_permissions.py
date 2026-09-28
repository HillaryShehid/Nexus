from src.permissions import PermissionSystem

def test_unknown_tool_is_blocked():
    assert PermissionSystem().evaluate_clearance("not_a_tool", {})["status"] == "blocked"

def test_invalid_action_is_blocked():
    result = PermissionSystem().evaluate_clearance("file_system", {"action":"delete","path":"x.txt"})
    assert result["status"] == "blocked"

def test_file_write_requires_approval():
    result = PermissionSystem().evaluate_clearance("file_system", {"action":"write","path":"x.txt","content":"hello"})
    assert result["status"] == "approval_required"

def test_code_execution_requires_approval():
    result = PermissionSystem().evaluate_clearance("code_tester", {"python_code":"print('hello')"})
    assert result["status"] == "approval_required"

def test_unknown_permission_state_fails_closed(mocker):
    from src.core import NexusCore
    brain = mocker.MagicMock()
    mocker.patch("src.core.AIBrain", return_value=brain)
    brain.generate.return_value = {"success":True,"content":'{"plan":[{"step":1,"tool":"calculator","args":{"expression":"2+2"},"description":"Calculate value"}]}',"error":None}
    nexus = NexusCore()
    mocker.patch.object(nexus.permissions, "evaluate_clearance", return_value={"status":"mystery","reason":"bad state"})
    nexus.tools.execute = mocker.MagicMock()
    result = nexus.handle_request("Calculate 2+2")
    assert "Final" not in result
    nexus.tools.execute.assert_called_once()
    assert not any(call.args[0] == "calculator" for call in nexus.tools.execute.call_args_list)
