"""Model gateway for the Personal Nexus brain.

Nexus owns memory, planning, permissions, tools, and verification. The model
provider is swappable. Free-first options include local Ollama and the Gemini
Developer API free tier; OpenAI-compatible endpoints can also be configured.
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


class AIBrain:
    """Route Nexus reasoning profiles through the configured model provider."""

    def __init__(self):
        self.provider = os.getenv("NEXUS_MODEL_PROVIDER", "ollama").lower()
        allowed = {"openai", "ollama", "gemini", "compatible"}
        if self.provider not in allowed:
            raise ValueError(
                "NEXUS_MODEL_PROVIDER must be 'ollama', 'gemini', "
                "'compatible', or 'openai'."
            )

        if self.provider == "ollama":
            self.default_model = os.getenv("NEXUS_LOCAL_MODEL", "llama3.2")
        elif self.provider == "gemini":
            self.default_model = os.getenv(
                "NEXUS_GEMINI_MODEL", "gemini-3.8-flash"
            )
        else:
            self.default_model = os.getenv("NEXUS_MODEL", "gpt-6-luna")

        if not self.default_model:
            raise ValueError("Nexus model name is missing.")

        self.client = None
        if self.provider == "ollama":
            self.client = OpenAI(
                base_url=os.getenv("NEXUS_OLLAMA_URL", "http://localhost:11434/v1"),
                api_key=os.getenv("NEXUS_OLLAMA_API_KEY", "ollama"),
            )
        elif self.provider == "compatible":
            api_key = os.getenv("NEXUS_API_KEY")
            base_url = os.getenv("NEXUS_API_BASE_URL")
            if not api_key or not base_url:
                raise ValueError(
                    "NEXUS_API_KEY and NEXUS_API_BASE_URL are required "
                    "for compatible providers."
                )
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        elif self.provider == "gemini":
            self.gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is required for Gemini.")
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "CRITICAL INITIALIZATION ERROR: 'OPENAI_API_KEY' is missing."
                )
            self.client = OpenAI(api_key=api_key)

        self.models = {
            profile: os.getenv(
                f"NEXUS_{profile.upper()}_MODEL",
                (
                    os.getenv(
                        "NEXUS_QUICK_MODEL",
                        "qwen2.5:1.5b" if self.provider == "ollama"
                        else self.default_model,
                    )
                    if profile == "quick"
                    else self.default_model
                ),
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

    def _generate_gemini(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        max_tokens: int,
    ) -> str:
        """Call Gemini directly without adding another SDK dependency."""
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + model
            + ":generateContent?key="
            + self.gemini_api_key
        )
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
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
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(
                f"Gemini API HTTP {exc.code}: {detail}"
            ) from exc

        candidates = payload.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini API returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(str(part.get("text", "")) for part in parts)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        profile: str = "normal",
    ) -> dict:
        """Generate one bounded model response."""
        if not isinstance(system_prompt, str) or not isinstance(user_prompt, str):
            return {
                "success": False,
                "content": "",
                "error": "Model input must be text.",
            }

        selected = self.models.get(profile, self.default_model)

        try:
            if self.provider in {"ollama", "compatible"}:
                kwargs = {
                    "model": selected,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": self.max_tokens.get(profile, 512),
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
            elif self.provider == "gemini":
                content = self._generate_gemini(
                    selected,
                    system_prompt,
                    user_prompt,
                    json_mode,
                    self.max_tokens.get(profile, 512),
                )
            else:
                request = {
                    "model": selected,
                    "instructions": system_prompt,
                    "input": user_prompt,
                }
                if json_mode:
                    request["instructions"] = (
                        system_prompt + "\nReturn the requested result as valid JSON."
                    )
                    request["text"] = {"format": {"type": "json_object"}}
                response = self.client.responses.create(**request)
                content = getattr(response, "output_text", None)

            if not isinstance(content, str) or not content.strip():
                return {
                    "success": False,
                    "content": "",
                    "error": "Model Provider Error: Empty output.",
                }

            return {
                "success": True,
                "content": content,
                "error": None,
                "model": selected,
                "profile": profile,
                "provider": self.provider,
            }

        except Exception:
            logger.exception(
                "Model provider communication failure for profile %s.",
                profile,
            )
            return {
                "success": False,
                "content": "",
                "error": "Internal Error: Model inference could not be completed safely.",
                "model": selected,
                "profile": profile,
                "provider": self.provider,
            }
