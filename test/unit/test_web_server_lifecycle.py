from types import SimpleNamespace

import web_server


def test_web_requests_reuse_one_nexus_brain(monkeypatch):
    instances = []

    class FakeNexusCore:
        def __init__(self, actor_id):
            self.actor_id = actor_id
            self.permissions = SimpleNamespace(approval_handler=None)
            instances.append(self)

    monkeypatch.setattr(web_server, "NexusCore", FakeNexusCore)
    monkeypatch.setattr(web_server.Handler, "nexus", None)

    first_handler = web_server.Handler.__new__(web_server.Handler)
    second_handler = web_server.Handler.__new__(web_server.Handler)

    first = first_handler._get_nexus()
    second = second_handler._get_nexus()

    assert first is second
    assert first.actor_id == "hilal"
    assert len(instances) == 1
