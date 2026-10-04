from src.voice_livekit import LiveKitVoiceConfig


def test_voice_config_defaults(monkeypatch):
    for key in (
        "NEXUS_VOICE_STT",
        "NEXUS_VOICE_LLM",
        "NEXUS_VOICE_TTS",
        "NEXUS_LOCAL_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)

    config = LiveKitVoiceConfig()
    assert config.stt_provider == "deepgram"
    assert config.llm_provider == "ollama"
    assert config.tts_provider == "kokoro"
    assert config.ollama_model == "llama3.2"
