"""Small local MemoryStore adapter backed by Nexus's existing memory tool."""
import json

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
        # Bound individual fields, not the serialized JSON string: slicing
        # encoded JSON can cut an escape sequence and silently corrupt memory.
        entry = value
        if isinstance(value, dict):
            entry = dict(value)
            if "user" in entry:
                entry["user"] = str(entry["user"])[:8000]
            if "assistant" in entry:
                entry["assistant"] = str(entry["assistant"])[:12000]
        serialized = json.dumps(entry, ensure_ascii=False)
        result = self.tools.execute(
            "memory_store",
            {"action": "append_conversation", "key": "chat_context", "value": serialized},
        )
        return result.get("success") is True

    def search(self, query):
        # The current local store has key lookup rather than full text search.
        # Keep the interface stable while durable/searchable storage is added.
        return [self.get(query)]

    def delete(self, key):
        # Deletion is intentionally unsupported by the legacy memory tool.
        return False
