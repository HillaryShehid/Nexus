"""Model gateway for Personal Nexus.

Nexus owns identity, memory, planning, permissions, tools, verification, and
conversation state. OmniRoute is the single model gateway and handles provider
selection and fallback behind one OpenAI-compatible endpoint.
"""

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger("nexus.model")

FREE_PROVIDER_ORDER = ("omniroute",)
ALLOWED_PROVIDERS = set(FREE_PROVIDER_ORDER)


class AIBrain:
    """Free-first, provider-independent model gateway for Nexus."""

    def __init__(self):
        self.mode = os.getenv("NEXUS_MODEL_MODE", "free").lower()
        # OmniRoute is the only Nexus gateway; it handles provider routing and fallback.
        self.provider_order = ("omniroute",)

        invalid = set(self.provider_order) - ALLOWED_PROVIDERS
        if invalid:
            raise ValueError(
                "Unsupported Nexus providers: "
                + ", ".join(sorted(invalid))
            )

        if self.mode not in {"free", "manual"}:
            raise ValueError(
                "NEXUS_MODEL_MODE must be 'free' or 'manual'. "
                "Nexus routes through OmniRoute in both modes."
            )

        if not self.provider_order:
            raise ValueError("No Nexus model providers are configured.")

        self.provider_models = {
            "omniroute": os.getenv("NEXUS_OMNIROUTE_MODEL", "auto"),
        }

        self.models = {
            profile: os.getenv(
                f"NEXUS_{profile.upper()}_MODEL",
                self.provider_models[self.provider_order[0]],
            )
            for profile in ("quick", "normal", "deep", "coding", "research")
        }

        self.max_tokens = {
            "quick": int(os.getenv("NEXUS_QUICK_MAX_TOKENS", "192")),
            "normal": int(os.getenv("NEXUS_NORMAL_MAX_TOKENS", "512")),
            "deep": int(os.getenv("NEXUS_DEEP_MAX_TOKENS", "1024")),
            "coding": int(os.getenv("NEXUS_CODING_MAX_TOKENS", "1024")),
            "research": int(os.getenv("NEXUS_RESEARCH_MAX_TOKENS", "1024")),
        }

        # OmniRoute is the sole model gateway. Its OpenAI-compatible API
        # handles provider selection, free-tier routing, and fallback.
        self.clients = {
            "omniroute": OpenAI(
                api_key=os.getenv("OMNIROUTE_API_KEY", "sk_omniroute"),
                base_url=os.getenv(
                    "OMNIROUTE_BASE_URL",
                    "http://127.0.0.1:20128/v1",
                ),
            )
        }

    def _available(self, provider: str) -> bool:
        return provider == "omniroute" and provider in self.clients

    def _provider_for_profile(self, profile: str) -> str:
        """Choose the first configured provider in the free-first order.

        Per-profile model overrides are still supported, but provider choice
        stays independent from the model name.
        """
        preferred = os.getenv(f"NEXUS_{profile.upper()}_PROVIDER")
        if preferred:
            preferred = preferred.lower()
            if preferred not in ALLOWED_PROVIDERS:
                raise ValueError(
                    f"Unsupported provider override: {preferred}"
                )
            if self._available(preferred):
                return preferred

        for provider in self.provider_order:
            if self._available(provider):
                return provider

        raise RuntimeError("No configured Nexus model provider is available.")

    def _generate_openai_compatible(
        self,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        max_tokens: int,
    ) -> str:
        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.clients[provider].chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return content if isinstance(content, str) else ""

    def _generate_openai_compatible_stream(
        self,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        max_tokens: int,
        on_chunk,
    ) -> str:
        """Stream text deltas from OpenAI-compatible cloud providers."""
        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "stream": True,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        pieces = []
        response = self.clients[provider].chat.completions.create(**kwargs)
        for chunk in response:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None)
            if isinstance(content, str) and content:
                pieces.append(content)
                on_chunk(content)
        return "".join(pieces)

    def _generate_with_provider(
        self,
        provider: str,
        profile: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        on_chunk=None,
    ) -> tuple[str, str]:
        model = os.getenv(
            f"NEXUS_{profile.upper()}_MODEL",
            self.provider_models[provider],
        )
        max_tokens = self.max_tokens.get(profile, 512)

        if on_chunk is not None:
            if provider != "omniroute":
                raise RuntimeError(f"Unsupported model gateway: {provider}")
            content = self._generate_openai_compatible_stream(
                provider, model, system_prompt, user_prompt, json_mode,
                max_tokens, on_chunk
            )
        elif provider == "omniroute":
            content = self._generate_openai_compatible(
                provider, model, system_prompt, user_prompt, json_mode, max_tokens
            )
        else:
            raise RuntimeError(f"Unsupported model gateway: {provider}")

        return content, model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        profile: str = "normal",
        on_chunk=None,
    ) -> dict:
        """Generate a response with automatic free-provider failover.

        When on_chunk is supplied, text is streamed from the selected provider.
        If a provider fails after emitting partial text, Nexus reports failure
        rather than silently mixing a fallback response into the partial output.
        """
        if not isinstance(system_prompt, str) or not isinstance(
            user_prompt, str
        ):
            return {
                "success": False,
                "content": "",
                "error": "Model input must be text.",
            }

        if profile not in self.max_tokens:
            profile = "normal"

        errors = []
        providers = list(self.provider_order)
        streamed_any = False

        def emit_chunk(chunk):
            nonlocal streamed_any
            streamed_any = True
            on_chunk(chunk)

        for provider in providers:
            if not self._available(provider):
                continue

            try:
                content, model = self._generate_with_provider(
                    provider,
                    profile,
                    system_prompt,
                    user_prompt,
                    json_mode,
                    on_chunk=emit_chunk if on_chunk is not None else None,
                )

                if not content.strip():
                    raise RuntimeError("Provider returned empty output.")

                return {
                    "success": True,
                    "content": content,
                    "error": None,
                    "model": model,
                    "profile": profile,
                    "provider": provider,
                    "fallback_used": bool(errors),
                    "attempted_providers": [
                        item["provider"] for item in errors
                    ] + [provider],
                }
            except Exception as exc:
                logger.warning(
                    "Nexus provider %s failed; trying the next provider.",
                    provider,
                )
                errors.append({
                    "provider": provider,
                    "error": type(exc).__name__,
                })
                # Once text has reached the UI, do not append a second
                # provider's full answer to the partial first answer.
                if streamed_any:
                    return {
                        "success": False,
                        "content": "",
                        "error": "The response stream was interrupted.",
                        "provider_errors": errors,
                        "profile": profile,
                    }

        return {
            "success": False,
            "content": "",
            "error": (
                "No configured Nexus model provider could complete "
                "the request safely."
            ),
            "provider_errors": errors,
            "profile": profile,
        }
