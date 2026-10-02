from src.worker_security import (
    api_token_is_configured,
    cors_headers,
    is_authorized_bearer,
    parse_allowed_origins,
)


def test_worker_api_token_must_be_configured_and_long_enough():
    assert api_token_is_configured("a" * 32)
    assert not api_token_is_configured("")
    assert not api_token_is_configured("short")
    assert not api_token_is_configured("a" * 31 + "\n")
    assert not api_token_is_configured("a" * 31 + "é")
    assert not api_token_is_configured(None)


def test_worker_requires_exact_bearer_token():
    token = "a" * 48

    assert is_authorized_bearer(f"Bearer {token}", token)
    assert is_authorized_bearer(f"bearer {token}", token)
    assert not is_authorized_bearer(f"Basic {token}", token)
    assert not is_authorized_bearer(f"Bearer {token}x", token)
    assert not is_authorized_bearer(f"Bearer  {token}", token)
    assert not is_authorized_bearer(f"Bearer {token}", "")


def test_worker_cors_echoes_only_an_explicit_normalized_origin():
    allowed = "https://app.example.com, http://localhost:3000"

    headers = cors_headers("https://APP.example.com", allowed)

    assert headers["Access-Control-Allow-Origin"] == "https://APP.example.com"
    assert headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
    assert headers["Access-Control-Allow-Headers"] == "Authorization, Content-Type"
    assert headers["Vary"] == "Origin"
    assert "Access-Control-Allow-Credentials" not in headers


def test_worker_cors_rejects_unlisted_or_malformed_origins():
    allowed = "https://app.example.com"

    assert cors_headers("https://app.example.com.evil.test", allowed) == {}
    assert cors_headers("https://evil.test", allowed) == {}
    assert cors_headers("null", allowed) == {}
    assert cors_headers("https://app.example.com/path", allowed) == {}
    assert cors_headers("https://app.example.com/", allowed) == {}
    assert cors_headers(None, allowed) == {}


def test_worker_allowlist_ignores_invalid_entries_and_wildcards():
    assert parse_allowed_origins(
        "*, https://good.example/path, https://good.example, ftp://bad.example"
    ) == frozenset({"https://good.example"})
