import json

from src.planner import Planner


class PlanningModel:
    def __init__(self, task):
        self.task = task
        self.system = ""
        self.prompt = ""

    def generate(self, system, prompt, **_kwargs):
        self.system = system
        self.prompt = prompt
        return {"success": True, "content": json.dumps({"plan": [self.task]})}


def test_planner_uses_only_knowledge_ids_present_in_world_model_context():
    knowledge_id = "K0123456789ab"
    model = PlanningModel({
        "step": 1,
        "tool": "calculator",
        "args": {"expression": "2 + 2"},
        "description": "Calculate the requested sum.",
        "rationale": f"The source-backed behavior in {knowledge_id} guides this check.",
        "knowledge_ids": [knowledge_id, "Kaaaaaaaaaaaa"],
    })
    planner = Planner(model)
    context = json.dumps({
        "world": {"knowledge": [{
            "knowledge_id": knowledge_id,
            "kind": "fact",
            "status": "source_supported",
            "confidence": "high",
        }]},
    })

    plan = planner.construct_plan("Calculate a sum", context)

    assert plan[0]["knowledge_ids"] == [knowledge_id]
    assert knowledge_id in plan[0]["rationale"]
    assert "ground truth" in model.system
    assert "not hidden chain-of-thought" in model.system


def test_planner_drops_rationale_with_unavailable_knowledge_reference():
    model = PlanningModel({
        "step": 1,
        "tool": "calculator",
        "args": {"expression": "2 + 2"},
        "description": "Calculate the requested sum.",
        "rationale": "The estimate in Kaaaaaaaaaaaa supports this step.",
        "knowledge_ids": ["Kaaaaaaaaaaaa"],
    })

    plan = Planner(model).construct_plan("Calculate a sum", "Recovery context is unstructured.")

    assert plan[0]["rationale"] == ""
    assert plan[0]["knowledge_ids"] == []


def test_planner_rejects_malformed_optional_reasoning_fields():
    planner = Planner(None)
    task = {
        "step": 1,
        "tool": "calculator",
        "args": {"expression": "2 + 2"},
        "description": "Calculate the requested sum.",
        "rationale": 42,
    }

    assert planner.validate_task_schema(task)["valid"] is False
