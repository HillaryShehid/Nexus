from src.voice_livekit import LiveKitVoiceConfig


def test_voice_config_defaults_to_omniroute(monkeypatch):
    for key in (
        "NEXUS_VOICE_STT",
        "NEXUS_VOICE_LLM",
        "NEXUS_VOICE_TTS",
        "NEXUS_LOCAL_MODEL",
        "NEXUS_OMNIROUTE_MODEL",
        "NEXUS_VOICE_LLM_MODEL",
        "OMNIROUTE_BASE_URL",
        "OMNIROUTE_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    config = LiveKitVoiceConfig()
    assert config.stt_provider == "deepgram"
    assert config.llm_provider == "omniroute"
    assert config.omniroute_model == "auto"
    assert config.omniroute_url == "http://127.0.0.1:20128/v1"
    assert config.omniroute_api_key == "sk_omniroute"
    assert config.tts_provider == "inference"


def test_voice_config_supports_explicit_ollama_fallback(monkeypatch):
    monkeypatch.setenv("NEXUS_VOICE_LLM", "ollama")
    monkeypatch.setenv("NEXUS_LOCAL_MODEL", "test-local-model")
    config = LiveKitVoiceConfig()
    assert config.llm_provider == "ollama"
    assert config.ollama_model == "test-local-model"
