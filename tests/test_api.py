import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep

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


def test_chat_rejects_oversized_body_before_json_parsing(monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", "x" * 40)
    response = client.post(
        "/v1/chat",
        headers={"Authorization": "Bearer " + "x" * 40},
        content=b'{"message":"' + b"a" * api.MAX_CHAT_REQUEST_BYTES + b'"}',
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large."}


def test_body_limit_rejects_chunked_stream_without_content_length():
    messages = iter(
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"56", "more_body": False},
        ]
    )
    sent = []
    app_called = False

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    async def fake_app(scope, receive, send):
        nonlocal app_called
        app_called = True

    middleware = api.ChatRequestBodyLimitMiddleware(fake_app, max_bytes=5)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "POST",
        "path": "/v1/chat",
        "headers": [],
    }

    asyncio.run(middleware(scope, receive, send))

    assert not app_called
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413


def test_chat_serializes_access_to_shared_nexus_core(monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", "test-token-" + "x" * 40)
    state_lock = Lock()
    active = 0
    max_active = 0

    class FakeCore:
        def handle_request(self, message):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
            sleep(0.03)
            with state_lock:
                active -= 1
            return f"received: {message}"

    monkeypatch.setattr(api, "_get_core", lambda: FakeCore())
    headers = {"Authorization": "Bearer " + os.environ["NEXUS_API_TOKEN"]}

    def send_message(index):
        response = client.post(
            "/v1/chat", headers=headers, json={"message": f"message {index}"}
        )
        assert response.status_code == 200
        return response.json()["response"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(send_message, range(4)))

    assert results == [f"received: message {i}" for i in range(4)]
    assert max_active == 1
