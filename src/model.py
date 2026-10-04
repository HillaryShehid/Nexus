"""Model gateway for the Personal Nexus brain.

Nexus owns memory, planning, permissions, tools, and verification. The model
provider is swappable: OpenAI cloud or a local OpenAI-compatible server such as
Ollama. Local mode keeps normal Nexus inference off the paid OpenAI API.
"""

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger("nexus.model")


class AIBrain:
    """Route Nexus reasoning profiles through the configured model provider."""

    def __init__(self):
        self.provider = os.getenv("NEXUS_MODEL_PROVIDER", "ollama").lower()
        if self.provider not in {"openai", "ollama"}:
            raise ValueError("NEXUS_MODEL_PROVIDER must be 'openai' or 'ollama'.")

        default_model = (
            os.getenv("NEXUS_LOCAL_MODEL", "llama3.2")
            if self.provider == "ollama"
            else os.getenv("NEXUS_MODEL", "gpt-6-luna")
        )
        self.default_model = default_model
        if not self.default_model:
            raise ValueError("Nexus model name is missing.")

        if self.provider == "ollama":
            self.client = OpenAI(
                base_url=os.getenv("NEXUS_OLLAMA_URL", "http://localhost:11434/v1"),
                api_key=os.getenv("NEXUS_OLLAMA_API_KEY", "ollama"),
            )
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
                    os.getenv("NEXUS_QUICK_MODEL", "qwen2.5:1.5b")
                    if profile == "quick" and self.provider == "ollama"
                    else self.default_model
                ),
            )
            for profile in ("quick", "normal", "deep", "coding", "research")
        }

        # Keep local conversational replies deliberately short so a slow
        # CPU-only machine does not spend minutes generating unnecessary text.
        self.max_tokens = {
            "quick": int(os.getenv("NEXUS_QUICK_MAX_TOKENS", "192")),
            "normal": int(os.getenv("NEXUS_NORMAL_MAX_TOKENS", "512")),
            "deep": int(os.getenv("NEXUS_DEEP_MAX_TOKENS", "1024")),
            "coding": int(os.getenv("NEXUS_CODING_MAX_TOKENS", "1024")),
            "research": int(os.getenv("NEXUS_RESEARCH_MAX_TOKENS", "1024")),
        }

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        profile: str = "normal",
    ) -> dict:
        """Generate one bounded model response.

        Nexus orchestration remains outside the provider. Deterministic systems
        stay authoritative for tool availability, permissions, execution, and
        verification.
        """
        if not isinstance(system_prompt, str) or not isinstance(user_prompt, str):
            return {
                "success": False,
                "content": "",
                "error": "Model input must be text.",
            }

        selected = self.models.get(profile, self.default_model)

        try:
            if self.provider == "ollama":
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                kwargs = {
                    "model": selected,
                    "messages": messages,
                    "max_tokens": self.max_tokens.get(profile, 512),
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
            else:
                request = {
                    "model": selected,
                    "instructions": system_prompt,
                    "input": user_prompt,
                }
                if json_mode:
                    request["instructions"] = (
                        system_prompt
                        + "\nReturn the requested result as valid JSON."
                    )
                    request["text"] = {
                        "format": {"type": "json_object"}
                    }

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
                "error": (
                    "Internal Error: Model inference could not be completed safely."
                ),
                "model": selected,
                "profile": profile,
                "provider": self.provider,
            }
