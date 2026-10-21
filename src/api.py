"""Small, token-protected HTTP API for hosted Nexus.

This is a single-owner deployment bridge, not the final multi-user NexusCore
platform. Do not expose model/provider credentials to a browser.
"""
from __future__ import annotations

import hmac
import os
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core import NexusCore

app = FastAPI(
    title="Nexus API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

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
    return ChatResponse(response=_get_core().handle_request(payload.message))
