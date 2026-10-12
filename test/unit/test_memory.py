import json

from src.brain.local_memory_store import LocalMemoryStore
from src.brain.memory import CognitiveMemory
from src.tools import ToolSystem


def test_conversation_history_round_trips_as_structured_entries(tmp_path, monkeypatch):
    tools = ToolSystem()
    monkeypatch.setattr(tools, "memory_file", str(tmp_path / "nexus_memory.json"))

    memory = CognitiveMemory(tools, store=LocalMemoryStore(tools))
    assert memory.save_conversation("hello", "Hi there") is True
    assert memory.save_conversation("second", "Still here") is True

    context = memory.read_context()
    assert "User: hello" in context
    assert "Nexus: Hi there" in context
    assert "User: second" in context
    assert "Nexus: Still here" in context


def test_legacy_json_string_conversations_are_readable(tmp_path, monkeypatch):
    tools = ToolSystem()
    memory_file = tmp_path / "nexus_memory.json"
    monkeypatch.setattr(tools, "memory_file", str(memory_file))
    legacy_entry = json.dumps({"user": "old", "assistant": "reply"})
    memory_file.write_text(
        json.dumps({"conversations": [legacy_entry], "facts": {}}),
        encoding="utf-8",
    )

    memory = CognitiveMemory(tools, store=LocalMemoryStore(tools))
    context = memory.read_context()
    assert "User: old" in context
    assert "Nexus: reply" in context

def test_long_escaped_conversation_remains_valid_json(tmp_path, monkeypatch):
    tools = ToolSystem()
    monkeypatch.setattr(tools, "memory_file", str(tmp_path / "nexus_memory.json"))
    memory = CognitiveMemory(tools, store=LocalMemoryStore(tools))

    user_message = '"' * 8000
    assistant_message = "\\" * 12000
    assert memory.save_conversation(user_message, assistant_message) is True

    raw = LocalMemoryStore(tools).get("chat_context")
    history = json.loads(raw)
    assert len(history) == 1
    assert history[0]["user"] == user_message
    assert history[0]["assistant"] == assistant_message
