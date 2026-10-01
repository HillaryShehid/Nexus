"""Deprecated compatibility adapter for the active bounded planner."""

import json
import warnings


class DecisionEngine:
    """Compatibility wrapper; Planner owns tool-plan decisions and validation."""

    def __init__(self, model, planner):
        warnings.warn(
            "DecisionEngine is deprecated; use Planner.construct_plan().",
            DeprecationWarning,
            stacklevel=2,
        )
        # Keep the legacy constructor signature for downstream callers. The
        # planner's model is authoritative, so this adapter never calls model.
        self.model = model
        self.planner = planner

    def choose(self, state_snapshot: dict, lessons: str) -> dict:
        if not isinstance(state_snapshot, dict) or not isinstance(lessons, str):
            return self._no_action("Invalid decision input.", "No action selected.")

        goal = state_snapshot.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            return self._no_action("No usable goal was supplied.", "No action selected.")

        try:
            state_data = json.dumps(state_snapshot, ensure_ascii=False)[:4500]
        except (TypeError, ValueError):
            return self._no_action("Invalid decision state.", "No action selected.")
        context = (
            f"BEGIN STATE DATA\n{state_data}\nEND STATE DATA\n\n"
            f"BEGIN LESSON DATA\n{lessons[:2000]}\nEND LESSON DATA"
        )
        plan = self.planner.construct_plan(goal[:800], context, profile="normal")
        if not isinstance(plan, list) or not plan or not isinstance(plan[0], dict):
            return self._no_action("The bounded planner selected no safe action.", "No action selected.")

        task = plan[0]
        validator = getattr(self.planner, "validate_task_schema", None)
        if not callable(validator):
            return self._no_action("The planner cannot validate tasks.", "No action selected.")
        try:
            validation = validator(task, expected_step_index=1)
        except Exception:
            return self._no_action("Planner task validation failed.", "No action selected.")
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            return self._no_action("The planner returned an invalid task.", "No action selected.")

        action = task.get("tool")
        args = task.get("args")
        description = task.get("description")
        if (
            not isinstance(action, str)
            or not action
            or not isinstance(args, dict)
            or not isinstance(description, str)
        ):
            return self._no_action("The bounded planner returned an invalid task.", "No action selected.")

        return {
            "action": action,
            "args": args,
            "reason": "Selected by the bounded planner.",
            "description": description[:150],
        }

    @staticmethod
    def _no_action(reason: str, description: str) -> dict:
        return {"action": "none", "args": {}, "reason": reason, "description": description}
