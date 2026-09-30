import json
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


def test_tool_safety_blocks_are_distinct_from_permission_and_tool_failures(tmp_path):
    result = SelfEvaluation(str(tmp_path)).record({
        "status": "partial",
        "failures": [{
            "tool": "read_page",
            "category": "tool_safety_block",
            "error": "Security Block: internal network target refused",
        }],
    })

    assert result["outcome"] == "blocked"
    assert result["permission_blocks"] == 0
    assert result["safety_blocks"] == 1
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
            assert set(result) == {
                "status", "verified_steps", "failures", "tool_attempts",
                "retry_attempts", "replans", "recovery_success", "duration_ms",
            }
            assert "private request" not in repr(result)
            assert "private tool output" not in repr(result)
            assert result["failures"] == [{
                "tool": "calculator", "category": "unknown", "permission_block": False,
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


def test_assess_computes_rates_and_bounds_runtime_measurements():
    metrics = SelfEvaluation.assess({
        "status": "partial",
        "verified_steps": 2,
        "tool_attempts": 3,
        "retry_attempts": 8,
        "replans": 99,
        "recovery_success": True,
        "duration_ms": 120,
        "failures": [{
            "tool": "calculator",
            "category": "tool_runtime",
            "error": "remote service reports insufficient permission",
        }],
    })

    assert metrics["tool_attempts"] == 3
    assert metrics["retry_attempts"] == 3
    assert metrics["replans"] == SelfEvaluation.MAX_REPLANS
    assert metrics["verification_rate_bp"] == 6666
    assert metrics["tool_failure_rate_bp"] == 3333
    assert metrics["recovery_success"] is True
    assert metrics["duration_ms"] == 120
    assert metrics["failure_events"] == [{
        "tool": "calculator", "category": "tool_runtime",
    }]


def test_root_cause_report_ranks_only_supported_hypotheses(tmp_path):
    evaluator = SelfEvaluation(str(tmp_path))
    evaluator.record({
        "status": "failed",
        "failures": [
            {"tool": "calculator", "category": "tool_runtime", "error": "private detail"},
        ],
    })
    evaluator.record({
        "status": "failed",
        "failures": [
            {"tool": "calculator", "category": "tool_runtime", "error": "another private detail"},
        ],
    })
    analysis = evaluator.report()["root_cause_hypotheses"][0]

    assert analysis["tool"] == "calculator"
    assert analysis["hypotheses"][0]["cause_hypothesis"] == "tool_or_external_dependency"
    assert analysis["hypotheses"][0]["confidence"] == "hypothesis_only"
    assert analysis["conclusion"].startswith("No root cause established")
    assert "private detail" not in (tmp_path / "nexus_performance.json").read_text()


def test_v1_history_migrates_without_inventing_unavailable_metrics(tmp_path):
    store = tmp_path / "nexus_performance.json"
    store.write_text(json.dumps({
        "schema_version": 1,
        "records": [{
            "record_id": "a" * 32,
            "recorded_at": "2026-09-30T10:00:00+00:00",
            "outcome": "failure",
            "status": "failed",
            "goal_achieved": False,
            "verified_steps": 0,
            "reported_failures": 1,
            "permission_blocks": 0,
            "failure_tools": ["calculator"],
        }],
    }), encoding="utf-8")
    evaluator = SelfEvaluation(str(tmp_path))

    legacy = evaluator.report()["records"][0]
    assert legacy["tool_attempts"] is None
    assert legacy["failure_events"] == [{"tool": "calculator", "category": "unknown"}]

    evaluator.record({"status": "stopped"})
    migrated_store = json.loads(store.read_text(encoding="utf-8"))
    assert migrated_store["schema_version"] == SelfEvaluation.SCHEMA_VERSION
    assert len(migrated_store["records"]) == 2
