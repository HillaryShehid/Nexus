import json
from datetime import datetime, timezone

from src.brain.local_memory_store import LocalMemoryStore


class CognitiveMemory:
    """Memory facade with a replaceable storage adapter."""
    def __init__(self, tools, store=None):
        self.tools = tools
        self.store = store or LocalMemoryStore(tools)

    def read_context(self):
        raw = self.store.get("chat_context")
        try:
            history = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return "No persisted conversation context is loaded."
        if not isinstance(history, list) or not history:
            return "No persisted conversation context is loaded."
        # Keep the model prompt bounded while retaining the full conversation log.
        recent = history[-20:]
        lines = []
        for item in recent:
            if isinstance(item, dict):
                user = str(item.get("user", ""))[:4000]
                assistant = str(item.get("assistant", ""))[:6000]
                lines.append(f"User: {user}\nNexus: {assistant}")
        return "\n\n".join(lines) if lines else "No persisted conversation context is loaded."

    def save_conversation(self, user_message, assistant_message):
        payload = {
            "user": str(user_message)[:8000],
            "assistant": str(assistant_message)[:12000],
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
