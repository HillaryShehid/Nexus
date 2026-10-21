from types import SimpleNamespace

from src.security_sandbox import SecureCodeSandbox


def test_sandbox_rejects_empty_or_oversized_code_without_starting_docker():
    sandbox = SecureCodeSandbox()
    assert not sandbox.execute_untrusted_code("   ")["success"]
    assert not sandbox.execute_untrusted_code("x" * 3001)["success"]


def test_sandbox_fails_closed_when_docker_sdk_is_missing(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_docker(name, *args, **kwargs):
        if name == "docker":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_docker)
    result = SecureCodeSandbox().execute_untrusted_code("print('hello')")
    assert result["success"] is False
    assert "was not executed" in result["error"]


def test_sandbox_uses_restricted_container(monkeypatch):
    import sys

    calls = {}

    class FakeContainer:
        status = "created"
        attrs = {"State": {"ExitCode": 0}}

        def start(self):
            self.status = "exited"

        def reload(self):
            return None

        def logs(self, **kwargs):
            return b"hello from sandbox"

        def remove(self, **kwargs):
            calls["removed"] = True

        def kill(self):
            calls["killed"] = True

    container = FakeContainer()

    class FakeContainers:
        def create(self, **kwargs):
            calls["config"] = kwargs
            return container

    class FakeImages:
        def get(self, image):
            calls["image"] = image

    class FakeClient:
        images = FakeImages()
        containers = FakeContainers()

        def close(self):
            calls["closed"] = True

    monkeypatch.setitem(sys.modules, "docker", SimpleNamespace(from_env=lambda: FakeClient()))
    result = SecureCodeSandbox().execute_untrusted_code("print('hello')")
    assert result["success"] is True
    assert "hello from sandbox" in result["result"]
    config = calls["config"]
    assert config["network_mode"] == "none"
    assert config["read_only"] is True
    assert config["cap_drop"] == ["ALL"]
    assert config["security_opt"] == ["no-new-privileges:true"]
    assert config["pids_limit"] <= 128
    assert calls["removed"] is True
    assert calls["closed"] is True
