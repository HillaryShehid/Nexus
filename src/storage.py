"""Storage interfaces used by Nexus brain subsystems.

The default implementations remain local and development-friendly. The
interfaces allow D1/SQLite/Postgres/other durable stores to be added later
without changing the brain's public behavior.
"""
import json
from abc import ABC, abstractmethod


class MemoryStore(ABC):
    @abstractmethod
    def get(self, key):
        raise NotImplementedError

    @abstractmethod
    def save(self, key, value):
        raise NotImplementedError

    def append_conversation(self, value):
        """Append one serialized conversation entry using the generic store API."""
        raw = self.get("chat_context")
        try:
            history = json.loads(raw) if raw else []
        except (TypeError, json.JSONDecodeError):
            history = []
        if not isinstance(history, list):
            history = []
        history.append(value)
        return self.save("chat_context", json.dumps(history, ensure_ascii=False))

    @abstractmethod
    def search(self, query):
        raise NotImplementedError

    @abstractmethod
    def delete(self, key):
        raise NotImplementedError


class TaskStore(ABC):
    @abstractmethod
    def create(self, task):
        raise NotImplementedError

    @abstractmethod
    def get(self, task_id):
        raise NotImplementedError

    @abstractmethod
    def update(self, task_id, **fields):
        raise NotImplementedError

    @abstractmethod
    def list_active(self):
        raise NotImplementedError
