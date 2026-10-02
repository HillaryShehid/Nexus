import json
from datetime import datetime, timezone

from src.brain.local_memory_store import LocalMemoryStore


class CognitiveMemory:
    """Memory facade with a replaceable storage adapter."""
    def __init__(self, tools, store=None):
        self.tools = tools
        self.store = store or LocalMemoryStore(tools)

    def read_context(self):
        return "No persisted conversation context is loaded."

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
