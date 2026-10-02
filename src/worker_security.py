"""Small, dependency-free security helpers for the Cloudflare API worker."""

from __future__ import annotations

import hmac
from urllib.parse import urlsplit


MIN_API_TOKEN_LENGTH = 32
MAX_API_TOKEN_LENGTH = 512


def api_token_is_configured(value: object) -> bool:
    """Require a sufficiently long server-side secret; fail closed otherwise."""
    return (
        isinstance(value, str)
        and MIN_API_TOKEN_LENGTH <= len(value) <= MAX_API_TOKEN_LENGTH
        and all(
            character.isascii() and (character.isalnum() or character in "-._~")
            for character in value
        )
    )


def is_authorized_bearer(authorization: object, expected_token: object) -> bool:
    """Check an Authorization header without a timing-sensitive string compare."""
    if not api_token_is_configured(expected_token) or not isinstance(authorization, str):
        return False
    scheme, separator, supplied_token = authorization.partition(" ")
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not supplied_token
        or any(character.isspace() for character in supplied_token)
    ):
        return False
    return hmac.compare_digest(supplied_token.encode("utf-8"), expected_token.encode("utf-8"))


def _normalize_origin(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 512:
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or "*" in parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != ""
            or parsed.query
            or parsed.fragment
        ):
            return None
        port = parsed.port
    except ValueError:
        return None

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    host = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and port != (443 if scheme == "https" else 80):
        host = f"{host}:{port}"
    return f"{scheme}://{host}"


def parse_allowed_origins(value: object) -> frozenset[str]:
    """Parse a comma-separated origin allowlist, ignoring invalid entries."""
    if not isinstance(value, str):
        return frozenset()
    return frozenset(
        normalized
        for item in value.split(",")
        if (normalized := _normalize_origin(item.strip())) is not None
    )


def cors_headers(origin: object, configured_origins: object) -> dict[str, str]:
    """Return CORS headers only when the request origin exactly matches config."""
    normalized = _normalize_origin(origin)
    if normalized is None or normalized not in parse_allowed_origins(configured_origins):
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Vary": "Origin",
    }
