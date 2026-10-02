from src.worker_security import (
    api_token_is_configured,
    cors_headers,
    is_authorized_bearer,
)


def test_bearer_token_requires_strong_configured_secret():
    assert not api_token_is_configured("short")
    assert api_token_is_configured("a" * 32)
    assert is_authorized_bearer("Bearer " + "a" * 32, "a" * 32)
    assert not is_authorized_bearer("Bearer " + "b" * 32, "a" * 32)


def test_cors_only_allows_explicit_origins():
    headers = cors_headers("https://nexus.example", "https://nexus.example")
    assert headers["Access-Control-Allow-Origin"] == "https://nexus.example"
    assert cors_headers("https://evil.example", "https://nexus.example") == {}
