import json
import os

import pytest

from src.learning import LearningSystem


def test_lessons_store_symlink_is_not_followed_or_overwritten():
    learning = LearningSystem()
    target = os.path.join(os.path.dirname(learning.log_path), "other_lessons.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump([], handle)
    try:
        os.symlink(target, learning.log_path)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this platform.")

    assert learning._load() == []
    result = learning.record_mistake({"tool": "calculator", "args": {}}, "failed", "test")
    assert result["success"] is True
    assert not os.path.islink(learning.log_path)
    with open(target, "r", encoding="utf-8") as handle:
        assert json.load(handle) == []
