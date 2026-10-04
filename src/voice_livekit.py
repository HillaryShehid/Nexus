"""LiveKit voice-agent adapter for Personal Nexus.

The voice transport and provider pipeline are intentionally separate from
NexusBrain. LiveKit handles realtime media and turn-taking; NexusCore remains
the authoritative personal assistant brain.

Default design:
- LiveKit Agents for realtime WebRTC/audio.
- Silero VAD locally.
- Ollama locally for the voice router.
- Kokoro locally for speech output when configured.
- Deepgram is supported as an optional STT provider.

The provider choices are environment-configurable so Nexus can move between
local and cloud components without changing its identity, memory, or tools.
"""

from __future__ import annotations

import os
from typing import Any


class LiveKitVoiceConfig:
    """Environment-backed voice provider configuration."""

    def __init__(self) -> None:
        self.stt_provider = os.getenv("NEXUS_VOICE_STT", "deepgram").lower()
        self.llm_provider = os.getenv("NEXUS_VOICE_LLM", "ollama").lower()
        self.tts_provider = os.getenv("NEXUS_VOICE_TTS", "kokoro").lower()
        self.ollama_model = os.getenv("NEXUS_LOCAL_MODEL", "llama3.2")
        self.ollama_url = os.getenv("NEXUS_OLLAMA_URL", "http://localhost:11434/v1")
        self.kokoro_url = os.getenv("NEXUS_KOKORO_URL", "http://localhost:8880/v1")
        self.kokoro_voice = os.getenv("NEXUS_KOKORO_VOICE", "af_alloy")
        self.deepgram_model = os.getenv("NEXUS_DEEPGRAM_STT_MODEL", "nova-3")
        self.elevenlabs_model = os.getenv("NEXUS_ELEVENLABS_TTS_MODEL", "eleven_turbo_v2_5")
        self.elevenlabs_voice = os.getenv("NEXUS_ELEVENLABS_TTS_VOICE", "")
        self.language = os.getenv("NEXUS_VOICE_LANGUAGE", "en")

    def describe(self) -> dict[str, Any]:
        return {
            "stt": self.stt_provider,
            "llm": self.llm_provider,
            "tts": self.tts_provider,
            "local_llm_model": self.ollama_model,
            "local_tts_voice": self.kokoro_voice,
            "language": self.language,
        }


def build_livekit_models(config: LiveKitVoiceConfig):
    """Create LiveKit AgentSession model components.

    Imports are intentionally lazy so the normal text-only Nexus install does
    not require LiveKit or its optional plugins.
    """
    from livekit.agents import inference
    from livekit.plugins import openai, silero

    vad = silero.VAD.load()

    if config.stt_provider == "deepgram":
        from livekit.plugins import deepgram

        stt = deepgram.STT(model=config.deepgram_model, language=config.language)
    elif config.stt_provider == "inference":
        stt = inference.STT(model="deepgram/flux-general", language=config.language)
    else:
        raise RuntimeError(
            "Unsupported NEXUS_VOICE_STT. Use 'deepgram' or 'inference'. "
            "A local Whisper adapter is intentionally kept as a separate provider."
        )

    if config.llm_provider == "ollama":
        llm = openai.LLM.with_ollama(
            model=config.ollama_model,
            base_url=config.ollama_url,
        )
    elif config.llm_provider == "inference":
        llm = inference.LLM(model="google/gemma-4-31b-it")
    else:
        raise RuntimeError("Unsupported NEXUS_VOICE_LLM. Use 'ollama' or 'inference'.")

    if config.tts_provider == "kokoro":
        tts = openai.TTS(
            model="kokoro",
            voice=config.kokoro_voice,
            api_key="not-needed",
            base_url=config.kokoro_url,
            response_format="wav",
        )
    elif config.tts_provider == "elevenlabs":
        from livekit.plugins import elevenlabs

        tts = elevenlabs.TTS(
            model=config.elevenlabs_model,
            voice_id=config.elevenlabs_voice or None,
        )
    elif config.tts_provider == "inference":
        tts = inference.TTS(
            model="fishaudio/s2.1-pro",
            voice="fa4c9eb3dccc4806b382b40d61c6b10a",
            language=config.language,
        )
    else:
        raise RuntimeError(
            "Unsupported NEXUS_VOICE_TTS. Use 'kokoro', 'elevenlabs', or 'inference'."
        )

    return vad, stt, llm, tts
