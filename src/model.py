"""OpenAI model gateway for the Personal Nexus brain.

Nexus owns memory, planning, permissions, tools, and verification. OpenAI
provides the reasoning/inference layer through the Responses API.
"""

import json
import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger("nexus.model")


class AIBrain:
    """Route Nexus reasoning profiles to OpenAI's current Responses API."""

    def __init__(self):
        self.default_model = os.getenv("NEXUS_MODEL", "gpt-6-luna")
        if not self.default_model:
            raise ValueError(
                "CRITICAL INITIALIZATION ERROR: 'NEXUS_MODEL' is missing."
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "CRITICAL INITIALIZATION ERROR: 'OPENAI_API_KEY' is missing."
            )

        self.client = OpenAI(api_key=api_key)
        self.models = {
            profile: os.getenv(
                f"NEXUS_{profile.upper()}_MODEL",
                self.default_model,
            )
            for profile in ("quick", "normal", "deep", "coding", "research")
        }

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        profile: str = "normal",
    ) -> dict:
        """Generate one bounded model response.

        The application deliberately keeps orchestration outside the provider:
        Nexus decides what tools/actions are allowed and verifies their results.
        """

        if not isinstance(system_prompt, str) or not isinstance(user_prompt, str):
            return {
                "success": False,
                "content": "",
                "error": "Model input must be text.",
            }

        selected = self.models.get(profile, self.default_model)

        try:
            request = {
                "model": selected,
                "instructions": system_prompt,
                "input": user_prompt,
            }

            if json_mode:
                # Responses API structured JSON mode. The planner still validates
                # the returned schema independently, so model output is never
                # treated as authoritative.
                request["instructions"] = system_prompt + "\nReturn the requested result as valid JSON.";

                request["text"] = {
                    "format": {
                        "type": "json_object",
                    }
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
            }

        except Exception:
            logger.exception(
                "OpenAI Responses API communication failure for profile %s.",
                profile,
            )
            return {
                "success": False,
                "content": "",
                "error": (
                    "Internal Error: OpenAI inference could not be completed "
                    "safely."
                ),
                "model": selected,
                "profile": profile,
            }
