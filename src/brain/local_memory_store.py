"""Small local MemoryStore adapter backed by Nexus's existing memory tool."""
from src.storage import MemoryStore


class LocalMemoryStore(MemoryStore):
    def __init__(self, tools):
        self.tools = tools

    def get(self, key):
        result = self.tools.execute("memory_store", {"action": "read", "key": str(key)[:80]})
        return result.get("result", "")

    def save(self, key, value):
        result = self.tools.execute(
            "memory_store",
            {"action": "save", "key": str(key)[:80], "value": str(value)[:1500]},
        )
        return result.get("success") is True

    def append_conversation(self, value):
        result = self.tools.execute(
            "memory_store",
            {"action": "append_conversation", "key": "chat_context", "value": __import__("json").dumps(value, ensure_ascii=False)[:24000]},
        )
        return result.get("success") is True

    def search(self, query):
        # The current local store has key lookup rather than full text search.
        # Keep the interface stable while durable/searchable storage is added.
        return [self.get(query)]

    def delete(self, key):
        # Deletion is intentionally unsupported by the legacy memory tool.
        return False
