from io import BytesIO

import pytest

from src.speech import NexusSpeech, SpeechConfig


class FakeResponse:
    def read(self):
        return b"audio"


class FakeSpeech:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeAudio:
    def __init__(self):
        self.speech = FakeSpeech()


class FakeClient:
    def __init__(self):
        self.audio = FakeAudio()


def test_speech_uses_openai_tts_and_nexus_voice_instructions():
    client = FakeClient()
    speech = NexusSpeech(
        client=client,
        config=SpeechConfig(max_chars=900),
    )

    assert speech.synthesize("Hello Nexus") == b"audio"
    call = client.audio.speech.calls[0]
    assert call["model"] == "gpt-4o-mini-tts"
    assert call["voice"] == "onyx"
    assert "British accent" in call["instructions"]


def test_speech_rejects_oversized_chunk():
    speech = NexusSpeech(
        client=FakeClient(),
        config=SpeechConfig(max_chars=5),
    )

    with pytest.raises(ValueError):
        speech.synthesize("123456")


def test_speech_empty_text_returns_no_audio():
    speech = NexusSpeech(client=FakeClient())
    assert speech.synthesize("   ") == b""
