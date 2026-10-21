import os

from fastapi.testclient import TestClient

from src import api


client = TestClient(api.app)


def setup_function():
    api._get_core.cache_clear()


def test_health_does_not_require_authentication():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "nexus-api"}


def test_chat_fails_closed_when_api_token_is_missing(monkeypatch):
    monkeypatch.delenv("NEXUS_API_TOKEN", raising=False)
    response = client.post("/v1/chat", json={"message": "Hi"})
    assert response.status_code == 503


def test_chat_rejects_missing_or_invalid_token(monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", "x" * 40)
    response = client.post("/v1/chat", json={"message": "Hi"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_chat_uses_nexus_core_only_after_authentication(monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", "test-token-" + "x" * 40)

    class FakeCore:
        def handle_request(self, message):
            return f"Nexus received: {message}"

    monkeypatch.setattr(api, "_get_core", lambda: FakeCore())
    response = client.post(
        "/v1/chat",
        headers={"Authorization": "Bearer " + os.environ["NEXUS_API_TOKEN"]},
        json={"message": "Hello Nexus"},
    )
    assert response.status_code == 200
    assert response.json() == {"response": "Nexus received: Hello Nexus"}


def test_chat_rejects_oversized_message(monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", "x" * 40)
    response = client.post(
        "/v1/chat",
        headers={"Authorization": "Bearer " + "x" * 40},
        json={"message": "a" * 8001},
    )
    assert response.status_code == 422
