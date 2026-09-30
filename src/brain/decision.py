import json

from src.registry import MAX_PLAN_STEPS, SHARED_REGISTRY


class DecisionEngine:
    def __init__(self, model, planner):
        self.model = model
        self.planner = planner

    def choose(self, state_snapshot: dict, lessons: str) -> dict:
        registry = list(SHARED_REGISTRY.keys())
        system = f"""You are Nexus v1.4.1's decision engine.
Choose the next useful action for the owner's goal.
You may select only registered tools: {registry}.
Do not invent tools, arguments, permissions, facts, or completed results.
If no tool is needed, choose tool=\"none\".
Prefer the smallest action that makes measurable progress.
Use previous failures and lessons to avoid repeating known mistakes.
Return ONLY JSON:
{{\"action\":\"tool\",\"args\":{{}},\"reason\":\"...\",\"description\":\"...\"}}
"""
        prompt = f"STATE:\n{json.dumps(state_snapshot, ensure_ascii=False)[:7000]}\n\nLESSONS:\n{lessons[:4000]}"
        response = self.model.generate(system, prompt, json_mode=True)
        if not response.get("success"):
            return {"action": "none", "args": {}, "reason": "Model unavailable.", "description": "No action selected."}
        try:
            raw = json.loads(response["content"])
            if not isinstance(raw, dict):
                raise ValueError
            action = str(raw.get("action", "none"))
            args = raw.get("args", {})
            reason = str(raw.get("reason", ""))[:400]
            description = str(raw.get("description", "Make progress toward the goal."))[:150]
            if action != "none":
                task = {"step": 1, "tool": action, "args": args, "description": description}
                check = self.planner.validate_task_schema(task, expected_step_index=1)
                if not check["valid"]:
                    return {"action": "none", "args": {}, "reason": "Decision failed task validation.", "description": "No safe action selected."}
            return {"action": action, "args": args if isinstance(args, dict) else {}, "reason": reason, "description": description}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {"action": "none", "args": {}, "reason": "Decision output was invalid.", "description": "No safe action selected."}
