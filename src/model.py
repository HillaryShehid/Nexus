"""Model gateway for Personal Nexus.

Nexus owns identity, memory, planning, permissions, tools, verification, and
conversation state. Model providers are replaceable infrastructure.

Online free-first providers:
- Gemini Developer API
- Groq API
- OpenRouter free-model router

Offline:
- Ollama remains available as the local fallback so Personal Nexus can still
  operate without an internet connection.

OpenAI is intentionally no longer a Personal Nexus provider.
"""

import json
import logging
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger("nexus.model")

FREE_PROVIDER_ORDER = ("gemini", "groq", "openrouter")
ALLOWED_PROVIDERS = set(FREE_PROVIDER_ORDER) | {"ollama"}


class AIBrain:
    """Free-first, provider-independent model gateway for Nexus."""

    def __init__(self):
        self.mode = os.getenv("NEXUS_MODEL_MODE", "free").lower()
        configured = os.getenv(
            "NEXUS_PROVIDER_ORDER",
            "gemini,groq,openrouter,ollama",
        )
        self.provider_order = tuple(
            item.strip().lower()
            for item in configured.split(",")
            if item.strip()
        )

        invalid = set(self.provider_order) - ALLOWED_PROVIDERS
        if invalid:
            raise ValueError(
                "Unsupported Nexus providers: "
                + ", ".join(sorted(invalid))
            )

        if self.mode not in {"free", "offline", "manual"}:
            raise ValueError(
                "NEXUS_MODEL_MODE must be 'free', 'offline', or 'manual'."
            )

        if self.mode == "offline":
            self.provider_order = ("ollama",)
        elif self.mode == "free":
            self.provider_order = tuple(
                provider
                for provider in self.provider_order
                if provider in FREE_PROVIDER_ORDER or provider == "ollama"
            )

        if not self.provider_order:
            raise ValueError("No Nexus model providers are configured.")

        self.provider_models = {
            "gemini": os.getenv("NEXUS_GEMINI_MODEL", "gemini-3.8-flash"),
            "groq": os.getenv("NEXUS_GROQ_MODEL", "openai/gpt-oss-120b"),
            "openrouter": os.getenv(
                "NEXUS_OPENROUTER_MODEL",
                "openrouter/free",
            ),
            "ollama": os.getenv("NEXUS_LOCAL_MODEL", "llama3.2"),
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

        self.clients = {}
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            self.clients["groq"] = OpenAI(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
            )

        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            self.clients["openrouter"] = OpenAI(
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": os.getenv(
                        "OPENROUTER_HTTP_REFERER",
                        "https://github.com/HillaryShehid/Nexus",
                    ),
                    "X-Title": "Nexus Personal AI",
                },
            )

        ollama_url = os.getenv(
            "NEXUS_OLLAMA_URL",
            "http://localhost:11434/v1",
        )
        self.clients["ollama"] = OpenAI(
            base_url=ollama_url,
            api_key=os.getenv("NEXUS_OLLAMA_API_KEY", "ollama"),
        )

    def _available(self, provider: str) -> bool:
        if provider == "gemini":
            return bool(self.gemini_api_key)
        return provider in self.clients

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

    def _generate_gemini(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        max_tokens: int,
    ) -> str:
        """Call the Gemini Developer API without another SDK dependency."""
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + model
            + ":generateContent?key="
            + self.gemini_api_key
        )
        body = {
            "system_instruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [{
                "role": "user",
                "parts": [{"text": user_prompt}],
            }],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
            },
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(
                "utf-8",
                errors="replace",
            )[:1000]
            raise RuntimeError(
                f"Gemini API HTTP {exc.code}: {detail}"
            ) from exc

        candidates = payload.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini API returned no candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(
            str(part.get("text", ""))
            for part in parts
        )

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

    def _generate_with_provider(
        self,
        provider: str,
        profile: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
    ) -> tuple[str, str]:
        model = os.getenv(
            f"NEXUS_{profile.upper()}_MODEL",
            self.provider_models[provider],
        )
        max_tokens = self.max_tokens.get(profile, 512)

        if provider == "gemini":
            content = self._generate_gemini(
                model,
                system_prompt,
                user_prompt,
                json_mode,
                max_tokens,
            )
        else:
            content = self._generate_openai_compatible(
                provider,
                model,
                system_prompt,
                user_prompt,
                json_mode,
                max_tokens,
            )

        return content, model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        profile: str = "normal",
    ) -> dict:
        """Generate a response with automatic free-provider failover."""
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
