""""Small, token-protected HTTP API for hosted Nexus.

This is a single-owner deployment bridge, not the final multi-user NexusCore
platform. Do not expose model/provider credentials to a browser.
"""
from __future__ import annotations

import hmac
import os
from functools import lru_cache
from threading import Lock

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from src.core import NexusCore

MAX_CHAT_REQUEST_BYTES = 64 * 1024
_core_request_lock = Lock()

app = FastAPI(
    title="Nexus API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class ChatRequestBodyLimitMiddleware:
    """Bound chat request bodies before FastAPI parses JSON or authenticates."""

    def __init__(self, app, max_bytes: int = MAX_CHAT_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/v1/chat":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > self.max_bytes:
                    await JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large."},
                    )(scope, receive, send)
                    return
            except ValueError:
                await JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                )(scope, receive, send)
                return

        # Also count streamed/chunked requests that omit Content-Length.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)


app.add_middleware(ChatRequestBodyLimitMiddleware)

# Browser origins are opt-in. Set a comma-separated list when the frontend exists.
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("NEXUS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class ChatResponse(BaseModel):
    response: str


@lru_cache(maxsize=1)
def _get_core() -> NexusCore:
    # Single-owner bootstrap only. Multi-user identity and memory isolation
    # must be implemented before inviting partners.
    return NexusCore(actor_id="hilal")


def _require_api_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("NEXUS_API_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nexus API authentication is not configured.",
        )
    scheme, _, supplied = (authorization or "").partition(" ")
    if (
        scheme.lower() != "bearer"
        or not supplied
        or not hmac.compare_digest(supplied, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/health")
def health() -> dict[str, str]:
    """Non-sensitive deployment health endpoint."""
    return {"status": "ok", "service": "nexus-api"}


@app.post(
    "/v1/chat",
    response_model=ChatResponse,
    dependencies=[Depends(_require_api_token)],
)
def chat(payload: ChatRequest) -> ChatResponse:
    """Send one text message to the canonical Nexus brain."""
    if not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be blank.",
        )
    # NexusCore and its learning/state stores are shared and not concurrency-safe.
    with _core_request_lock:
        response = _get_core().handle_request(payload.message)
    return ChatResponse(response=response)
"