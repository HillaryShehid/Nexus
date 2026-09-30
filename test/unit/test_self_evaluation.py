from types import SimpleNamespace

import pytest

from src.brain.brain import NexusBrain
from src.brain.self_evaluation import SelfEvaluation


def test_assess_classifies_success_partial_blocked_and_unknown():
    assert SelfEvaluation.assess({
        "status": "complete", "verified_steps": 1,
    })["outcome"] == "success"
    assert SelfEvaluation.assess({
        "status": "partial", "verified_steps": 1,
    })["outcome"] == "partial_success"
    assert SelfEvaluation.assess({
        "status": "blocked", "failures": [{"permission_block": True}],
    })["outcome"] == "blocked"
    unknown = SelfEvaluation.assess({"status": "private-value"})
    assert unknown["outcome"] == "unknown"
    assert unknown["status"] == "unknown"


def test_recurring_failures_need_three_distinct_runs_and_make_proposal(tmp_path):
    evaluator = SelfEvaluation(str(tmp_path))
    repeated_event = {
        "status": "failed",
        "failures": [
            {"tool": "calculator", "error": "TOP SECRET diagnostic"}
            for _ in range(3)
        ],
    }

    assert evaluator.record(repeated_event)["weakness_signals"] == []
    assert evaluator.record(repeated_event)["weakness_signals"] == []
    third = evaluator.record(repeated_event)

    assert len(third["weakness_signals"]) == 1
    assert third["weakness_signals"][0]["distinct_runs"] == 3
    proposal = third["proposals"][0]
    assert proposal["status"] == "proposal_only"
    assert proposal["suspected_cause"].startswith("Unknown;")
    assert proposal["required_tests"]
    assert "TOP SECRET" not in (tmp_path / "nexus_performance.json").read_text()


def test_permission_failures_are_counted_but_not_treated_as_tool_weakness(tmp_path):
    evaluator = SelfEvaluation(str(tmp_path))
    result = evaluator.record({
        "status": "blocked",
        "failures": [
            {"tool": "file_system", "error": "Owner approval was not granted."},
        ],
    })

    assert result["outcome"] == "blocked"
    assert result["permission_blocks"] == 1
    assert result["failure_tools"] == []
    assert result["weakness_signals"] == []


def test_history_is_bounded_and_rejects_corruption_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.setattr(SelfEvaluation, "MAX_RECORDS", 3)
    evaluator = SelfEvaluation(str(tmp_path))
    for _ in range(5):
        evaluator.record({"status": "stopped"})
    assert len(evaluator.report()["records"]) == 3

    store = tmp_path / "nexus_performance.json"
    store.write_text("not valid JSON", encoding="utf-8")
    with pytest.raises(ValueError):
        evaluator.record({"status": "stopped"})
    assert store.read_text(encoding="utf-8") == "not valid JSON"


def test_finish_records_only_aggregated_outcome_fields():
    class Model:
        def generate(self, *_args, **_kwargs):
            return {"success": True, "content": "Done."}

    class Identity:
        def response_prompt(self):
            return "Respond safely."

    class Capabilities:
        def select(self, _request):
            return {"active_layers": []}

    class Evaluator:
        def record(self, result):
            assert set(result) == {"status", "verified_steps", "failures"}
            assert "private request" not in repr(result)
            assert "private tool output" not in repr(result)
            assert result["failures"] == [{
                "tool": "calculator", "permission_block": False,
            }]
            return {**SelfEvaluation.assess(result), "history_recorded": True}

    brain = NexusBrain.__new__(NexusBrain)
    brain.model = Model()
    brain.identity = Identity()
    brain.capabilities = Capabilities()
    brain.self_evaluation = Evaluator()
    brain.MAX_RESPONSE_EVIDENCE = 9000
    state = SimpleNamespace(
        goal="private goal",
        intent="answer",
        status="complete",
        request="private request",
        world={},
        completed_steps=[{"detail": "private tool output"}],
        failures=[{
            "tool": "calculator",
            "error": "private diagnostic text",
        }],
    )
    brief = {"success_criteria": []}
    route = SimpleNamespace(name="default", profile="safe")

    result = brain._finish(state, brief, route)

    assert result["response"] == "Done."
    assert result["self_evaluation"]["history_recorded"] is True


def test_evaluation_store_failure_does_not_fail_response():
    class Model:
        def generate(self, *_args, **_kwargs):
            return {"success": True, "content": "Still done."}

    class Identity:
        def response_prompt(self):
            return "Respond safely."

    class Capabilities:
        def select(self, _request):
            return {"active_layers": []}

    class BrokenEvaluator:
        def record(self, _result):
            raise ValueError("private path must not enter logs")

    brain = NexusBrain.__new__(NexusBrain)
    brain.model = Model()
    brain.identity = Identity()
    brain.capabilities = Capabilities()
    brain.self_evaluation = BrokenEvaluator()
    brain.MAX_RESPONSE_EVIDENCE = 9000
    state = SimpleNamespace(
        goal="goal", intent="answer", status="stopped", request="request",
        world={}, completed_steps=[], failures=[],
    )

    result = brain._finish(state, {"success_criteria": []}, SimpleNamespace(
        name="default", profile="safe",
    ))

    assert result["response"] == "Still done."
    assert result["self_evaluation"]["history_recorded"] is False
    assert result["self_evaluation"]["outcome"] == "unknown"
