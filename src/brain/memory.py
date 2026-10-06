import json
from datetime import datetime, timezone


class _EphemeralMemoryStore:
    def get(self, key):
        return ""

    def save(self, key, value):
        return False

    def append_conversation(self, value):
        return False


class CognitiveMemory:
    """Memory facade with an explicitly injected storage adapter."""
    def __init__(self, tools=None, store=None):
        self.tools = tools
        self.store = store if store is not None else _EphemeralMemoryStore()

    def read_context(self):
        raw = self.store.get("chat_context")
        try:
            history = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return "No persisted conversation context is loaded."
        if not isinstance(history, list) or not history:
            return "No persisted conversation context is loaded."

        normalized = []
        for item in history:
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except (TypeError, json.JSONDecodeError):
                    continue
            if isinstance(item, dict):
                normalized.append(item)

        recent = normalized[-20:]
        lines = []
        for item in recent:
            user = str(item.get("user", ""))[:8000]
            assistant = str(item.get("assistant", ""))[:12000]
            lines.append(f"User: {user}\nNexus: {assistant}")
        return "\n\n".join(lines) if lines else "No persisted conversation context is loaded."

    def save_conversation(self, user_message, assistant_message):
        payload = {
            "user": str(user_message),
            "assistant": str(assistant_message),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        append = getattr(self.store, "append_conversation", None)
        if callable(append):
            return append(payload)
        raw = self.store.get("chat_context")
        try:
            history = json.loads(raw) if raw else []
        except (TypeError, json.JSONDecodeError):
            history = []
        if not isinstance(history, list):
            history = []
        history.append(payload)
        return self.store.save("chat_context", json.dumps(history, ensure_ascii=False))

    def read_fact(self, key):
        return str(self.store.get(key[:80]))[:1500]

    def save_fact(self, key, value):
        return self.store.save(key[:80], value[:1500])

    def remember(self, category, value):
        payload = json.dumps(
            {"value": str(value)[:1200], "updated_at": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False,
        )
        return self.save_fact(f"nexus_{category}", payload)

    def recall(self, category):
        return self.read_fact(f"nexus_{category}")
