import json

import pytest

from src.brain.decision import DecisionEngine
from src.brain.understanding import UnderstandingEngine


def test_understanding_compatibility_adapter_delegates_to_executive(mocker):
    model = mocker.MagicMock()
    model.generate.return_value = {
        "success": True,
        "content": json.dumps({"goal": "answer the question", "needs_action": False}),
    }

    with pytest.warns(DeprecationWarning, match="ExecutiveController"):
        engine = UnderstandingEngine(model)
    result = engine.analyze("Answer this", "memory", "lessons")

    assert result == {
        "goal": "answer the question",
        "intent": "general",
        "constraints": [],
        "known_facts": [],
        "missing_information": [],
        "assumptions": [],
        "needs_action": False,
    }
    model.generate.assert_called_once()


def test_decision_compatibility_adapter_delegates_to_planner(mocker):
    model = mocker.MagicMock()
    planner = mocker.MagicMock()
    planner.construct_plan.return_value = [{
        "step": 1,
        "tool": "web_search",
        "args": {"query": "Nexus architecture"},
        "description": "Find relevant architecture references.",
    }]
    planner.validate_task_schema.return_value = {"valid": True}

    with pytest.warns(DeprecationWarning, match="Planner.construct_plan"):
        engine = DecisionEngine(model, planner)
    result = engine.choose({"goal": "Research the design", "status": "planning"}, "lesson data")

    assert result == {
        "action": "web_search",
        "args": {"query": "Nexus architecture"},
        "reason": "Selected by the bounded planner.",
        "description": "Find relevant architecture references.",
    }
    planner.construct_plan.assert_called_once()
    objective, context = planner.construct_plan.call_args.args
    assert objective == "Research the design"
    assert '"status": "planning"' in context
    assert "lesson data" in context
    planner.validate_task_schema.assert_called_once_with(
        planner.construct_plan.return_value[0],
        expected_step_index=1,
    )
    model.generate.assert_not_called()


def test_decision_compatibility_adapter_fails_closed_on_invalid_planner_task(mocker):
    planner = mocker.MagicMock()
    planner.construct_plan.return_value = [{
        "step": 1,
        "tool": "unregistered_tool",
        "args": {},
        "description": "Try an unknown tool.",
    }]
    planner.validate_task_schema.return_value = {"valid": False}

    with pytest.warns(DeprecationWarning):
        engine = DecisionEngine(mocker.MagicMock(), planner)
    result = engine.choose({"goal": "Do a task"}, "")

    assert result["action"] == "none"
    assert result["args"] == {}
    assert planner.validate_task_schema.called


def test_decision_compatibility_adapter_selects_no_action_for_empty_plan(mocker):
    planner = mocker.MagicMock()
    planner.construct_plan.return_value = []

    with pytest.warns(DeprecationWarning):
        engine = DecisionEngine(mocker.MagicMock(), planner)
    result = engine.choose({"goal": "No tool needed"}, "")

    assert result["action"] == "none"
    assert result["args"] == {}
    planner.validate_task_schema.assert_not_called()


def test_decision_adapter_keeps_state_and_lessons_inside_planner_context(mocker):
    planner = mocker.MagicMock()
    planner.construct_plan.return_value = []

    with pytest.warns(DeprecationWarning):
        engine = DecisionEngine(mocker.MagicMock(), planner)
    engine.choose({"goal": "Review state", "details": "x" * 10000}, "LESSON_MARKER")

    _, context = planner.construct_plan.call_args.args
    assert len(context) < 7000
    assert "END STATE DATA" in context
    assert "LESSON_MARKER" in context
    assert "END LESSON DATA" in context
