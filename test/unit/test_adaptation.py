from types import SimpleNamespace

from src.brain.adaptation import AdaptationEngine


class FakeLearning:
    pass


def test_diagnosis_keeps_candidate_explanation_as_a_hypothesis():
    captured = {}

    class Model:
        def generate(self, system, prompt, **_kwargs):
            captured.update(system=system, prompt=prompt)
            return {"success": True, "content": "The remote lookup may have timed out."}

    state = SimpleNamespace(
        goal="Research a public source",
        failures=[{
            "step": 2, "tool": "web_search", "category": "external_dependency",
        }],
    )
    cause = AdaptationEngine(Model(), FakeLearning()).diagnose(
        state,
        {"step": 2, "tool": "web_search", "args": {"query": "public documentation"}},
        "Network Error: Host resolution failed.",
    )

    assert cause.startswith("Hypothesis only:")
    assert "external_dependency" in captured["prompt"]
    assert "Unknown cause" in captured["system"]


def test_diagnosis_reports_unknown_when_model_has_insufficient_evidence():
    class Model:
        def generate(self, *_args, **_kwargs):
            return {"success": True, "content": "Insufficient evidence to determine why."}

    state = SimpleNamespace(goal="Investigate", failures=[])
    cause = AdaptationEngine(Model(), FakeLearning()).diagnose(
        state, {"tool": "calculator", "args": {}}, "Unexpected verification mismatch."
    )

    assert cause == "Unknown cause"
