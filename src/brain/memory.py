import json


class CognitiveMemory:
    def __init__(self, tools):
        self.tools = tools

    def read_context(self) -> str:
        result = self.tools.execute("memory_store", {"action": "read", "key": "chat_context"})
        if result.get("success"):
            return str(result.get("result", ""))[:5000]
        return "No conversation memory available."

    def read_fact(self, key: str) -> str:
        result = self.tools.execute("memory_store", {"action": "read", "key": key[:40]})
        return str(result.get("result", ""))[:1500]

    def save_fact(self, key: str, value: str) -> bool:
        result = self.tools.execute("memory_store", {"action": "save", "key": key[:40], "value": value[:1500]})
        return result.get("success") is True
