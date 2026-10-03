"""Hardware-agnostic voice contracts for Personal Nexus."""
from dataclasses import dataclass
from src.personal_runtime import VoiceMode, VoiceSession

@dataclass
class VoiceEvent:
    kind: str
    text: str = ""

class VoiceController:
    MAX_SPEECH_CHARS = 900

    def __init__(self, session: VoiceSession | None = None):
        self.session = session or VoiceSession()

    def process_wake_word(self, transcript: str) -> bool:
        if self.session.mode == VoiceMode.SILENT:
            return False
        if self.session.wake_word.casefold() in str(transcript).casefold():
            self.session.activate()
            return True
        return False

    def begin_listening(self) -> VoiceEvent:
        self.session.activate()
        return VoiceEvent("listening")

    def end_listening(self) -> VoiceEvent:
        self.session.listening = False
        return VoiceEvent("listening_stopped")

    def set_mode(self, mode: VoiceMode | str) -> VoiceEvent:
        self.session.set_mode(mode)
        return VoiceEvent("mode_changed", self.session.mode.value)

    @classmethod
    def chunk_response(cls, text: str) -> list[str]:
        """Split long speech into lossless, natural chunks for TTS."""
        text = str(text or "")
        if not text:
            return []
        chunks, current = [], ""
        for paragraph in text.split("\\n"):
            for word in paragraph.split():
                candidate = word if not current else current + " " + word
                if len(candidate) <= cls.MAX_SPEECH_CHARS:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = word
            if current:
                chunks.append(current)
                current = ""
        return chunks

    def route_response(self, text: str) -> VoiceEvent:
        if not self.session.should_output_audio():
            return VoiceEvent("visual_only", text)
        target = "airpods" if self.session.mode == VoiceMode.PRIVATE else "speaker"
        return VoiceEvent(target, text)
