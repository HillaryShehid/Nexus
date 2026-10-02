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


def test_real_local_memory_store_does_not_truncate_history():
    from src.brain.local_memory_store import LocalMemoryStore
    from src.tools import ToolSystem

    tools = ToolSystem()
    tools.memory_file = str(__import__("pathlib").Path(tools.workspace_root) / "test-chat-memory.json")
    store = LocalMemoryStore(tools)
    memory = CognitiveMemory(tools=tools, store=store)

    for index in range(40):
        assert memory.save_conversation("u" * 100 + str(index), "a" * 200 + str(index))

    history = json.loads(store.get("chat_context"))
    assert len(history) == 40
    assert history[0]["user"].startswith("u" * 100)
    assert history[-1]["assistant"].endswith("39")


def test_generic_store_fallback_appends_history():
    class GenericStore:
        def __init__(self):
            self.values = {}
        def get(self, key):
            return self.values.get(key, "")
        def save(self, key, value):
            self.values[key] = value
            return True

    memory = CognitiveMemory(tools=None, store=GenericStore())
    for index in range(25):
        assert memory.save_conversation(f"user {index}", f"reply {index}") is True
    history = json.loads(memory.store.values["chat_context"])
    assert len(history) == 25
    assert history[-1]["user"] == "user 24"
