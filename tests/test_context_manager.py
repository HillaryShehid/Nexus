import pytest

from src.context_manager import SlidingContextManager


def test_context_manager_keeps_latest_turns_under_budget():
    manager = SlidingContextManager(max_token_ceiling=512, reserved_system_tokens=256, max_turns=20)
    history = [
        {"user": f"old-{index}-" + ("x" * 500), "assistant": "y" * 500}
        for index in range(10)
    ]
    history.append({"user": "latest question", "assistant": "latest answer"})
    compiled = manager.compile_history(history)
    assert "latest question" in compiled
    assert "latest answer" in compiled
    assert len(compiled) <= 256 * 4


def test_context_manager_does_not_mutate_or_delete_history():
    manager = SlidingContextManager(max_token_ceiling=512, reserved_system_tokens=256)
    history = [{"user": "hello", "assistant": "hi"}]
    manager.compile_history(history)
    assert history == [{"user": "hello", "assistant": "hi"}]


def test_context_manager_validates_configuration():
    with pytest.raises(ValueError):
        SlidingContextManager(max_token_ceiling=100, reserved_system_tokens=200)
    with pytest.raises(ValueError):
        SlidingContextManager(max_turns=0)


def test_context_manager_ignores_malformed_items():
    manager = SlidingContextManager()
    assert manager.compile_history([None, "bad", 4]) == "No persisted conversation context is loaded."
