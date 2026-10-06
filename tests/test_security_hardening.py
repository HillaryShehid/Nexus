from unittest.mock import patch

from src.model import AIBrain
from src.permissions import PermissionSystem
from src.tools import ToolSystem
from web_server import _is_loopback_host


def test_elevated_tools_route_to_explicit_approval():
    permissions = PermissionSystem(actor_id="hilal")

    assert permissions.evaluate_clearance(
        "file_system",
        {"action": "write", "path": "example.txt", "content": "hello"},
    )["status"] == "approval_required"

    assert permissions.evaluate_clearance(
        "email",
        {"action": "send", "to": "test@example.com", "subject": "Hi", "body": "Hello"},
    )["status"] == "approval_required"

    assert permissions.evaluate_clearance(
        "code_tester",
        {"python_code": "print('hello')"},
    )["status"] == "approval_required"


def test_elevated_tools_enter_approval_flow_without_actor():
    permissions = PermissionSystem()

    assert permissions.evaluate_clearance(
        "file_system",
        {"action": "write", "path": "example.txt", "content": "hello"},
    )["status"] == "approval_required"

    assert permissions.evaluate_clearance(
        "code_tester",
        {"python_code": "print('hello')"},
    )["status"] == "approval_required"


def test_provider_fallback_never_reuses_primary_provider_model(monkeypatch):
    brain = AIBrain.__new__(AIBrain)
    brain.provider_models = {
        "gemini": "gemini-default",
        "groq": "groq-default",
    }
    monkeypatch.setenv("NEXUS_NORMAL_MODEL", "gemini-custom")

    assert brain._resolve_model("gemini", "normal", "gemini") == "gemini-custom"
    assert brain._resolve_model("groq", "normal", "gemini") == "groq-default"

    monkeypatch.setenv("NEXUS_GROQ_NORMAL_MODEL", "groq-custom")
    assert brain._resolve_model("groq", "normal", "gemini") == "groq-custom"


def test_remote_bind_hosts_are_not_treated_as_loopback():
    assert _is_loopback_host("127.0.0.1")
    assert _is_loopback_host("localhost")
    assert _is_loopback_host("::1")
    assert not _is_loopback_host("0.0.0.0")
    assert not _is_loopback_host("192.168.1.10")


def test_code_tester_requires_docker_instead_of_host_python():
    tools = ToolSystem()
    with patch("src.tools.shutil.which", return_value=None):
        result = tools.tool_code_tester("print('should not run on host')")

    assert result["success"] is False
    assert "Docker is required" in result["error"]


def test_code_tester_command_is_restricted(monkeypatch):
    tools = ToolSystem()
    monkeypatch.setattr("src.tools.shutil.which", lambda name: "/usr/bin/docker")

    class FakeProcess:
        pid = 123

        def communicate(self, timeout=None):
            return "ok", ""

        returncode = 0

    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        return FakeProcess()

    monkeypatch.setattr("src.tools.subprocess.Popen", fake_popen)

    result = tools.tool_code_tester("print('ok')")

    assert result["success"] is True
    command = captured["command"]
    assert "--network" in command and command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert "--cap-drop" in command and command[command.index("--cap-drop") + 1] == "ALL"
    assert "--pids-limit" in command
    assert "--memory" in command
    assert "--mount" in command
    assert "--security-opt" in command
    assert "python:3.12-alpine" in command
