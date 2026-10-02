import json

from src.brain.memory import CognitiveMemory


class FakeStore:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key, "")

    def save(self, key, value):
        self.values[key] = value
        return True


def test_conversation_history_has_no_artificial_count_limit():
    store = FakeStore()
    memory = CognitiveMemory(tools=None, store=store)

    for index in range(75):
        assert memory.save_conversation(f"hello {index}", f"reply {index}") is True

    history = json.loads(store.values["chat_context"])
    assert len(history) == 75
    assert history[-1]["user"] == "hello 74"


def test_prompt_context_uses_recent_window_without_deleting_history():
    store = FakeStore()
    memory = CognitiveMemory(tools=None, store=store)

    for index in range(30):
        memory.save_conversation(f"hello {index}", f"reply {index}")

    context = memory.read_context()
    assert "hello 29" in context
    assert "hello 10" in context
    assert "hello 9" not in context
    assert len(json.loads(store.values["chat_context"])) == 30
