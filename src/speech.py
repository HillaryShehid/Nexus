"""OpenAI speech output for Personal Nexus."""

import io
import os
from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class SpeechConfig:
    model: str = "gpt-4o-mini-tts"
    voice: str = "onyx"
    response_format: str = "mp3"
    speed: float = 0.98
    max_chars: int = 900

    @classmethod
    def from_env(cls) -> "SpeechConfig":
        return cls(
            model=os.getenv("NEXUS_TTS_MODEL", "gpt-4o-mini-tts"),
            voice=os.getenv("NEXUS_TTS_VOICE", "onyx"),
            response_format=os.getenv("NEXUS_TTS_FORMAT", "mp3"),
            speed=float(os.getenv("NEXUS_TTS_SPEED", "0.98")),
            max_chars=int(os.getenv("NEXUS_TTS_MAX_CHARS", "900")),
        )


class NexusSpeech:
    """Small provider adapter so the Nexus brain remains independent of TTS."""

    def __init__(self, client: OpenAI | None = None, config: SpeechConfig | None = None):
        self.client = client or OpenAI()
        self.config = config or SpeechConfig.from_env()

    def synthesize(self, text: str) -> bytes:
        text = str(text or "").strip()
        if not text:
            return b""
        if len(text) > self.config.max_chars:
            raise ValueError(f"Speech input exceeds {self.config.max_chars} characters.")

        response = self.client.audio.speech.create(
            model=self.config.model,
            voice=self.config.voice,
            input=text,
            instructions=(
                "Speak as Nexus: warm, natural, confident, slightly low male voice "
                "with a subtle British accent. Sound conversational and present, "
                "not robotic. Keep the user's requested humour and personality. "
                "Use natural pauses and emphasis."
            ),
            response_format=self.config.response_format,
            speed=self.config.speed,
        )
        return response.read()

    def synthesize_to_buffer(self, text: str) -> io.BytesIO:
        return io.BytesIO(self.synthesize(text))
